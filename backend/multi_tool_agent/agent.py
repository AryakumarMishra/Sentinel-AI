# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import MCPToolset, StdioConnectionParams
from mcp import StdioServerParameters
from dotenv import load_dotenv

load_dotenv(override=True)

server_params = StdioServerParameters(
    command='python',
    args=["-m", "multi_tool_agent.gitlab_mcp.server"],
    env={
        "GITLAB_PRIVATE_TOKEN": os.environ.get("GITLAB_PRIVATE_TOKEN", ""),
        "GITLAB_BASE_URL": os.environ.get("GITLAB_BASE_URL", "https://gitlab.com/api/v4")
    }
)

gitlab_mcp_server = StdioConnectionParams(
    server_params = server_params,
    timeout=30.0
)

gitlab_tools = MCPToolset(
    connection_params=gitlab_mcp_server
)

root_agent = Agent(
    name="sentinel_ai",
    model="gemini-3.1-flash-lite",
    description=(
        "Agent to assist and fix CI/CD or DevOps failures in deployments on GitLab."
    ),
    instruction=(
            """
            You are an autonomous CI/CD repair expert.
            Your goal is to fix failed pipelines on GitLab.
            
            Follow this strict operational loop:
            1. Call 'get_failed_jobs' with the project_path and pipeline_id to find failed jobs.
            2. From the result, extract the failed Job ID and call 'get_pipeline_logs' with project_path and that job_id.
            3. Parse the log output to identify the exact source file path that caused the failure.
            4. Call 'read_repository_files' with project_path, that exact file_path, and ref set to the commit_sha or branch to read the broken file.
            5. Analyze the issue and generate the corrected file content.
            6. Call 'create_branch' with project_path, a branch name like 'fix/pipeline-<ID>', and ref='main'.
            7. Call 'commit_file_change' with project_path, the branch_name, the file_path, a descriptive commit_message, and the corrected file_content.
            8. Call 'create_merge_request' with project_path, the source_branch, a title, and a description.
            """
    ),
    tools=[gitlab_tools],
)