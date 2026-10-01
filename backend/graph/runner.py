"""
run_pipeline() — drop-in replacement for pipeline/orchestrator.py.

Accepts the same arguments as the old orchestrator and returns the same
{ "response": str, "debug": dict } shape so chat.py needs only a one-line
import change.
"""

import asyncio
import logging
from typing import Optional

from graph.graph import get_graph
from graph.state import BankingPipelineState

logger = logging.getLogger(__name__)


async def run_pipeline(
    message: str,
    session_id: str = "default",
    conversation_id: Optional[int] = None,
    document_bytes: Optional[bytes] = None,
) -> dict:
    """
    Run the full LangGraph pipeline for a single user message.

    Parameters
    ----------
    message        : raw user text
    session_id     : identifies the conversation session (used for history lookup)
    conversation_id: legacy numeric ID kept for backward compat with chat.py
    document_bytes : raw file upload bytes (None if no document)

    Returns
    -------
    dict
        response : str  — final text to show the user
        debug    : dict — full pipeline audit trace
    """
    graph = get_graph()

    initial_state: BankingPipelineState = {
        # Input
        "message":          message,
        "session_id":       session_id or str(conversation_id or "default"),
        "document_bytes":   document_bytes,
        "conversation_history": [],  # Will be populated by entry_node

        # Document (initialised by entry_node / document_ingestion_node)
        "has_document":       False,
        "document_text":      None,
        "document_type":      None,
        "document_figures":   None,
        "document_doc_id":    None,
        "document_insights":  None,
        "document_reused_from_session": False,

        # Classifier
        "emotion":                 None,
        "intent":                  None,
        "situation":               None,
        "classification_reasoning": None,
        "should_persuade":         None,

        # Ethics gate
        "gate_decision":   None,
        "gate_reason":     None,
        "gate_confidence": None,

        # Strategy
        "strategy_path":      None,
        "strategy_config":    None,
        "strategy_reasoning": None,

        # Generator
        "response_draft":  None,
        "retrieved_docs":  None,
        "constraints":     None,

        # Critic
        "critic_score":       None,
        "critic_violations":  None,
        "critic_reasoning":   None,
        "critic_suggestions": None,
        "critic_feedback":    None,
        "rewrite_count":      0,

        # Output
        "final_response": None,
        "debug_trace":    {},
    }

    logger.info("[runner] Starting pipeline for message: %.60s…", message)

    loop = asyncio.get_event_loop()
    final_state = await loop.run_in_executor(None, graph.invoke, initial_state)

    logger.info(
        "[runner] Pipeline complete — gate=%s critic=%.1f",
        final_state.get("gate_decision"),
        final_state.get("critic_score") or 0.0,
    )

    return {
        "response": final_state.get("final_response") or "",
        "debug":    final_state.get("debug_trace") or {},
    }
