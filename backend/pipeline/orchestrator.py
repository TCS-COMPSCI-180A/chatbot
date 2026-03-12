"""
Orchestrator - Coordinates the full AI pipeline.
STUB — implementation is handled by teammate (Issue #11).

Pipeline order (NEVER change):
  1. Ethics Gate   → BLOCKED | APPROVED | AMBIGUOUS
  2. Classifier    → emotion, intent, situation (APPROVED only)
  3. Strategy      → select + load YAML
  4. Generator     → Gemini 2.5 Flash response
  5. Critic        → validate + optional one-time rewrite (skip for AMBIGUOUS)
  6. DB Logger     → persist full audit trail

Teammate implementing Issue #11 must implement run_pipeline() which:
  - Calls ethics_gate.evaluate(message)
  - If APPROVED: calls classifier.classify(message)
  - Calls strategy.select_strategy(gate, classification) + strategy.load_strategy(path)
  - Calls generator.generate(message, classification, strategy_config)
  - If not AMBIGUOUS: calls critic.validate_and_maybe_rewrite(...)
  - Logs full trace to DB via Classification model
  - Returns {"response": str, "debug": dict}
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sqlalchemy.orm import Session  # type: ignore[import]


def run_pipeline(
    message: str,  # noqa: ARG001
    db: "Optional[Session]" = None,  # noqa: ARG001
    conversation_id: Optional[int] = None,  # noqa: ARG001
    message_id: Optional[int] = None,  # noqa: ARG001
) -> dict:
    """TODO (Issue #11): Coordinate full pipeline and return {response, debug}."""
    raise NotImplementedError("Orchestrator not yet implemented — see Issue #11")
