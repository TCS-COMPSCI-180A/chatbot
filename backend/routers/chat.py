"""
Chat endpoint - main conversational interface
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Conversation, Message, MessageRole, ConversationStatus
from schemas import ChatRequest, ChatResponse, MessageResponse
from datetime import datetime

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"]
)


def generate_simple_response(user_message: str) -> str:
    """
    Placeholder response generator
    TODO: Replace with actual LLM + ethical gating pipeline
    """
    # Simple echo response for now
    return f"I received your message: '{user_message}'. (AI response pipeline coming soon)"


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Main chat endpoint

    - Accepts a user message
    - Creates or retrieves a conversation
    - Stores the user message
    - Generates an assistant response (placeholder for now)
    - Stores the assistant response
    - Returns both messages

    In the future, this will integrate:
    - Ethical gating (situation classification)
    - Context analysis (intent, emotion, vulnerability)
    - Strategy selection
    - RAG knowledge retrieval
    - LLM response generation
    - Critic validation
    """

    # Step 1: Get or create conversation
    if request.conversation_id:
        # Retrieve existing conversation
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.status == ConversationStatus.ACTIVE
        ).first()

        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {request.conversation_id} not found or not active"
            )
    else:
        # Create new conversation
        conversation = Conversation(
            user_id=request.user_id,
            status=ConversationStatus.ACTIVE
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Step 2: Store user message
    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=request.message,
        metadata={"timestamp": datetime.utcnow().isoformat()}
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # Step 3: Generate assistant response
    # TODO: This is where the full pipeline will go:
    # - Ethical gating & situation classification
    # - Context analysis (intent, emotion, vulnerability)
    # - Business event classification
    # - Strategy selection (if persuasion approved)
    # - RAG knowledge retrieval
    # - LLM response generation with constraints
    # - Critic validation & optional rewrite

    assistant_response_text = generate_simple_response(request.message)

    # Step 4: Store assistant message
    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=assistant_response_text,
        metadata={
            "timestamp": datetime.utcnow().isoformat(),
            "model": "placeholder",
            "pipeline_version": "0.1.0"
        }
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    # Step 5: Update conversation timestamp
    conversation.updated_at = datetime.utcnow()
    db.commit()

    # Step 6: Return response
    return ChatResponse(
        conversation_id=conversation.id,
        user_message=user_message,
        assistant_message=assistant_message,
        classification=None  # TODO: Add classification data when implemented
    )


@router.get("/health")
async def chat_health():
    """
    Health check for chat service
    """
    return {
        "status": "ok",
        "service": "chat",
        "pipeline_status": "placeholder - awaiting full implementation"
    }
