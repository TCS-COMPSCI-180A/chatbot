"""
Chat endpoint - main conversational interface.
PLACEHOLDER — full implementation depends on orchestrator (Issue #11).

Once orchestrator.run_pipeline() is implemented, this endpoint should:
  1. Get or create a conversation
  2. Store the user message
  3. Call run_pipeline(message, db, conversation_id, message_id)
  4. Store and return the assistant response
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"],
)


@router.post("")
async def chat(request: dict):
    """TODO: Wire to orchestrator.run_pipeline() once Issue #11 is complete."""
    return {
        "message": "Chat endpoint not yet implemented — orchestrator pending (Issue #11)",
        "echo": request.get("message", ""),
    }


@router.get("/health")
async def chat_health():
    """Health check for the chat service."""
    return {
        "status": "ok",
        "service": "chat",
        "pipeline_status": "partial — classifier/strategy/generator done, orchestrator pending",
    }
