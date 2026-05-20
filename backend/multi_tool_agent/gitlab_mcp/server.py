import os
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# Initializing the MCP server
mcp = FastMCP("Sentinel GitLab Healer")

# Configuring the GitLab Connections
GL_TOKEN = os.environ.get("GITLAB_PRIVATE_TOKEN")
GL_BASE = "https://gitlab.com"
HEADERS = {"PRIVATE-TOKEN": GL_TOKEN}


# MCP Tools to interact with GitLab
@mcp.tool()
async def get_failed_jobs(project_path: str, pipeline_id: int) -> str:
    """
    Retrieves a list of failed jobs for a specific pipeline ID.
    Use this first to discover which specific job_id has the broken logs.
    Args:
        project_path: The URL-encoded path of the project (e.g., 'user%2Frepo') or ID.
        pipeline_id: The numeric ID of the pipeline that failed.
    """
    url = f"{GL_BASE}/projects/{project_path}/pipelines/{pipeline_id}/jobs"
    params = {"scope": "failed"} # Trying to filter the failed jobs directly via API scope parameter
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            return f"Error fetching failed jobs: {response.status_code} - {response.text}"
            
        jobs = response.json()
        if not jobs:
            return "No failed jobs found for this pipeline."
            
        result = []
        for job in jobs:
            result.append(f"Job Name: {job.get('name')} | Job ID: {job.get('id')} | Stage: {job.get('stage')}")
        return "\n".join(result)


@mcp.tool()
async def get_pipeline_logs(project_path: str, job_id: int) -> str:
    """
    Fetches the trace logs for a specific failed job in GitLab.
    Args:
        project_path: The URL-encoded path of the project (e.g., 'user%2Frepo') or ID.
        job_id: The numeric ID of the job.
    """
    url = f"{GL_BASE}/projects/{project_path}/jobs/{job_id}/trace"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS)
        
        if response.status_code != 200:
            return f"Error: {response.status_code} - {response.text}"
        return response.text[-5000:]  # Returning the trailing logs as errors would appear at the very end


@mcp.tool()
async def get_recent_commits(project_path: str, ref_name: str = "main", max_count: int = 5) -> str:
    """
    Retrieves recent commits for a project to help find who or what broke the build.
    Args:
        project_path: The URL-encoded path of the project (e.g., 'user%2Frepo') or ID.
        ref_name: The branch name or tag name to fetch commits from (defaults to 'main').
        max_count: The maximum number of recent commits to return (defaults to 5).
    """
    url = f"{GL_BASE}/projects/{project_path}/repository/commits"
    params = {"ref_name": ref_name, "per_page":max_count}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            return f"Error: {response.status_code} - {response.text}"
        
        commits = response.json()
        result = []
        for c in commits:
            result.append(f"SHA: {c.get('id')[:8]} | Title: {c.get('title')} | Author: {c.get('author_name')}")
        return "\n".join(result)      


@mcp.tool()
async def create_branch(project_path: str, branch_name: str, ref: str = "main") -> str:
    """
    Creates a new Git branch in the repository. 
    Use this to create an isolation branch (e.g., 'fix/pipeline-error') before pushing fixes.
    Args:
        project_path: The URL-encoded path of the project (e.g., 'user%2Frepo') or ID.
        branch_name: The name of the new branch you want to create.
        ref: The branch or commit SHA to branch off from (defaults to 'main').
    """
    url = f"{GL_BASE}/projects/{project_path}/repository/branches"
    payload = {
        "branch": branch_name,
        "ref": ref
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=HEADERS, json=payload)
        
        if response.status_code == 201:
            return f"Success: Branch '{branch_name}' created off reference '{ref}'."
        return f"Error creating branch: {response.status_code} - {response.text}"


@mcp.tool()
async def create_merge_request(project_path: str, source_branch: str, title: str, description: str) -> str:
    """Creates a merge request with the fix."""
    url = f"{GL_BASE}/projects/{project_path}/merge_requests"
    payload = {
        "source_branch": source_branch,
        "target_branch": "main",
        "title": title,
        "description": description
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=HEADERS, json=payload)
        return str(resp.json())
    


if __name__ == "__main__":
    mcp.run()