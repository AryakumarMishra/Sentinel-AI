import json
import re
import httpx
import asyncio
from .config.settings import settings


HEALING_SEMAPHORE = asyncio.Semaphore(1) # Only 1 healing session at a time

def parse_fix_json(text: str) -> dict | None:
    "Try 3 strategies to extract JSON from Gemini's response"
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r'\{\s*"file_path"\s*:', text, re.DOTALL)
    if match:
        start = match.start()
        depth = 0
        in_string = False
        escaped = False
        for i, ch in enumerate(text[start:]):
            if escaped:
                escaped = False
                continue
            if ch == '\\':
                escaped = True
                continue
            if ch == '"' and not escaped:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        candidate = text[start:start + i + 1]
                        return json.loads(candidate)
                    except (json.JSONDecodeError, ValueError):
                        return None
    
    return None


async def verify_file_exists(project_path: str, file_path: str, ref: str) -> bool:
    """Hit GitLab API to confirm file_path exists in the repo."""
    encoded = file_path.replace("/", "%2F")
    url = f"{settings.GITLAB_BASE_URL}/projects/{project_path}/repository/files/{encoded}/raw?ref={ref}"
    headers = {"PRIVATE-TOKEN": settings.GITLAB_PRIVATE_TOKEN}
    
    async with httpx.AsyncClient() as client:
        response =await client.get(url, headers=headers)
        
    return response.status_code == 200