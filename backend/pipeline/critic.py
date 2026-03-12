"""
Critic - Step 5 of the pipeline.
STUB — implementation is handled by teammate (Issue #10).

Teammate implementing Issue #10 must implement:
  - score_response(response, strategy, gate) -> dict
      Returns: {"score": float, "violations": list, "passed": bool}
  - validate_and_maybe_rewrite(response, strategy, gate, message, classification) -> tuple
      Returns: (final_response: str, critic_result: dict)
      One rewrite max if score < 7.0. Skip for AMBIGUOUS gate decisions.
"""

from typing import Optional


def score_response(response: str, strategy: dict, gate: dict) -> dict:  # noqa: ARG001
    """TODO (Issue #10): Score response for ethical compliance (0–10)."""
    raise NotImplementedError("Critic not yet implemented — see Issue #10")


def validate_and_maybe_rewrite(
    response: str,  # noqa: ARG001
    strategy: dict,  # noqa: ARG001
    gate: dict,
    message: str,  # noqa: ARG001
    classification: Optional[dict],  # noqa: ARG001
) -> tuple:
    """TODO (Issue #10): Validate response and rewrite once if it fails."""
    raise NotImplementedError("Critic not yet implemented — see Issue #10")
