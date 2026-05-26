import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..agent import root_agent


APP_NAME = "pipeline_healer"

# Shared singleton session service
session_service = InMemorySessionService()

# Shared singleton runner
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service
)


async def execute_agent(
    prompt: str,
    session_id: str,
    user_id: str = "system_orchestrator"
) -> str:
    """
    Executes an ADK agent session and streams back the final text response.
    """

    await session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id
    )

    user_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)]
    )

    full_response = ""

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message
    ):
        if hasattr(event, "text") and event.text:
            full_response += event.text

    return full_response