"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from backend.models import ConversationStatus, MessageRole, SituationType, GateDecision


# ============================================================================
# Message Schemas
# ============================================================================

class MessageBase(BaseModel):
    """Base message schema"""
    content: str = Field(..., min_length=1, description="Message content")
    role: MessageRole = Field(..., description="Message role (user/assistant/system)")


class MessageCreate(MessageBase):
    """Schema for creating a new message"""
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class MessageResponse(MessageBase):
    """Schema for message response"""
    id: int
    conversation_id: int
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Conversation Schemas
# ============================================================================

class ConversationBase(BaseModel):
    """Base conversation schema"""
    user_id: Optional[str] = Field(None, description="Optional user identifier")


class ConversationCreate(ConversationBase):
    """Schema for creating a new conversation"""
    pass


class ConversationResponse(ConversationBase):
    """Schema for conversation response"""
    id: int
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    context_data: Optional[Dict[str, Any]] = None
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(ConversationBase):
    """Schema for conversation list response (without messages)"""
    id: int
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Chat Schemas
# ============================================================================

class ChatRequest(BaseModel):
    """Schema for chat request"""
    message: str = Field(..., min_length=1, max_length=5000, description="User message")
    conversation_id: Optional[int] = Field(None, description="Existing conversation ID (creates new if not provided)")
    user_id: Optional[str] = Field(None, description="Optional user identifier")


class ChatResponse(BaseModel):
    """Schema for chat response"""
    conversation_id: int
    user_message: MessageResponse
    assistant_message: MessageResponse
    classification: Optional[Dict[str, Any]] = Field(None, description="Classification data if available")


# ============================================================================
# Classification Schemas
# ============================================================================

class ClassificationResponse(BaseModel):
    """Schema for classification response"""
    id: int
    conversation_id: int
    message_id: Optional[int]
    situation_type: Optional[SituationType]
    gate_decision: Optional[GateDecision]
    intent: Optional[str]
    emotion: Optional[str]
    vulnerability_level: Optional[str]
    business_event_type: Optional[str]
    selected_strategy: Optional[str]
    confidence_scores: Optional[Dict[str, Any]]
    created_at: datetime
    classifier_version: Optional[str]

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Utility Schemas
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Schema for health check response"""
    status: str
    database: str
    environment: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Schema for error response"""
    error: str
    detail: Optional[str] = None
    status_code: int
