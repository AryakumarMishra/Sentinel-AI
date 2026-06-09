import os
import json
import re
import httpx
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from ..config.settings import settings
from pydantic import BaseModel
from ..workflows.pipeline_recovery import PipelineRecoveryWorkflow
from ..runtime.adk_runtime import execute_agent
from ..utils import parse_fix_json, verify_file_exists
from ..utils import HEALING_SEMAPHORE

routes_router = APIRouter()

class ManualTriggerRequest(BaseModel):
    project_path: str
    pipeline_id: int
    commit_sha: str = "main"

class ApprovalDecisionRequest(BaseModel):
    approve: bool



async def run_background_agent_job(
        recovery_id: str, 
        project_path: str, 
        pipeline_id: int, 
        commit_sha: str
    ):
    async with HEALING_SEMAPHORE:
        """Executes the Google ADK healing run while logging checkpoints."""
        # Reloading workflow state to track update progress
        state_data = PipelineRecoveryWorkflow.get_recovery_by_id(recovery_id)
        if not state_data:
            return
        
        # Rehydrating tracker class
        tracker = PipelineRecoveryWorkflow(pipeline_id, project_path, commit_sha)
        tracker.recovery_id = recovery_id
        
        try:
            tracker.log_step("ANALYZING", "IN_PROGRESS", "Gemini exploring failed job runs...")
            
            prompt = f"""
                You are analyzing a failed CI/CD pipeline. Use the available tools to diagnose the problem, but do NOT run any deployment actions (create_branch, commit_file_change, create_merge_request).

                Pipeline:
                - Project Path: {project_path}
                - Pipeline ID: {pipeline_id}
                - Ref: {commit_sha}

                Steps:
                1. Call get_failed_jobs(project_path="{project_path}", pipeline_id={pipeline_id})
                2. From the result, extract the job_id, then call get_pipeline_logs(project_path="{project_path}", job_id=<job_id>)
                3. From the logs, identify the file mentioned in the error (e.g., src/test_math.py:4). Call read_repository_files(project_path="{project_path}", file_path="<path from logs>", ref="{commit_sha}") to read it. Note which directory the file is in and examine its import statements.
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
            
            full_response_text = await execute_agent(
                prompt=prompt,
                session_id=f"analysis_{recovery_id}"
            )

            tracker.log_step("COMPLETED", "SUCCESS", f"Execution complete. Agent Note: {full_response_text[:200]}")

            fix_json = parse_fix_json(full_response_text)
            
            if fix_json:
                required_keys = {'file_path', 'explanation', 'content'}
                missing = required_keys - set(fix_json.keys())
                if missing:
                    tracker.log_step("CRASHED", "FAILED", f"AI patch missing required fields: {', '.join(sorted(missing))}")
                else:
                    exists = await verify_file_exists(project_path, fix_json["file_path"], commit_sha)
                    
                    if not exists:
                        tracker.log_step("COMPLETED", "FAILED", f"Agent hallucinated path'{fix_json['file_path']}'")
                        return
                    
                    tracker.proposed_fix = fix_json
                    tracker.log_step("AWAITING_APPROVAL", "IN_PROGRESS", "AI patch ready. Waiting for human approval")
            else:
                tracker.log_step("CRASHED", "FAILED", "Failed to parse structured JSON repair patch matrix from agent response.")
                
            
        except Exception as e:
            tracker.log_step("CRASHED", "FAILED", f"Error encountered during runtime orchestration: {str(e)}")


async def complete_healing_after_approval(recovery_id: str):
    """Executes the final GitLab deployment after Human gives approval.
    Calls GitLab API directly — no agent/MCP needed for the deploy phase."""
    tracker_data = PipelineRecoveryWorkflow.get_recovery_by_id(recovery_id)
    if not tracker_data:
        return

    tracker = PipelineRecoveryWorkflow(tracker_data['pipeline_id'], tracker_data['project_name'], tracker_data['commit_sha'])
    tracker.recovery_id = recovery_id
    tracker.proposed_fix = tracker_data['proposed_fix']

    try:
        tracker.log_step("REMEDIATION", "IN_PROGRESS", "Human approved! Pushing fix branch and creating MR...")

        fix_info = tracker.proposed_fix
        required_keys = {'file_path', 'explanation', 'content'}
        if not fix_info or not all(k in fix_info for k in required_keys):
            missing = required_keys - set(fix_info.keys()) if fix_info else required_keys
            tracker.log_step("COMPLETED", "FAILED", f"Proposed fix malformed — missing: {', '.join(sorted(missing))}")
            return

        project_path = tracker.project_name
        encoded_project_path = project_path.replace("/", "%2F")
        branch_name = f"fix/pipeline-{tracker_data['pipeline_id']}"
        file_path = fix_info['file_path']
        encoded_file_path = file_path.replace("/", "%2F")
        headers = {"PRIVATE-TOKEN": settings.GITLAB_PRIVATE_TOKEN}
        base = settings.GITLAB_BASE_URL

        async with httpx.AsyncClient() as client:
            # Creating branch
            branch_resp = await client.post(
                f"{base}/projects/{encoded_project_path}/repository/branches",
                headers=headers,
                json={"branch": branch_name, "ref": "main"}
            )
            if branch_resp.status_code != 201:
                tracker.log_step("COMPLETED", "FAILED", f"Branch creation failed: {branch_resp.status_code} — {branch_resp.text}")
                return

            # Committing the file (PUT to update, fallback to POST to create)
            file_url = f"{base}/projects/{encoded_project_path}/repository/files/{encoded_file_path}"
            file_payload = {
                "branch": branch_name,
                "commit_message": f"[Sentinel AI] Automated fix: {fix_info.get('explanation', 'pipeline remediation')}",
                "content": fix_info['content']
            }
            file_resp = await client.put(file_url, headers=headers, json=file_payload)
            if file_resp.status_code == 400:
                file_resp = await client.post(file_url, headers=headers, json=file_payload)
            if file_resp.status_code not in (200, 201):
                tracker.log_step("COMPLETED", "FAILED", f"File commit failed: {file_resp.status_code} — {file_resp.text}")
                return

            # Creating the Merge Request 
            mr_resp = await client.post(
                f"{base}/projects/{encoded_project_path}/merge_requests",
                headers=headers,
                json={
                    "source_branch": branch_name,
                    "target_branch": "main",
                    "title": "[Sentinel AI] Automated pipeline fix",
                    "description": f"Sentinel AI detected and fixed a pipeline failure.\n\nRoot Cause: {fix_info.get('explanation', 'N/A')}\n\nFile: {file_path}"
                }
            )
            if mr_resp.status_code != 201:
                tracker.log_step("COMPLETED", "FAILED", f"MR creation failed: {mr_resp.status_code} — {mr_resp.text}")
                return

            mr_url = mr_resp.json().get("web_url", "")
            tracker.log_step("COMPLETED", "SUCCESS", f"MR created: {mr_url}")

    except Exception as e:
        tracker.log_step("CRASHED", "FAILED", f"Deployment execution failed: {str(e)}")




@routes_router.get("/recoveries")
def list_recoveries():
    """Returns a full record history to feed the main Next.js timeline index grid."""
    return PipelineRecoveryWorkflow.get_all_recoveries()


@routes_router.get("/recoveries/{recovery_id}")
def get_recovery_detail(recovery_id: str):
    """Returns detailed real-time logs for a specific tracking item."""
    detail = PipelineRecoveryWorkflow.get_recovery_by_id(recovery_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Recovery tracking session index not found")
    return detail


@routes_router.post("/recoveries/manual-trigger")
def trigger_manual_healing(payload: ManualTriggerRequest, background_tasks: BackgroundTasks):
    """Allows developers to test or run fixes on-demand from the UI."""
    # Creating the initial tracking state record
    tracker = PipelineRecoveryWorkflow(payload.pipeline_id, payload.project_path, payload.commit_sha)
    
    # Offloading to async processing threads to avoid API lock-ups
    background_tasks.add_task(
        run_background_agent_job,
        recovery_id=tracker.recovery_id,
        project_path=payload.project_path,
        pipeline_id=payload.pipeline_id,
        commit_sha=payload.commit_sha
    )
    return {"status": "enqueued", "recovery_id": tracker.recovery_id}


@routes_router.post("/recoveries/{recovery_id}/decision")
def handle_human_decision(recovery_id: str, payload: ApprovalDecisionRequest, background_tasks: BackgroundTasks):
    """Receives approval or rejection requests from the Next.js frontend action buttons."""
    state_data = PipelineRecoveryWorkflow.get_recovery_by_id(recovery_id)
    if not state_data:
        raise HTTPException(status_code=404, detail="Recovery ID not found")
        
    # Instantiate tracker object safely
    file_path = os.path.join("recovery_states", f"{recovery_id}.json")
    
    if not payload.approve:
        state_data['status'] = "REJECTED_BY_HUMAN"
        with open(file_path, "w") as f:
            json.dump(state_data, f, indent=4)
        return {"status": "rejected", "message": "AI patch discarded by operator successfully."}
        
    # Updating state file to reflect human authorization checkmark
    state_data['status'] = "APPROVED_BY_HUMAN"
    state_data['approved_by_human'] = True
    with open(file_path, "w") as f:
        json.dump(state_data, f, indent=4)
        
    # Starting the final deployment tools in the background
    background_tasks.add_task(complete_healing_after_approval, recovery_id=recovery_id)
    return {"status": "approved", "message": "Deployment workflow resumed."}
