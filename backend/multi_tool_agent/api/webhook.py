import uuid
import time
import asyncio
import hashlib
import hmac
import base64
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
from ..workflows.pipeline_recovery import PipelineRecoveryWorkflow
from ..config.settings import settings
from ..runtime.adk_runtime import execute_agent
from ..utils import parse_fix_json, verify_file_exists
from ..utils import HEALING_SEMAPHORE


webhook_router = APIRouter()
GITLAB_WEBHOOK_SECRET = settings.GITLAB_WEBHOOK_SECRET

ACTIVE_LOCKS: dict[str, dict] = {}
LOCK_TTL = 900 # seconds


def _check_and_acquire_lock(project_name: str, recovery_id: str) -> bool:
    """Returns True if lock was aquired, False if already healing."""
    now = time.time()

    # TTL gaurd: clean expired locks
    expired = [k for k, v in ACTIVE_LOCKS.items() if now - v["locked_at"] > LOCK_TTL]
    for k in expired:
        del ACTIVE_LOCKS[k]
    
    if project_name in ACTIVE_LOCKS:
        # Double-checking against state file (in case the server restarted)
        existing = PipelineRecoveryWorkflow.get_recovery_by_id(
            ACTIVE_LOCKS[project_name]['recovery_id']
        )
        if existing and existing.get("status") in (
            "TRIGGERED", "ANALYZING", "AWAITING_APPROVAL"
        ):
            return False
        # Deleting stale lock
        del ACTIVE_LOCKS[project_name]
    
    ACTIVE_LOCKS[project_name] = {"recovery_id": recovery_id, "locked_at": now}
    return True


async def run_agent_healing_pipeline(
        project_name: str, 
        pipeline_id: int, 
        commit_sha: str, 
        recovery_id: str
    ):
    async with HEALING_SEMAPHORE:
        """Called by backgroud worker. Gated by semaphore + lock lifecycle"""
        tracker = PipelineRecoveryWorkflow(pipeline_id, project_name, commit_sha)
        tracker.recovery_id = recovery_id

        try:
            tracker.log_step("TRIGGERED", "IN_PROGRESS", "Webhook_received - starting automated healing")
        
            # A runtime prompt dynamically targeting the failure context
            prompt =  f"""
                    You are analyzing a failed CI/CD pipeline. Use the available tools to diagnose the problem, but do NOT run any deployment actions (create_branch, commit_file_change, create_merge_request).

                    Pipeline:
                    - Project Path: {project_name}
                    - Pipeline ID: {pipeline_id}
                    - Ref: {commit_sha}

                    Steps:
                    1. Call get_failed_jobs(project_path="{project_name}", pipeline_id={pipeline_id})
                    2. From the result, extract the job_id, then call get_pipeline_logs(project_path="{project_name}", job_id=<job_id>)
                    3. From the logs, identify the file mentioned in the error (e.g., src/test_math.py:4). Call read_repository_files(project_path="{project_name}", file_path="<path from logs>", ref="{commit_sha}") to read it. Note which directory the file is in and examine its import statements.
                    4. If the file imports from another module (e.g., "from math_operations import ..."), the source file may be in the same directory OR at the project root. Try read_repository_files at each possible path:
                    - First try: same directory as the test file (e.g., src/math_operations.py)
                    - Then try: one level up (e.g., math_operations.py)
                    Use whichever returns file content successfully — that's the real bug location.

                    After all steps, output a JSON block with the fix for the BUGGY SOURCE FILE:
                    ```json
                    {{
                        "file_path": "<the dependency file path that needs fixing>",
                        "explanation": "<root cause>",
                        "content": "<full corrected file content>"
                    }}
                    """
            tracker.log_step("ANALYZING", "IN_PROGRESS", "Gemini diagnosing failure....")

            response = await execute_agent(
                prompt=prompt,
                session_id=f"analysis_{recovery_id}"
            )

            fix_json = parse_fix_json(response)
            if not fix_json:
                tracker.log_step("COMPLETED", "FAILED", "Failed to parse JSON structure from agent")
                return
            
            missing = {"file_path", "explanation", "content"} - set(fix_json.keys())
            if missing:
                tracker.log_step("COMPLETED", "FAILED", f"AI patch missing fields: {', '.join(sorted(missing))}")
                return
            
            exists = await verify_file_exists(
                project_name, fix_json["file_path"], commit_sha
            )
            if not exists:
                tracker.log_step("COMPLETED", "FAILED", f"Agent hallucinated path'{fix_json['file_path']}'")
                return
            
            tracker.proposed_fix = fix_json
            tracker.log_step("AWAITING_APPROVAL", "IN_PROGRESS", "AI patch ready. Waiting for human approval")
        
        except Exception as e:
            tracker.log_step("CRASHED", "FAILED", f"Healing pipeline failed: {str(e)}")
        
        finally:
            ACTIVE_LOCKS.pop(project_name, None)

        


@webhook_router.post("/gitlab-webhook")
async def handle_gitlab_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    webhook_signature: str = Header(None, alias="webhook-signature"),
    event_id: str = Header(None, alias="webhook-id"),
    timestamp: str = Header(None, alias="webhook-timestamp"),
):
    # Security validation
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    raw_key = base64.b64decode(GITLAB_WEBHOOK_SECRET.removeprefix('whsec_'))
    message = f"{event_id}.{timestamp}.{body_str}".encode('utf-8')  
    digest = hmac.new(raw_key, message, hashlib.sha256).digest()
    expected = "v1," + base64.b64encode(digest).decode('utf-8')

    if not any(
        hmac.compare_digest(expected, sig)
        for sig in (webhook_signature or "").split(' ')
    ):
        raise HTTPException(status_code=401, detail="Invalid GitLab Webhook Signature")


    # Extracting the payload data as JSON
    payload = await request.json()
    if payload.get("object_kind") != "pipeline":
        return {"status": "ignored", "message": "Not a pipeline event"}
    
    attributes = payload.get("object_attributes", {})
    if attributes.get("status") != "failed":
        return {"status": "ignored", "message": "Pipeline not in a failed state"}
    
    project_name = payload.get("project", {}).get("path_with_namespace")
    pipeline_id = attributes.get("id")
    commit_sha = attributes.get("sha")

    # Generating the recovery_id upfront for the lock
    recovery_id = str(uuid.uuid4())

    if not _check_and_acquire_lock(project_name, recovery_id):
        return {"status": "skipped", "message": f"Already healing {project_name} - webhook skipped"}
            
    # Delegating to background workers so GitLab gets an immediate HTTP 200 back
    background_tasks.add_task(
        run_agent_healing_pipeline,
        project_name=project_name, 
        recovery_id=recovery_id,
        pipeline_id=pipeline_id, 
        commit_sha=commit_sha
    )
    return {"status": "processing", "recovery_id": recovery_id, "message": "Failing pipeline passed to Sentinel Agent."}
