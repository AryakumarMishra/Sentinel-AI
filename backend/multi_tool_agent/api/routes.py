import os
import json
import re
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from ..workflows.pipeline_recovery import PipelineRecoveryWorkflow
from ..agent import root_agent

routes_router = APIRouter()

class ManualTriggerRequest(BaseModel):
    project_path: str
    pipeline_id: int
    commit_sha: str = "main"

class ApprovalDecisionRequest(BaseModel):
    approve: bool



async def run_background_agent_job(recovery_id: str, project_path: str, pipeline_id: int, commit_sha: str):
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
        Analyze this failure event:
        Project Path: {project_path}
        Pipeline ID: {pipeline_id}
        
        Instructions:
        1. Call get_failed_jobs and get_pipeline_logs.
        2. Identify the broken file path, read it with read_repository_file.
        3. Formulate a precise code fix correction.
        4. STOP HERE. Do not call any modification tools (do not branch, commit or open MRs).
        
        Output your recommendation strictly as a JSON object inside markdown backticks:
        ```json
        {{
            "file_path": "path/to/broken_file.py",
            "explanation": "Brief explanation of what broke",
            "content": "The exact full replacement text content for the file"
        }}
        ```
        """
        
        agent_response = await root_agent.execute(prompt)
        tracker.log_step("COMPLETED", "SUCCESS", f"Execution complete. Agent Note: {agent_response.text[:200]}")

        # Using regex to extract the JSON payload returned by Gemini
        match = re.search(r"```json\s*(.*?)\s*```", agent_response.text, re.DOTALL)
        if match:
            fix_json = json.loads(match.group(1))
            
            # Saving the proposed patch to state storage
            file_path = os.path.join("recovery_states", f"{recovery_id}.json")
            state_data = PipelineRecoveryWorkflow.get_recovery_by_id(recovery_id)
            state_data['proposed_fix'] = fix_json
            state_data['status'] = "AWAITING_APPROVAL" # Pauses loop
            
            with open(file_path, "w") as f:
                json.dump(state_data, f, indent=4)
                
            tracker.log_step("AWAITING_APPROVAL", "SUCCESS", "AI patch generated. Holding for engineer verification review.")
        else:
            tracker.log_step("CRASHED", "FAILED", "Failed to parse structured JSON repair patch matrix from agent response.")
            
        
    except Exception as e:
        tracker.log_step("CRASHED", "FAILED", f"Error encountered during runtime orchestration: {str(e)}")


async def complete_healing_after_approval(recovery_id: str):
    """Executes the final GitLab deployment after Human gives approval"""
    # Reloading workflow state to track update progress
    tracker_data = PipelineRecoveryWorkflow.get_recovery_by_id(recovery_id)
    if not tracker_data:
        return
        
    # Rehydrate our state tracker class
    tracker = PipelineRecoveryWorkflow(tracker_data['pipeline_id'], tracker_data['project_name'], tracker_data['commit_sha'])
    tracker.recovery_id = recovery_id
    tracker.proposed_fix = tracker_data['proposed_fix']
    
    try:
        tracker.log_step("REMEDIATION", "IN_PROGRESS", "Human approved! Pushing fix branch and creating MR...")
        
        fix_info = tracker.proposed_fix
        project_path = tracker.project_name
        
        # Explicit prompt telling Gemini to skip analysis and strictly execute the approved deployment tools
        execution_prompt = f"""
        The human supervisor has APPROVED your proposed fix code. Execute your deployment tools right now.
        
        Context:
        - Project Path: {project_path}
        - File to change: {fix_info['file_path']}
        - Approved Content: {fix_info['content']}
        
        Steps:
        1. Create an isolation branch via create_branch.
        2. Push the approved text change using commit_file_change.
        3. Open a pull request through create_merge_request.
        """
        
        agent_response = await root_agent.execute(execution_prompt)
        tracker.log_step("COMPLETED", "SUCCESS", "Merge request successfully dispatched to GitLab!")
        
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
