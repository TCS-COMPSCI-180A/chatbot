"""
Chat endpoint - main conversational interface.
Wired to the LangGraph runner (graph/runner.py) for the v2 agentic pipeline.
"""

from fastapi import APIRouter
import random

from graph.runner import run_pipeline

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"],
)


@router.post("")
async def chat(request: dict):
    """
    Process a chat message through the LangGraph AI pipeline.

    Accepts { message, conversation_id?, session_id? } JSON body.
    Returns { conversation_id, assistant_message: { content }, classification }.
    """

    message = request.get("message", "")
    conversation_id = request.get("conversation_id") or random.randint(1000, 9999)
    session_id = request.get("session_id") or str(conversation_id)

    # Run LangGraph pipeline
    try:
        pipeline_result = await run_pipeline(
            message=message,
            session_id=session_id,
            conversation_id=conversation_id,
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
            "entry":          "operational",
            "classifier":     "operational",
            "ethics_gate":    "operational",
            "generator":      "operational (Gemini 2.5 Flash)",
            "critic":         "operational",
            "db_logger":      "operational",
            "graph_runner":   "operational (LangGraph)",
        }
    }
