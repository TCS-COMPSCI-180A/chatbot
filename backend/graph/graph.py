"""
LangGraph StateGraph — Banking Ethical Persuasion Pipeline.

Node order follows Banking_Assistant_Diagram (diagram takes precedence over
updated_design.md where they conflict):

  entry → classifier → ethics_gate → [routing] → generator → critic
       → [routing] → db_logger → END

Key difference from updated_design.md v2:
  - Classifier runs BEFORE Ethics Gate (diagram ordering)
  - No separate Strategy Agent node; strategy selection is inside generator_node
  - Parallel fanout (classifier + doc_analysis) is a stub for future Member 3 work;
    sequential execution is used for now per the diagram's simpler flow

Stub nodes registered for future implementation by other members:
  - document_ingestion_node  (Member 3)
  - document_analysis_node   (Member 3)
"""

import logging
from langgraph.graph import StateGraph, END

from graph.state import BankingPipelineState
from graph.routing import route_after_gate, route_after_critic

logger = logging.getLogger(__name__)


# =============================================================================
# Node: Entry
# =============================================================================
def entry_node(state: BankingPipelineState) -> dict:
    """
    Initialize derived state fields from raw inputs.
    Sets has_document and default counters; passes through everything else.
    """
    has_doc = bool(state.get("document_bytes"))
    return {
        "has_document": has_doc,
        "rewrite_count": 0,
        "debug_trace": {},
    }


# =============================================================================
# Node: Document Ingestion (stub — Member 3)
# =============================================================================
def document_ingestion_node(state: BankingPipelineState) -> dict:
    """
    Stub: parse, classify, extract figures, and embed a document upload.
    Skipped when has_document is False.
    Real implementation: Member 3 (backend/document/ingestion.py).
    """
    if not state.get("has_document"):
        return {}

    logger.info("[document_ingestion] Stub — no document processing yet")
    return {
        "document_text": None,
        "document_type": None,
        "document_figures": None,
        "document_doc_id": None,
    }


# =============================================================================
# Node: Classifier Agent
# =============================================================================
def classifier_node(state: BankingPipelineState) -> dict:
    """
    Classify the user message for emotion, intent, and situation.

    Currently wraps the DeBERTa zero-shot classifier (pipeline/classifier.py).
    Upgrade path: replace with LLM ReAct agent that calls get_conversation_history
    tool for multi-turn context awareness (Member 2's enhancement).
    """
    from pipeline import classifier as clf_module

    try:
        result = clf_module.classify(state["message"])
        logger.info(
            "[classifier] emotion=%s intent=%s situation=%s",
            result["emotion"], result["intent"], result["situation"],
        )
        return {
            "emotion": result["emotion"],
            "intent": result["intent"],
            "situation": result["situation"],
        }
    except Exception as exc:
        logger.error("[classifier] Failed: %s", exc, exc_info=True)
        return {
            "emotion": "neutral_or_calm",
            "intent": "general_banking_inquiry",
            "situation": "neutral_for_business",
        }


# =============================================================================
# Node: Ethics State Agent
# =============================================================================
def ethics_gate_node(state: BankingPipelineState) -> dict:
    """
    Evaluate the message through the deterministic Ethics Gate.

    Layer 1: Hard keyword rules (instant, 100 % recall).
    Layer 2: DeBERTa v3 zero-shot SLM.
    Layer 3 (future): document-type awareness (foreclosure_notice → BLOCKED).

    When BLOCKED, sets final_response to a compassionate canned reply so the
    generator is bypassed entirely (per diagram's BLOCKED → db_logger path).
    """
    from pipeline import ethics_gate
    from pipeline.blocked_responses import get_blocked_response

    doc_type = state.get("document_type")
    message = state["message"]

    # Layer 3: document-type hard block (Member 2 integration point)
    if doc_type in ("foreclosure_notice", "bankruptcy_filing"):
        logger.info("[ethics_gate] BLOCKED by document type: %s", doc_type)
        gate_result = {
            "decision": "BLOCKED",
            "reason": f"document_type:{doc_type}",
            "confidence": 1.0,
            "layer": "document_type",
            "raw": None,
        }
        return {
            "gate_decision": "BLOCKED",
            "gate_reason": gate_result["reason"],
            "gate_confidence": 1.0,
            "final_response": get_blocked_response(gate_result),
        }

    result = ethics_gate.evaluate(message)
    logger.info(
        "[ethics_gate] decision=%s reason=%s confidence=%.2f",
        result["decision"], result["reason"], result["confidence"],
    )

    updates = {
        "gate_decision": result["decision"],
        "gate_reason": result["reason"],
        "gate_confidence": result["confidence"],
    }

    if result["decision"] == "BLOCKED":
        updates["final_response"] = get_blocked_response(result)

    return updates


# =============================================================================
# Node: Document Analysis (stub — Member 3)
# =============================================================================
def document_analysis_node(state: BankingPipelineState) -> dict:
    """
    Stub: retrieve relevant chunks and produce grounded document_insights.
    Only runs when has_document is True and gate == APPROVED.
    Real implementation: Member 3 (backend/agents/document_analysis_agent.py).
    """
    if not state.get("has_document"):
        return {}

    logger.info("[document_analysis] Stub — no RAG yet")
    return {"document_insights": []}


# =============================================================================
# Node: Generator Agent
# =============================================================================
def generator_node(state: BankingPipelineState) -> dict:
    """
    Select a strategy and generate the response draft.

    Strategy selection priority (Section 5, Node 5 of updated_design.md):
      1. Gate BLOCKED/AMBIGUOUS → blocked or ambiguous strategy
      2. Compliance overrides (fraud, close_account, loan_modification)
      3. Document-grounded path (stub — has_document + advice intent)
      4. Emotion-first selection
      5. Default: neutral/informational

    A rewrite is detected when response_draft is already set (prior generation
    exists). rewrite_count is incremented HERE on rewrites so that routing can
    enforce the max-1-rewrite policy without critic needing to mutate the counter.
    """
    from pipeline import strategy as strat_module, generator as gen_module

    gate_decision = state.get("gate_decision") or "APPROVED"
    is_rewrite = state.get("response_draft") is not None
    current_rewrite_count = state.get("rewrite_count") or 0
    new_rewrite_count = current_rewrite_count + 1 if is_rewrite else current_rewrite_count

    gate = {
        "decision": gate_decision,
        "reason": state.get("gate_reason") or "",
        "confidence": state.get("gate_confidence") or 1.0,
    }

    classification = None
    if gate_decision == "APPROVED":
        classification = {
            "emotion": state.get("emotion") or "neutral_or_calm",
            "emotion_confidence": 1.0,
            "intent": state.get("intent") or "general_banking_inquiry",
            "intent_confidence": 1.0,
            "situation": state.get("situation") or "neutral_for_business",
            "situation_confidence": 1.0,
        }

    strategy_path = strat_module.select_strategy(gate, classification)
    strategy_config = strat_module.load_strategy(strategy_path)

    logger.info("[generator] strategy=%s is_rewrite=%s", strategy_path, is_rewrite)

    response = gen_module.generate(
        message=state["message"],
        classification=classification,
        strategy_config=strategy_config,
        rewrite=is_rewrite,
    )

    return {
        "strategy_path":  strategy_path,
        "strategy_config": strategy_config,
        "constraints":    strategy_config.get("prohibited", []),
        "response_draft": response,
        "rewrite_count":  new_rewrite_count,
    }


# =============================================================================
# Node: Critic Agent
# =============================================================================
def critic_node(state: BankingPipelineState) -> dict:
    """
    Score the response draft for ethical compliance (0–10).

    Increments rewrite_count on failure so route_after_critic can enforce
    the max-1-rewrite policy without needing to mutate state in routing.
    """
    from pipeline import critic as critic_module

    gate = {"decision": state.get("gate_decision") or "APPROVED"}
    result = critic_module.score_response(
        response=state.get("response_draft") or "",
        strategy=state.get("strategy_config") or {},
        gate=gate,
    )

    logger.info(
        "[critic] score=%.1f/10 violations=%d passed=%s",
        result["score"], len(result.get("violations") or []), result.get("passed"),
    )

    return {
        "critic_score":      result["score"],
        "critic_violations": result.get("violations"),
    }


# =============================================================================
# Node: DB Logger
# =============================================================================
def db_logger_node(state: BankingPipelineState) -> dict:
    """
    Finalize the response and write the full audit trace.

    Preference order for final_response:
      1. state["final_response"]  — set by ethics_gate for BLOCKED messages
      2. state["response_draft"]  — set by generator for APPROVED/AMBIGUOUS
      3. Fallback error string

    DB write is a stub: real implementation writes to the classifications table
    (Member 5 / DB integration week).
    """
    final = (
        state.get("final_response")
        or state.get("response_draft")
        or "I'm sorry, I was unable to process your request. Please contact support."
    )

    debug_trace = {
        "gate_decision":      state.get("gate_decision"),
        "gate_reason":        state.get("gate_reason"),
        "gate_confidence":    state.get("gate_confidence"),
        "emotion":            state.get("emotion"),
        "intent":             state.get("intent"),
        "situation":          state.get("situation"),
        "strategy_path":      state.get("strategy_path"),
        "critic_score":       state.get("critic_score"),
        "critic_violations":  state.get("critic_violations"),
        "rewrite_count":      state.get("rewrite_count"),
        "has_document":       state.get("has_document"),
        "document_type":      state.get("document_type"),
    }

    logger.info(
        "[db_logger] gate=%s strategy=%s critic=%.1f rewrites=%d",
        debug_trace["gate_decision"],
        debug_trace["strategy_path"] or "n/a",
        debug_trace["critic_score"] or 0.0,
        debug_trace["rewrite_count"] or 0,
    )

    return {
        "final_response": final,
        "debug_trace": debug_trace,
    }


# =============================================================================
# Graph construction
# =============================================================================
def create_graph():
    """
    Build and compile the LangGraph StateGraph.

    Flow (follows Banking_Assistant_Diagram):
      entry → classifier → ethics_gate
        → BLOCKED  : db_logger → END
        → APPROVED/AMBIGUOUS : generator → critic
            → score≥7 or rewrite≥1 : db_logger → END
            → score<7 and rewrite=0 : generator (rewrite) → critic → db_logger → END
    """
    builder = StateGraph(BankingPipelineState)

    # ── Register nodes ──────────────────────────────────────────────────────
    builder.add_node("entry",              entry_node)
    builder.add_node("classifier",         classifier_node)
    builder.add_node("ethics_gate",        ethics_gate_node)
    builder.add_node("generator",          generator_node)
    builder.add_node("critic",             critic_node)
    builder.add_node("db_logger",          db_logger_node)

    # Stub nodes (Member 3 implementations plug in here)
    builder.add_node("document_ingestion", document_ingestion_node)
    builder.add_node("document_analysis",  document_analysis_node)

    # ── Entry point ─────────────────────────────────────────────────────────
    builder.set_entry_point("entry")

    # ── Sequential edges ─────────────────────────────────────────────────────
    builder.add_edge("entry",      "classifier")
    builder.add_edge("classifier", "ethics_gate")

    # ── Conditional: after Ethics Gate ───────────────────────────────────────
    builder.add_conditional_edges(
        "ethics_gate",
        route_after_gate,
        {
            "generator":  "generator",
            "db_logger":  "db_logger",
        },
    )

    # ── Generator → Critic (always) ──────────────────────────────────────────
    builder.add_edge("generator", "critic")

    # ── Conditional: after Critic (rewrite loop or finalize) ─────────────────
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "generator":  "generator",   # one rewrite allowed
            "db_logger":  "db_logger",
        },
    )

    builder.add_edge("db_logger", END)

    return builder.compile()


# ── Singleton compiled graph ────────────────────────────────────────────────
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = create_graph()
    return _graph
