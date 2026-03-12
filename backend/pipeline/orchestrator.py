"""
Orchestrator - Coordinates the full AI pipeline.

Pipeline order (NEVER change):
  1. Ethics Gate   → BLOCKED | APPROVED | AMBIGUOUS
  2. Classifier    → emotion, intent, situation (APPROVED only)
  3. Strategy      → select + load YAML
  4. Generator     → GPT-4o-mini response
  5. Critic        → validate + optional one-time rewrite (skip for AMBIGUOUS)
  6. DB Logger     → persist full audit trail

Each step has a single responsibility. The orchestrator coordinates, not decides.
"""

from typing import Optional
from sqlalchemy.orm import Session


def run_pipeline(
    message: str,
    db: Optional[Session] = None,
    conversation_id: Optional[int] = None,
    message_id: Optional[int] = None,
) -> dict:
    """
    Run the full ethical persuasion pipeline for a user message.

    Args:
        message: Raw user message text
        db: SQLAlchemy session for audit logging (optional; skips logging if None)
        conversation_id: DB conversation ID (required for logging)
        message_id: DB message ID for the user message (required for logging)

    Returns:
        dict with:
          - response: str   Final response to send to the user
          - debug: dict     Full pipeline trace for compliance/debugging
    """
    from pipeline.ethics_gate import evaluate
    from pipeline.classifier import classify
    from pipeline.strategy import select_strategy, load_strategy
    from pipeline.generator import generate
    from pipeline.critic import validate_and_maybe_rewrite

    debug = {
        "pipeline_version": "1.0.0",
        "gate": None,
        "classification": None,
        "strategy_path": None,
        "strategy_name": None,
        "critic": None,
    }

    # ── Step 1: Ethics Gate ───────────────────────────────────────────────────
    gate = evaluate(message)
    debug["gate"] = gate

    # ── Step 2: Classifier (APPROVED only) ───────────────────────────────────
    classification = None
    if gate["decision"] == "APPROVED":
        classification = classify(message)
        debug["classification"] = classification

    # ── Step 3: Strategy Selection ───────────────────────────────────────────
    strategy_path = select_strategy(gate, classification)
    strategy_config = load_strategy(strategy_path)
    debug["strategy_path"] = strategy_path
    debug["strategy_name"] = strategy_config.get("name")

    # ── Step 4: LLM Generation ───────────────────────────────────────────────
    response = generate(
        message=message,
        classification=classification,
        strategy_config=strategy_config,
    )

    # ── Step 5: Critic ───────────────────────────────────────────────────────
    # Skip for AMBIGUOUS: clarifying questions are inherently safe
    critic_result = None
    if gate["decision"] != "AMBIGUOUS":
        response, critic_result = validate_and_maybe_rewrite(
            response=response,
            strategy=strategy_config,
            gate=gate,
            message=message,
            classification=classification,
        )
        debug["critic"] = critic_result

    # ── Step 6: Database Logging ─────────────────────────────────────────────
    if db is not None and conversation_id is not None and message_id is not None:
        _log_to_db(
            db=db,
            conversation_id=conversation_id,
            message_id=message_id,
            gate=gate,
            classification=classification,
            strategy_path=strategy_path,
            critic_result=critic_result,
        )

    return {
        "response": response,
        "debug": debug,
    }


def _log_to_db(
    db: Session,
    conversation_id: int,
    message_id: int,
    gate: dict,
    classification: Optional[dict],
    strategy_path: str,
    critic_result: Optional[dict],
) -> None:
    """
    Persist the full pipeline trace to the Classification table for audit.

    Maps pipeline results to the existing Classification model fields.
    Full raw data is also stored in raw_classification_data JSON column.
    """
    from models import Classification, GateDecision, SituationType

    # Map string decisions to DB enums
    gate_decision_map = {
        "BLOCKED": GateDecision.BLOCKED,
        "APPROVED": GateDecision.APPROVED,
        "AMBIGUOUS": GateDecision.AMBIGUOUS,
    }
    situation_map = {
        "positive_for_business": SituationType.POSITIVE,
        "neutral_for_business": SituationType.NEUTRAL,
        "negative_for_business": SituationType.NEGATIVE,
    }

    gate_enum = gate_decision_map.get(gate["decision"], GateDecision.AMBIGUOUS)

    situation_enum = None
    if classification:
        situation_enum = situation_map.get(classification.get("situation"))

    # Build confidence_scores JSON (stores all non-modeled confidence values)
    confidence_scores = {
        "gate_confidence": gate.get("confidence"),
        "gate_layer": gate.get("layer"),
        "gate_reason": gate.get("reason"),
    }
    if classification:
        confidence_scores.update(
            {
                "emotion_confidence": classification.get("emotion_confidence"),
                "intent_confidence": classification.get("intent_confidence"),
                "situation_confidence": classification.get("situation_confidence"),
            }
        )

    clf_record = Classification(
        conversation_id=conversation_id,
        message_id=message_id,
        gate_decision=gate_enum,
        situation_type=situation_enum,
        emotion=classification.get("emotion") if classification else None,
        intent=classification.get("intent") if classification else None,
        selected_strategy=strategy_path,
        critic_score=critic_result.get("score") if critic_result else None,
        critic_violations=critic_result.get("violations") if critic_result else None,
        confidence_scores=confidence_scores,
        raw_classification_data={
            "gate": gate,
            "classification": classification,
            "strategy_path": strategy_path,
            "critic": critic_result,
        },
        classifier_version="1.0.0",
    )

    db.add(clf_record)
    db.commit()
