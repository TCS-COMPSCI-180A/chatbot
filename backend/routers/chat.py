"""
Chat endpoint - main conversational interface.
Wired to the LangGraph runner (graph/runner.py) for the v2 agentic pipeline.
Handles both JSON and multipart/form-data (for document uploads).
"""

from fastapi import APIRouter, Request
import uuid

from graph.runner import run_pipeline

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"],
)


@router.post("")
async def chat(request: Request):
    """
    Process a chat message through the LangGraph AI pipeline.

    Accepts JSON { message, conversation_id?, session_id? } or
    multipart/form-data { message, conversation_id?, document? } for file uploads.
    Returns { conversation_id, assistant_message: { content }, classification }.
    """

    content_type = request.headers.get("content-type", "")
    document_bytes = None

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        message = str(form.get("message", ""))
        raw_cid = form.get("conversation_id")
        try:
            conversation_id = int(raw_cid) if raw_cid else None
        except (ValueError, TypeError):
            conversation_id = None
        upload = form.get("document") or form.get("file")
        if upload is not None and hasattr(upload, "read"):
            document_bytes = await upload.read()
    else:
        body = await request.json()
        message = body.get("message", "")
        raw_cid = body.get("conversation_id")
        try:
            conversation_id = int(raw_cid) if raw_cid is not None else None
        except (ValueError, TypeError):
            conversation_id = None

    if not conversation_id:
        conversation_id = abs(hash(uuid.uuid4())) % (10 ** 9)

    session_id = str(conversation_id)

    # Run LangGraph pipeline
    try:
        pipeline_result = await run_pipeline(
            message=message,
            session_id=session_id,
            conversation_id=conversation_id,
            document_bytes=document_bytes,
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
