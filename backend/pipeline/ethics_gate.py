"""
Ethics Gate - Step 1 of the pipeline.

Determines whether persuasion is appropriate for this message.
Uses two layers:
  Layer 1: Hard-coded keyword rules (instant, deterministic, no false negatives)
  Layer 2: DeBERTa v3 zero-shot classification (nuanced vulnerability detection)

Returns one of three decisions:
  BLOCKED   - Vulnerable context; provide empathy/info only, no persuasion
  APPROVED  - Safe to proceed with full pipeline
  AMBIGUOUS - Context unclear; ask clarifying questions first

Research basis:
  - FCA Consumer Duty (2023) - vulnerable customer protection
  - MoritzLaurer/deberta-v3-base-zeroshot-v2.0 (state-of-the-art zero-shot, Jan 2025)
"""

from typing import Optional

# Hard-block keywords: always BLOCKED, 100% deterministic, no LLM needed
HARD_BLOCK_KEYWORDS = [
    "passed away",
    "death",
    "died",
    "funeral",
    "bereavement",
    "grieving",
    "suicide",
    "bankruptcy",
    "foreclosure",
    "lost my job",
    "laid off",
    "can't afford",
    "cannot afford",
    "lost my home",
    "eviction",
    "terminal illness",
    "diagnosed with",
]

# Keywords that specifically indicate bereavement (used for strategy routing)
BEREAVEMENT_KEYWORDS = {
    "passed away",
    "death",
    "died",
    "funeral",
    "bereavement",
    "grieving",
}

# Lazy-loaded model (only loads on first call to save startup time)
_classifier = None


def _get_classifier():
    """Load the DeBERTa v3 zero-shot classifier lazily."""
    global _classifier
    if _classifier is None:
        from transformers import pipeline

        _classifier = pipeline(
            "zero-shot-classification",
            model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
            device=-1,  # CPU; set to 0 for GPU if available
        )
    return _classifier


def evaluate(message: str) -> dict:
    """
    Evaluate whether persuasion is appropriate for this message.

    Args:
        message: Raw user message text

    Returns:
        dict with keys:
          - decision: "BLOCKED" | "APPROVED" | "AMBIGUOUS"
          - reason: human-readable explanation (e.g. "bereavement:passed away")
          - confidence: float 0.0–1.0
          - layer: "hard_rule" | "zero_shot"

    Examples:
        >>> evaluate("My spouse passed away")
        {"decision": "BLOCKED", "reason": "bereavement:passed away", ...}

        >>> evaluate("I want to increase my 401k contribution")
        {"decision": "APPROVED", "reason": "safe_context", ...}

        >>> evaluate("Not sure what to do")
        {"decision": "AMBIGUOUS", "reason": "unclear_context", ...}
    """
    msg_lower = message.lower()

    # ── Layer 1: Hard-coded rules ─────────────────────────────────────────────
    for keyword in HARD_BLOCK_KEYWORDS:
        if keyword in msg_lower:
            reason_type = "bereavement" if keyword in BEREAVEMENT_KEYWORDS else "hardship"
            return {
                "decision": "BLOCKED",
                "reason": f"{reason_type}:{keyword}",
                "confidence": 1.0,
                "layer": "hard_rule",
            }

    # ── Layer 2: Zero-shot classification ─────────────────────────────────────
    clf = _get_classifier()
    result = clf(
        message,
        candidate_labels=[
            "this person is vulnerable or distressed",
            "this is a routine financial inquiry",
            "the context is unclear",
        ],
    )

    top_label: str = result["labels"][0]
    top_score: float = result["scores"][0]

    if "vulnerable" in top_label and top_score > 0.6:
        return {
            "decision": "BLOCKED",
            "reason": "vulnerability_detected",
            "confidence": top_score,
            "layer": "zero_shot",
        }

    if "unclear" in top_label and top_score > 0.5:
        return {
            "decision": "AMBIGUOUS",
            "reason": "unclear_context",
            "confidence": top_score,
            "layer": "zero_shot",
        }

    return {
        "decision": "APPROVED",
        "reason": "safe_context",
        "confidence": top_score,
        "layer": "zero_shot",
    }
