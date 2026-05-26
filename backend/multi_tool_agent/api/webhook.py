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
    prompt = f"""
    GitLab Pipeline failure detected!
    - Project ID: {project_id}
    - Project Name: {project_name}
    - Failed Pipeline ID: {pipeline_id}
    - Failing Commit SHA: {commit_sha}
    
    Please examine the failed jobs, fetch the trace logs, fix the error, and create an automated Merge Request.
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
