import os
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from workflows.pipeline_recovery import PipelineRecoveryWorkflow
from agent import root_agent

routes_router = APIRouter()

class ManualTriggerRequest(BaseModel):
    project_path: str
    pipeline_id: int
    commit_sha: str = "main"


def run_background_agent_job(recovery_id: str, project_path: str, pipeline_id: int, commit_sha: str):
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
        Handle execution flow for failure event:
        Project Path: {project_path}
        Pipeline ID: {pipeline_id}
        Commit Target Reference: {commit_sha}
        
        Steps:
        1. Call get_failed_jobs.
        2. Get trace logs via get_pipeline_logs.
        3. Read the relevant target breaking file with read_repository_file.
        4. Spin up a separate branch via create_branch.
        5. Push corrected fixes using commit_file_change.
        6. Open a pull request through create_merge_request.
        """
        
        agent_response = root_agent.run(prompt)
        tracker.log_step("COMPLETED", "SUCCESS", f"Execution complete. Agent Note: {agent_response.text[:200]}")
        
    except Exception as e:
        tracker.log_step("CRASHED", "FAILED", f"Error encountered during runtime orchestration: {str(e)}")


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
    tracker = PipelineRecoveryWorkflow(payload.project_path, payload.project_path, payload.commit_sha)
    
    # Offloading to async processing threads to avoid API lock-ups
    background_tasks.add_task(
        run_background_agent_job,
        recovery_id=tracker.recovery_id,
        project_path=payload.project_path,
        pipeline_id=payload.pipeline_id,
        commit_sha=payload.commit_sha
    )
    return {"status": "enqueued", "recovery_id": tracker.recovery_id}
