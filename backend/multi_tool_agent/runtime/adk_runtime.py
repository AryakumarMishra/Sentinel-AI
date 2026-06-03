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
    turn_count = 0
    max_turns = 15

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message
    ):
        # Log non-standard events for debugging
        if not event.content or not event.content.parts:
            print(f"[ADK] Event with no content parts: author={event.author}, "
                  f"final={event.is_final_response()}, actions={event.actions}")
            continue

        for part in event.content.parts:
            if hasattr(part, 'text') and part.text:
                full_response += part.text
            if hasattr(part, 'function_call') and part.function_call:
                turn_count += 1
                print(f"[ADK] Tool call #{turn_count}: {part.function_call.name}")

        if turn_count >= max_turns:
            break

    if not full_response.strip():
        if turn_count > 0:
            print(f"[ADK] WARNING: Agent made {turn_count} tool calls but "
                  f"returned no text — response likely blocked by safety filters")
            full_response = '{"error": "Model response blocked by safety filters"}'
        else:
            print(f"[ADK] WARNING: Agent made no tool calls and no text output")

    return full_response