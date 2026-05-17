"""
SQLAlchemy database models
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON, Float, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base
from pgvector.sqlalchemy import Vector
import enum
import uuid


class ConversationStatus(str, enum.Enum):
    """Conversation status enum"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MessageRole(str, enum.Enum):
    """Message role enum"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SituationType(str, enum.Enum):
    """Situation classification types from PRD"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class GateDecision(str, enum.Enum):
    """Ethical gate decision types from PRD"""
    APPROVED = "approved"
    BLOCKED = "blocked"
    AMBIGUOUS = "ambiguous"
    HIGH_RISK = "high_risk"


class Conversation(Base):
    """
    Conversation model - represents a chat session with a user
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), index=True, nullable=True)  # Optional user identification
    status = Column(Enum(ConversationStatus), default=ConversationStatus.ACTIVE, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Context information (will be populated as conversation progresses)
    context_data = Column(JSON, nullable=True)  # Store user context, intent, emotion, etc.

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    classifications = relationship("Classification", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, status={self.status})>"


class Message(Base):
    """
    Message model - individual messages within a conversation
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Message content
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Additional data (e.g., model used, tokens, etc.)
    message_metadata = Column(JSON, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"


class Classification(Base):
    """
    Classification model - stores ethical gating and context classification results
    This supports the PRD's requirement for auditability and decision tracking
    """
    __tablename__ = "classifications"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=True, index=True)

    # Classification results from PRD
    situation_type = Column(Enum(SituationType), nullable=True)  # positive/neutral/negative
    gate_decision = Column(Enum(GateDecision), nullable=True)  # approved/blocked/ambiguous/high_risk

    # User context analysis
    intent = Column(String(255), nullable=True)
    emotion = Column(String(255), nullable=True)
    vulnerability_level = Column(String(50), nullable=True)  # low/medium/high

    # Business event classification
    business_event_type = Column(String(255), nullable=True)

    # Strategy selection (if persuasion approved)
    selected_strategy = Column(String(255), nullable=True)

    # Critic validation
    critic_score = Column(Float, nullable=True)  # 0-10 score from critic layer
    critic_violations = Column(JSON, nullable=True)  # List of detected violations

    # Confidence scores
    confidence_scores = Column(JSON, nullable=True)

    # Full classification data (for auditability)
    raw_classification_data = Column(JSON, nullable=True)

    # tracks which document (if any) was uploaded during this conversation
    document_type = Column(String(100), nullable=True)    # e.g. "bank_statement"
    document_doc_id = Column(String(36), nullable=True)   # links to document_chunks table

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    classifier_version = Column(String(50), nullable=True)  # Track which model version was used

    # Relationships
    conversation = relationship("Conversation", back_populates="classifications")

    def __repr__(self):
        return f"<Classification(id={self.id}, gate_decision={self.gate_decision}, situation_type={self.situation_type})>"


class DocumentChunk(Base):
    """Stores pgvector embeddings of uploaded document chunks for semantic retrieval."""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(36), nullable=False, index=True)     # groups all chunks from one upload
    session_id = Column(String(255), nullable=True, index=True)
    chunk_index = Column(Integer, nullable=True)                 # position within the document
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)              # 1536-dim vector from text-embedding-3-small

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<DocumentChunk(doc_id={self.doc_id}, chunk_index={self.chunk_index})>"
