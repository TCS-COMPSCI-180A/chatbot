"""
Chat endpoint - main conversational interface.

Handles conversation management and delegates all AI logic to the orchestrator.
Pipeline: Ethics Gate → Classifier → Strategy → Generator → Critic → DB Log
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Conversation, Message, MessageRole, ConversationStatus
from schemas import ChatRequest, ChatResponse, MessageResponse
from datetime import datetime

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"],
)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Main chat endpoint.

    1. Get or create a conversation
    2. Store the user message
    3. Run the full AI pipeline (ethics gate → classify → strategy → generate → critic)
    4. Store the assistant response
    5. Return both messages + classification debug data
    """
    # ── Step 1: Get or create conversation ───────────────────────────────────
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.status == ConversationStatus.ACTIVE,
        ).first()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {request.conversation_id} not found or not active",
            )
    else:
        conversation = Conversation(
            user_id=request.user_id,
            status=ConversationStatus.ACTIVE,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # ── Step 2: Store user message ────────────────────────────────────────────
    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=request.message,
        metadata={"timestamp": datetime.utcnow().isoformat()},
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # ── Step 3: Run the AI pipeline ───────────────────────────────────────────
    try:
        from pipeline.orchestrator import run_pipeline

        pipeline_result = run_pipeline(
            message=request.message,
            db=db,
            conversation_id=conversation.id,
            message_id=user_message.id,
        )
        assistant_response_text = pipeline_result["response"]
        debug_data = pipeline_result["debug"]
    except Exception as e:
        # Fail safe: return a neutral error response rather than crashing
        assistant_response_text = (
            "I'm sorry, I encountered an issue processing your request. "
            "Please try again or contact support if the problem persists."
        )
        debug_data = {"error": str(e), "pipeline_version": "error"}

    # ── Step 4: Store assistant message ──────────────────────────────────────
    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=assistant_response_text,
        metadata={
            "timestamp": datetime.utcnow().isoformat(),
            "model": "gpt-4o-mini",
            "pipeline_version": debug_data.get("pipeline_version", "1.0.0"),
            "gate_decision": debug_data.get("gate", {}).get("decision") if debug_data.get("gate") else None,
            "strategy": debug_data.get("strategy_path"),
        },
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    # ── Step 5: Update conversation timestamp ────────────────────────────────
    conversation.updated_at = datetime.utcnow()
    db.commit()

    # ── Step 6: Return response ───────────────────────────────────────────────
    return ChatResponse(
        conversation_id=conversation.id,
        user_message=user_message,
        assistant_message=assistant_message,
        classification=debug_data,
    )


@router.get("/health")
async def chat_health():
    """Health check for the chat service."""
    return {
        "status": "ok",
        "service": "chat",
        "pipeline_status": "active",
        "pipeline_version": "1.0.0",
    }
