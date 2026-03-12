"""
Critic - Step 5 of the pipeline.
Validates generated responses for ethical violations and scores them.
Uses zero-shot classification (shared DeBERTa v3 instance) + hard-coded pattern checks.
"""

from typing import Optional, List, Dict
import logging
from pipeline.ethics_gate import _get_classifier

logger = logging.getLogger(__name__)

VIOLATION_PATTERNS = [
    "guaranteed returns",
    "you should",
    "you must",
    "act now",
    "limited time",
    "everyone is doing this",
    "you will regret",
]

_ETHICAL_LABELS = [
    "this response is manipulative or coercive",
    "this response is informative and ethical",
    "this response is neutral",
]


def check_hard_violations(response: str) -> List[str]:
    """Check for hard-coded violation patterns. Returns list of violation strings."""
    violations = []
    response_lower = response.lower()
    for pattern in VIOLATION_PATTERNS:
        if pattern in response_lower:
            violations.append(f"Prohibited phrase: '{pattern}'")
    return violations


def score_response(response: str, strategy: dict, gate: dict) -> Dict:
    """
    Score response for ethical compliance (0-10).

    Args:
        response: LLM-generated text
        strategy: Strategy config dict used to generate the response
        gate: Ethics gate result dict (e.g. {"decision": "BLOCKED", ...})

    Returns:
        {"score": float, "violations": list, "passed": bool, "raw_classification": dict}
    """
    violations: List[str] = []

    # Check 1: Hard-coded violation patterns
    hard_violations = check_hard_violations(response)
    violations.extend(hard_violations)

    # Check 2: Zero-shot ethical classification (shared DeBERTa v3 model)
    classifier = _get_classifier()
    result = classifier(response, candidate_labels=_ETHICAL_LABELS)
    top_label: str = result["labels"][0]
    top_score: float = result["scores"][0]
    raw_classification = dict(zip(result["labels"], result["scores"]))

    if "manipulative" in top_label and top_score > 0.6:
        violations.append(f"Manipulative language detected ({top_score:.2f} confidence)")

    # Check 3: BLOCKED context — persuasive words are an instant fail
    gate_decision = (gate or {}).get("decision", "")
    persuasive_words = {"consider", "recommend", "opportunity"}
    if gate_decision == "BLOCKED":
        found = persuasive_words & set(response.lower().split())
        if found:
            violations.append(f"Persuasive language in BLOCKED context: {found}")

    # Check 4: Length guard (MVP limit)
    if len(response) > 500:
        violations.append("Response exceeds 500 character limit")

    # Scoring: start at 10, deduct per violation type
    score = 10.0
    score -= len(hard_violations) * 2.0
    if "manipulative" in top_label and top_score > 0.6:
        score -= 3.0
    if gate_decision == "BLOCKED" and any("BLOCKED context" in v for v in violations):
        score = 0.0  # instant fail per architecture spec
    if len(response) > 500:
        score -= 1.0
    score = max(0.0, min(10.0, score))

    passed = score >= 7.0 and len(violations) == 0
    logger.info("Critic: score=%.1f/10 violations=%d passed=%s", score, len(violations), passed)

    return {
        "score": score,
        "violations": violations,
        "passed": passed,
        "raw_classification": raw_classification,
    }


def validate_and_maybe_rewrite(
    response: str,
    strategy: dict,
    gate: dict,
    message: str,
    classification: Optional[dict],
) -> tuple:
    """
    Validate response and rewrite ONCE if it fails (score < 7.0).
    Skips rewrite for AMBIGUOUS gate decisions (ask clarifying questions instead).

    Returns:
        (final_response: str, critic_result: dict)
    """
    from pipeline import generator  # local import avoids circular dependency

    critic_result = score_response(response, strategy, gate)

    gate_decision = (gate or {}).get("decision", "")
    if not critic_result["passed"] and gate_decision != "AMBIGUOUS":
        logger.info(
            "Critic: first attempt failed (score=%.1f), attempting one rewrite",
            critic_result["score"],
        )
        rewritten = generator.generate(message, classification, strategy)
        critic_result = score_response(rewritten, strategy, gate)
        return rewritten, critic_result

    return response, critic_result


def validate(response: str, strategy: dict) -> Dict:
    """
    Convenience wrapper around score_response with no gate context.
    Returns 'approved' key (alias for 'passed') for test compatibility.

    Args:
        response: LLM-generated text
        strategy: Strategy config dict

    Returns:
        {"score": float, "violations": list, "approved": bool, "passed": bool, "raw_classification": dict}
    """
    result = score_response(response, strategy, gate={})
    result["approved"] = result["passed"]
    return result
