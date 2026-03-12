"""
Chat endpoint - main conversational interface.
Wired to orchestrator for full AI pipeline integration (demo version without database).
"""

from fastapi import APIRouter
import random

from backend.pipeline import orchestrator

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"],
)


@router.post("")
async def chat(request: dict):
    """
    Process a chat message through the AI pipeline.

    Simple demo version - calls orchestrator, returns response to frontend.
    """

    message = request.get("message", "")
    conversation_id = request.get("conversation_id") or random.randint(1000, 9999)

    # Run AI pipeline
    try:
        pipeline_result = await orchestrator.run_pipeline(
            message=message,
            conversation_id=conversation_id
        )

        response_text = pipeline_result["response"]
        debug_info = pipeline_result.get("debug", {})

    except Exception as e:
        # Graceful fallback on pipeline error
        response_text = f"I apologize, but I'm having trouble processing your request. Error: {str(e)}"
        debug_info = {"error": str(e), "gate_decision": "ERROR"}

    # Return in format frontend expects
    return {
        "conversation_id": conversation_id,
        "assistant_message": {
            "content": response_text
        },
        "classification": debug_info
    }


@router.get("/health")
async def chat_health():
    """Health check for the chat service."""
    return {
        "status": "ok",
        "service": "chat",
        "pipeline_status": "fully_operational",
        "components": {
            "ethics_gate": "operational",
            "classifier": "operational",
            "strategy": "operational",
            "generator": "operational (Gemini 2.5 Flash)",
            "critic": "operational",
            "orchestrator": "operational"
        }
    }
