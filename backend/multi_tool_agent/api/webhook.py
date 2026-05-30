import uuid
from google.adk.runners import InMemoryRunner
from google.genai import types
from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
from ..agent import root_agent
from ..config.settings import settings
from ..runtime.adk_runtime import execute_agent

webhook_router = APIRouter()

# Securing webhooks via Secret Token
GITLAB_WEBHOOK_SECRET = settings.GITLAB_WEBHOOK_SECRET

async def run_agent_healing_pipeline(project_id: str, project_name: str, pipeline_id: int, commit_sha: str):
    """Executes the Google ADK healing cycle as a detached background thread."""
    print(f"Triggering ADK Healing workflow for project {project_name}...")
    
    # A runtime prompt dynamically targeting the failure context
    prompt =  f"""
        SYSTEM OVERRIDE: You are in AUTONOMOUS HEALING MODE. Your goal is to fix this pipeline failure end-to-end.

        Pipeline failure context:
        - Project Path: {project_name}
        - Pipeline ID: {pipeline_id}
        - Failing Commit SHA: {commit_sha}

        Follow this exact operational loop:

        Step 1 — Call get_failed_jobs(project_path="{project_name}", pipeline_id={pipeline_id})

        Step 2 — From Step 1, extract the job_id, then call get_pipeline_logs(project_path="{project_name}", job_id=<the job_id>)

        Step 3 — From the logs, find the exact file path that caused the error. Call read_repository_files(project_path="{project_name}", file_path="<the exact path>", ref="{commit_sha}")

        Step 4 — Generate the corrected file content and call create_branch(project_path="{project_name}", branch_name="fix/pipeline-{pipeline_id}", ref="{commit_sha}")

        Step 5 — Call commit_file_change(project_path="{project_name}", branch_name="fix/pipeline-{pipeline_id}", file_path="<the exact file path>", commit_message="[Sentinel AI] Automated pipeline fix", file_content="<the corrected content>")

        Step 6 — Call create_merge_request(project_path="{project_name}", source_branch="fix/pipeline-{pipeline_id}", title="[Sentinel AI] Automated pipeline fix", description="Sentinel AI automatically fixed the failed pipeline.\\n\\nRoot cause extracted from pipeline #{pipeline_id} logs.")

        After completion, output a brief summary of what was fixed.
        """

    session_id = f"pipeline_fix_{pipeline_id}_{uuid.uuid4().hex[:6]}"

    try:
        response = await execute_agent(
            prompt=prompt,
            session_id=session_id
        )

        print(response)
        print(f"\nADK Healing pipeline finished for session: {session_id}")

    except Exception as e:
        print(f"ADK Healing pipeline crashed: {str(e)}")


@webhook_router.post("/gitlab-webhook")
async def handle_gitlab_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    x_gitlab_token: str = Header(None) # Token matching configured value in GitLab UI
):
    # Security validation
    if x_gitlab_token != GITLAB_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid GitLab Webhook Secret Token")

    # Extracting the payload data as JSON
    payload = await request.json()
    
    # Detecting what type of event sent this hook
    object_kind = payload.get("object_kind") # Expected: 'pipeline' or 'deployment' or 'build'
    
    if object_kind == "pipeline":
        attributes = payload.get("object_attributes", {})
        status = attributes.get("status") # 'pending', 'running', 'success', 'failed'
        
        # We only care if there is a failure
        if status == "failed":
            project_id = payload.get("project", {}).get("id")
            project_name = payload.get("project", {}).get("path_with_namespace")
            pipeline_id = attributes.get("id")
            commit_sha = attributes.get("sha")
            
            # Delegating to background workers so GitLab gets an immediate HTTP 200 back
            background_tasks.add_task(
                run_agent_healing_pipeline, 
                project_id=str(project_id), 
                project_name=project_name, 
                pipeline_id=pipeline_id, 
                commit_sha=commit_sha
            )
            return {"status": "processing", "message": "Failing pipeline passed to Sentinel Agent."}
            
    # Ignoring passing/running stages to prevent unnecessary token usage 
    return {"status": "ignored", "message": "Not a failing pipeline event status."}
