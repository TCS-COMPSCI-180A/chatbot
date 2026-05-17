"""
pipeline_state.py — Shared State, Types, and Utilities
backend/pipeline/pipeline_state.py

Single source of truth for the LangGraph pipeline.
Matches the architecture diagram collective state exactly.

FIELD OWNERSHIP (per diagram):
  entry_node       → session_id, user_id, current_query, chat_history, status="entry_complete"
  classifier_node  → route_decision, confidence, tools_used, reasoning, status="classified"
  ethics_gate_node → ethics_decision, risk_level, reasoning, tools_used, status="evaluated"
  generator_node   → generated_response, status="generated"
  critic_node      → critic_feedback, status="reviewed"
  db_logger_node   → final_response, status="logged"

  ALL nodes append → trace_log  (via Annotated operator.add)
  ALL nodes write  → metadata   (their own subkey only)
"""

from __future__ import annotations

import json
import operator
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict


# =========================================================
# LITERAL TYPES
# =========================================================
RouteDecision  = Literal["general", "domain", "ethical"]
EthicsDecision = Literal["pass", "blocked", "ambiguous"]
RouteSignal    = Literal["allow", "block", "human"]
RiskLevel      = Literal["low", "med", "high"]


# =========================================================
# MESSAGE SHAPE
# =========================================================
class Message(TypedDict):
    role: str       # "user" | "assistant"
    content: str


# =========================================================
# COLLECTIVE STATE  — matches diagram exactly
# =========================================================
class CollectiveState(TypedDict, total=False):

    # --- Entry node fields ---
    session_id:    str
    user_id:       Optional[str]
    current_query: str
    chat_history:  List[Message]

    # --- Classifier outputs ---
    route_decision: str          # general | domain | ethical
    confidence:     float
    tools_used:     List[str]
    reasoning:      str
    status:         str

    # --- Ethics Gate outputs ---
    ethics_decision: Optional[str]   # pass | blocked | ambiguous
    risk_level:      Optional[str]   # low | med | high

    # --- Routing signal (drives conditional edges out of ethics gate) ---
    route_signal: str                # allow | block | human

    # --- Generator outputs ---
    generated_response: Optional[str]

    # --- Critic outputs ---
    critic_feedback: Optional[Dict[str, Any]]

    # --- DB Logger outputs ---
    final_response: Optional[str]

    # --- Observability (append-only via operator.add) ---
    trace_log: Annotated[List[Dict[str, Any]], operator.add]
    metadata:  Dict[str, Any]


# =========================================================
# SHARED HELPERS
# =========================================================

def _safe_parse(text: str) -> dict:
    """Safe JSON parser — never raises. Falls back to brace-extraction."""
    if not text or not text.strip():
        return {}
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return {}
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return {}


def _extract_usage(response: Any) -> dict[str, int]:
    """Safely extracts token usage from a Gemini response object."""
    try:
        meta = response.usage_metadata
        return {
            "prompt":     getattr(meta, "prompt_token_count",     0) or 0,
            "completion": getattr(meta, "candidates_token_count", 0) or 0,
            "total":      getattr(meta, "total_token_count",       0) or 0,
        }
    except Exception:
        return {"prompt": 0, "completion": 0, "total": 0}
