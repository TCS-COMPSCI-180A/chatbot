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
# Helper: Retrieve Conversation History
# =============================================================================
def _get_conversation_history(session_id: str, limit: int = 5) -> list[dict]:
    """
    Retrieve last N messages from the database for context.

    Returns list of {role: str, content: str} dicts in chronological order.
    """
    if not session_id or session_id == "default":
        return []

    try:
        from backend.database import SessionLocal
        from backend.models import Conversation, Message
    except ImportError:
        from database import SessionLocal
        from models import Conversation, Message

    db = SessionLocal()
    try:
        # Find conversation by session_id (stored in user_id field)
        conversation = db.query(Conversation).filter(
            Conversation.user_id == session_id
        ).first()

        if not conversation:
            return []

        # Get last N messages in chronological order
        messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at.desc()).limit(limit).all()

        # Reverse to get chronological order (oldest first)
        history = [
            {"role": msg.role.value, "content": msg.content}
            for msg in reversed(messages)
        ]

        logger.info(f"[entry] Retrieved {len(history)} messages from conversation history")
        return history

    except Exception as e:
        logger.warning(f"[entry] Failed to retrieve conversation history: {e}")
        return []
    finally:
        db.close()


# =============================================================================
# Node: Entry
# =============================================================================
def entry_node(state: BankingPipelineState) -> dict:
    """
    Initialize derived state fields from raw inputs.
    Sets has_document, retrieves conversation history, and initializes counters.
    """
    has_doc = bool(state.get("document_bytes"))
    session_id = state.get("session_id", "default")

    # Retrieve conversation history for context-aware responses
    conversation_history = _get_conversation_history(session_id, limit=5)

    return {
        "has_document": has_doc,
        "conversation_history": conversation_history,
        "rewrite_count": 0,
        "debug_trace": {},
    }


# =============================================================================
# Node: Document Ingestion (stub — Member 3)
# =============================================================================
def document_ingestion_node(state: BankingPipelineState) -> dict:
    """
    Parse, classify, extract figures, and embed a document upload.
    Uses Member 3's document ingestion implementation.
    """
    if not state.get("has_document"):
        return {}

    from document import ingestion

    document_bytes = state.get("document_bytes")
    session_id = state.get("session_id", "default")

    try:
        # Parse PDF → text
        text = ingestion.parse_pdf_document(document_bytes)

        # Classify document type
        doc_type = ingestion.classify_banking_document(text)

        # Extract key figures (regex patterns)
        figures = ingestion.extract_banking_figures(text, doc_type)

        # Chunk + Embed → store in pgvector
        doc_id = ingestion.chunk_and_embed_document(text, session_id)

        logger.info(
            "[document_ingestion] Processed: type=%s figures=%d doc_id=%s",
            doc_type, len(figures), doc_id
        )

        return {
            "document_text": text,
            "document_type": doc_type,
            "document_figures": figures,
            "document_doc_id": doc_id,
        }

    except Exception as e:
        logger.error("[document_ingestion] Failed: %s", e, exc_info=True)
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
    Retrieve relevant chunks and produce grounded document_insights.
    Only runs when has_document is True and gate == APPROVED.
    Uses Member 3's document analysis implementation.
    """
    if not state.get("has_document"):
        return {}

    from agents import document_analysis_agent

    result = document_analysis_agent.run_document_analysis(state)

    logger.info(
        "[document_analysis] Generated %d insights",
        len(result.get("document_insights", []))
    )

    return result


# =============================================================================
# Node: Generator Agent
# =============================================================================
def generator_node(state: BankingPipelineState) -> dict:
    """
    Select a strategy and generate the response draft using Member 4's agents.

    Strategy selection priority (Section 5, Node 5 of updated_design.md):
      1. Gate BLOCKED/AMBIGUOUS → blocked or ambiguous strategy (or human handoff)
      2. Compliance overrides (fraud, close_account, loan_modification)
      3. Document-grounded path (has_document + advice intent)
      4. Emotion-first selection
      5. Default: neutral/informational

    A rewrite is detected when response_draft is already set (prior generation
    exists). rewrite_count is incremented HERE on rewrites so that routing can
    enforce the max-1-rewrite policy without critic needing to mutate the counter.
    """
    from agents import strategy_agent, generator_agent

    is_rewrite = state.get("response_draft") is not None
    current_rewrite_count = state.get("rewrite_count") or 0
    new_rewrite_count = current_rewrite_count + 1 if is_rewrite else current_rewrite_count

    # Step 1: Strategy selection (Member 4's LLM-based agent)
    strategy_result = strategy_agent.strategy_node(state)

    # Check if strategy agent wants human handoff (BLOCKED case)
    if strategy_result.get("human_handoff"):
        logger.info("[generator] Strategy agent triggered human handoff")
        return {
            "strategy_path": None,
            "strategy_config": None,
            "response_draft": "I understand this is a sensitive situation. Let me connect you with a specialist who can provide personalized assistance.",
            "rewrite_count": new_rewrite_count,
            "human_handoff": True,
            "handoff_reason": strategy_result.get("handoff_reason"),
        }

    # Step 2: Update state with strategy
    state_with_strategy = {**state, **strategy_result}

    # Step 3: Generate response (Member 4's LLM-based generator)
    generator_result = generator_agent.generator_node(state_with_strategy)

    logger.info(
        "[generator] strategy=%s is_rewrite=%s",
        strategy_result.get("strategy_path"),
        is_rewrite
    )

    return {
        "strategy_path":  strategy_result.get("strategy_path"),
        "strategy_config": strategy_result.get("strategy_config"),
        "strategy_reasoning": strategy_result.get("strategy_reasoning"),
        "constraints":    strategy_result.get("strategy_config", {}).get("prohibited", []),
        "response_draft": generator_result.get("response_draft"),
        "rewrite_count":  new_rewrite_count,
    }


# =============================================================================
# Node: Critic Agent
# =============================================================================
def critic_node(state: BankingPipelineState) -> dict:
    """
    Score the response draft for ethical compliance (0–10) using Member 4's LLM critic.

    Uses chain-of-thought reasoning to check:
    - Coercive language, fear tactics
    - Persuasion in BLOCKED contexts
    - Document-specific violations (fabricated figures, missing citations)
    - YAML prohibited phrase violations
    """
    from agents import critic_agent

    result = critic_agent.critic_node(state)

    logger.info(
        "[critic] score=%.1f/10 violations=%d",
        result.get("critic_score", 0.0),
        len(result.get("critic_violations", [])),
    )

    return {
        "critic_score":      result.get("critic_score", 0.0),
        "critic_violations": result.get("critic_violations", []),
        "critic_reasoning":  result.get("critic_reasoning", ""),
    }


# =============================================================================
# Node: DB Logger
# =============================================================================
def db_logger_node(state: BankingPipelineState) -> dict:
    """
    Finalize the response and write the full audit trace to database.

    Preference order for final_response:
      1. state["final_response"]  — set by ethics_gate for BLOCKED messages
      2. state["response_draft"]  — set by generator for APPROVED/AMBIGUOUS
      3. Fallback error string

    Saves to classifications table for full auditability.
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

    # ═══════════════════════════════════════════════════════════════
    # SAVE TO DATABASE (for audit trail and future analysis)
    # ═══════════════════════════════════════════════════════════════
    try:
        from backend.database import SessionLocal
        from backend.models import Conversation, Message, Classification, MessageRole, GateDecision
    except ImportError:
        from database import SessionLocal
        from models import Conversation, Message, Classification, MessageRole, GateDecision

    session_id = state.get("session_id", "default")
    message_text = state.get("message", "")

    db = SessionLocal()
    try:
        # Get or create conversation
        conversation = db.query(Conversation).filter(
            Conversation.user_id == session_id
        ).first()

        if not conversation:
            conversation = Conversation(user_id=session_id)
            db.add(conversation)
            db.flush()

        # Save user message
        user_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=message_text
        )
        db.add(user_msg)
        db.flush()

        # Save assistant response
        assistant_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=final
        )
        db.add(assistant_msg)
        db.flush()

        # Save classification/audit trail
        gate_dec = state.get("gate_decision")
        gate_decision_enum = None
        if gate_dec:
            try:
                gate_decision_enum = GateDecision(gate_dec.lower())
            except (ValueError, AttributeError):
                logger.warning(f"Invalid gate_decision: {gate_dec}")

        classification = Classification(
            conversation_id=conversation.id,
            message_id=user_msg.id,
            situation_type=None,  # Can map from state if needed
            gate_decision=gate_decision_enum,
            intent=state.get("intent"),
            emotion=state.get("emotion"),
            selected_strategy=state.get("strategy_path"),
            critic_score=state.get("critic_score"),
            critic_violations=state.get("critic_violations"),
            document_type=state.get("document_type"),
            document_doc_id=state.get("document_doc_id"),
            raw_classification_data=debug_trace
        )
        db.add(classification)
        db.commit()

        logger.info("[db_logger] Saved to database: conv_id=%d msg_id=%d", conversation.id, user_msg.id)
    except Exception as e:
        logger.error("[db_logger] Database save failed: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()

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

    Flow (with document analysis integrated):
      entry → document_ingestion → classifier → ethics_gate
        → BLOCKED  : db_logger → END
        → APPROVED/AMBIGUOUS : document_analysis → generator → critic
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
    builder.add_edge("entry",              "document_ingestion")
    builder.add_edge("document_ingestion", "classifier")
    builder.add_edge("classifier",         "ethics_gate")

    # ── Conditional: after Ethics Gate ───────────────────────────────────────
    builder.add_conditional_edges(
        "ethics_gate",
        route_after_gate,
        {
            "document_analysis":  "document_analysis",  # APPROVED path
            "db_logger":  "db_logger",                   # BLOCKED path
        },
    )

    # ── Document Analysis → Generator (always) ────────────────────────────────
    builder.add_edge("document_analysis", "generator")

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
