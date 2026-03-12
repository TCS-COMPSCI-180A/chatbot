"""
Critic - Step 5 of the pipeline.

Validates the generated response for ethical and tonal compliance using
zero-shot classification on the response text itself.

Scoring:
  10.0 - Start score
  -3.0 - Coercive or manipulative language detected
  -3.0 - Fear tactics or false urgency detected
   0.0 - Instant fail if persuasion found in BLOCKED context

Pass threshold: score >= 7.0
On failure: ONE rewrite attempt (then accept regardless of rewrite score)

Skipped for AMBIGUOUS path (clarifying questions are inherently safe).

Research basis:
  - FCA Consumer Duty (2023): responses must be fair, clear, not misleading
  - Bounded rewrite (max 1): prevents latency loops, forces first-gen quality
"""

import os
from typing import Optional

_classifier = None


def _get_classifier():
    """Reuse the DeBERTa v3 classifier instance from ethics_gate."""
    global _classifier
    if _classifier is None:
        from pipeline.ethics_gate import _get_classifier as get_gate_clf
        _classifier = get_gate_clf()
    return _classifier


def score_response(response: str, strategy: dict, gate: dict) -> dict:
    """
    Score a generated response for ethical compliance.

    Args:
        response: Generated response text to validate
        strategy: Loaded strategy YAML dict (for context)
        gate: Ethics gate result dict (decision needed for BLOCKED check)

    Returns:
        dict with:
          - score: float 0.0–10.0
          - violations: list of violation strings
          - passed: bool (score >= 7.0)
    """
    clf = _get_classifier()

    result = clf(
        response,
        candidate_labels=[
            "response is coercive or manipulative",
            "response uses fear tactics or false urgency",
            "response is empathetic and transparent",
            "response provides helpful factual information",
        ],
    )

    violations = []
    score = 10.0
    top_label: str = result["labels"][0]
    top_score: float = result["scores"][0]

    # Penalize coercive language
    if "coercive" in top_label and top_score > 0.4:
        violations.append("coercive_language")
        score -= 3.0

    # Penalize fear tactics
    if "fear" in top_label and top_score > 0.4:
        violations.append("fear_tactics")
        score -= 3.0

    # Critical: BLOCKED contexts must contain ZERO persuasive language
    if gate["decision"] == "BLOCKED":
        persuasive_phrases = [
            "consider upgrading",
            "recommend switching",
            "great opportunity",
            "don't miss out",
            "limited time",
            "you should invest",
            "take advantage",
            "act now",
            "before you cancel",
            "you might want to reconsider",
        ]
        response_lower = response.lower()
        for phrase in persuasive_phrases:
            if phrase in response_lower:
                violations.append(f"persuasion_in_blocked_context:{phrase}")
                score = 0.0  # Instant fail
                break

    score = max(0.0, score)
    return {
        "score": round(score, 2),
        "violations": violations,
        "passed": score >= 7.0,
    }


def _rewrite_response(
    original_response: str,
    violations: list,
    message: str,
    strategy: dict,
    gate: dict,
    classification: Optional[dict],
) -> str:
    """
    Generate ONE rewrite of a failed response to fix detected violations.

    Uses a lower temperature (0.5) for more controlled, conservative output.
    """
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    violation_str = "\n".join(f"  - {v}" for v in violations)
    strategy_name = strategy.get("name", "Informational")
    tone = strategy.get("tone", "Professional, helpful")

    rewrite_prompt = f"""The following response violated ethical guidelines:

ORIGINAL RESPONSE:
{original_response}

VIOLATIONS DETECTED:
{violation_str}

STRATEGY: {strategy_name}
REQUIRED TONE: {tone}

Please rewrite the response to:
1. Remove ALL coercive, manipulative, or fear-based language
2. Remove any persuasion from a BLOCKED (vulnerable) context
3. Preserve all genuinely helpful and factual information
4. Follow the original strategy tone: {tone}

Keep the rewrite concise (2-3 paragraphs). Respond directly to the customer."""

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": rewrite_prompt},
            {"role": "user", "content": message},
        ],
        temperature=0.5,
        max_tokens=300,
    )
    return completion.choices[0].message.content.strip()


def validate_and_maybe_rewrite(
    response: str,
    strategy: dict,
    gate: dict,
    message: str,
    classification: Optional[dict],
) -> tuple:
    """
    Validate a response and perform ONE rewrite if it fails the critic.

    Pipeline contract: called once per message, at most ONE rewrite.
    The rewrite result is accepted regardless of its critic score (no loops).

    Args:
        response: Generated response from generator
        strategy: Loaded strategy YAML dict
        gate: Ethics gate result dict
        message: Original user message (needed for rewrite context)
        classification: Classification dict or None

    Returns:
        Tuple of (final_response: str, critic_result: dict)
        critic_result includes score, violations, passed, rewrote
    """
    critic_result = score_response(response, strategy, gate)
    critic_result["rewrote"] = False

    if not critic_result["passed"]:
        response = _rewrite_response(
            original_response=response,
            violations=critic_result["violations"],
            message=message,
            strategy=strategy,
            gate=gate,
            classification=classification,
        )
        # Score the rewrite for logging, but do NOT rewrite again
        rewrite_score = score_response(response, strategy, gate)
        critic_result["score"] = rewrite_score["score"]
        critic_result["violations"] = rewrite_score["violations"]
        critic_result["passed"] = rewrite_score["passed"]
        critic_result["rewrote"] = True

    return response, critic_result
