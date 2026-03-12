"""
Conversation management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models import Conversation, Message, ConversationStatus
from backend.schemas import (
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse
)

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"]
)


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation: ConversationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new conversation
    """
    db_conversation = Conversation(
        user_id=conversation.user_id,
        status=ConversationStatus.ACTIVE
    )
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    return db_conversation


@router.get("", response_model=List[ConversationListResponse])
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    user_id: str = None,
    db: Session = Depends(get_db)
):
    """
    List conversations with pagination
    Optionally filter by user_id
    """
    query = db.query(Conversation)

    # Filter by user_id if provided
    if user_id:
        query = query.filter(Conversation.user_id == user_id)

    # Filter out deleted conversations
    query = query.filter(Conversation.status != ConversationStatus.DELETED)

    # Order by most recent first
    query = query.order_by(Conversation.updated_at.desc())

    # Apply pagination
    conversations = query.offset(skip).limit(limit).all()

    # Add message count to each conversation
    result = []
    for conv in conversations:
        conv_dict = {
            "id": conv.id,
            "user_id": conv.user_id,
            "status": conv.status,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "message_count": len(conv.messages)
        }
        result.append(conv_dict)

    return result


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific conversation with all messages
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.status != ConversationStatus.DELETED
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found"
        )

    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """
    Soft delete a conversation (marks as deleted, doesn't actually remove)
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found"
        )

    conversation.status = ConversationStatus.DELETED
    db.commit()

    return None


@router.patch("/{conversation_id}/archive", response_model=ConversationResponse)
async def archive_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """
    Archive a conversation
    """
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found"
        )

    conversation.status = ConversationStatus.ARCHIVED
    db.commit()
    db.refresh(conversation)

    return conversation
