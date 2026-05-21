import os
import json
import uuid
from datetime import datetime, timezone

STATE_DIR = "recovery_states"
os.makedirs(STATE_DIR, exist_ok=True)

class PipelineRecoveryWorkflow:
    def __init__(self, pipeline_id: int, project_name: str, commit_sha: str):
        self.recovery_id = str(uuid.uuid4())
        self.pipeline_id = pipeline_id
        self.project_name = project_name
        self.commit_sha = commit_sha
        self.start_time = datetime.now(timezone.utc).isoformat()
        self.status = "TRIGGERED" # TRIGGERED -> ANALYZING -> PATCHING -> MR_CREATED -> FAILED
        self.steps = []
        self.save_state()

    def log_step(self, step_name: str, status: str, details: str = ""):
        """Appends an event tracking record to the history timeline."""
        self.steps.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": step_name,
            "status": status,
            "details": details
        })
        # Set top-level status to match the latest milestone
        if status in ["IN_PROGRESS", "SUCCESS", "FAILED"]:
            self.status = step_name if status == "IN_PROGRESS" else f"{step_name}_{status}"
        self.save_state()

    def save_state(self):
        """Saves current instance variables to a local JSON tracking block."""
        file_path = os.path.join(STATE_DIR, f"{self.recovery_id}.json")
        with open(file_path, "w") as f:
            json.dump(self.__dict__, f, indent=4)

    @staticmethod
    def get_all_recoveries():
        """Reads all JSON logs to display a global tracking dashboard list."""
        records = []
        for file in os.listdir(STATE_DIR):
            if file.endswith(".json"):
                with open(os.path.join(STATE_DIR, file), "r") as f:
                    records.append(json.load(f))
        return records

    @staticmethod
    def get_recovery_by_id(recovery_id: str):
        """Fetches the state tracker file for details on a specific recovery."""
        file_path = os.path.join(STATE_DIR, f"{recovery_id}.json")
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return None
