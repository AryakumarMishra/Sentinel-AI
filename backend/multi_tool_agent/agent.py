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
from google.adk.tools.mcp_tool import MCPToolset
from mcp import StdioServerParameters

gitlab_mcp_server = StdioServerParameters(
    command='python',
    args=["-m", "tools.gitlab_mcp.server"],
    env={
        "GITLAB_PRIVATE_TOKEN": os.environ.get("GITLAB_PRIVATE_TOKEN")
    }
)

gitlab_tools = MCPToolset(
    connection_params=gitlab_mcp_server
)

sentinel_agent = Agent(
    name="sentinel_ai",
    model="gemini-2.5-flash-lite",
    description=(
        "Agent to assist and fix CI/CD or DevOps failures in deployments on GitLab."
    ),
    instruction=(
            """
            You are an autonomous CI/CD repair expert.
            Your goal is to fix failed pipelines on GitLab.
            
            Follow this strict operational loop:
            1. Call 'get_failed_jobs' using the provided pipeline context parameters.
            2. Identify the broken Job ID and call 'get_pipeline_logs' to pull the trace.
            3. Parse the log error trace to discover the file path causing the runtime failure.
            4. Run 'read_repository_file' to study the target code lines that broke.
            5. Reason about the solution and generate fixed file string blocks.
            6. Create a new branch via 'create_branch' (e.g., 'fix/pipeline-{id}').
            7. Push your code update using 'commit_file_change' targeting your newly isolated branch.
            8. Open a Merge Request using 'create_merge_request' so developers can review your automated solution.
            """
    ),
    tools=[gitlab_tools],
)