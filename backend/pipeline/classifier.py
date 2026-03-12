"""
Classifier - Step 2 of the pipeline.

Runs 3 zero-shot classifications to extract rich context from the user message.
Only called when Ethics Gate returns APPROVED (saves compute on blocked messages).

Three dimensions classified:
  1. Emotion  - Based on Plutchik's Wheel of Emotions + financial context
  2. Intent   - Financial services taxonomy (investment, policy, withdrawal, etc.)
  3. Situation - Business perspective (positive/neutral/negative for business)

Research basis:
  - Plutchik (1980) - Psychoevolutionary Theory of Emotion (8 basic emotions)
  - Ekman additions for financial context
  - WAND Banking Taxonomy for intent labels
  - Reuses the same DeBERTa v3 model instance from ethics_gate (memory efficient)
"""

# ── Emotion Labels (Plutchik's Wheel + Financial Context) ─────────────────────
EMOTION_LABELS = [
    "anxiety_or_worry",           # Financial uncertainty, market fear
    "fear_or_apprehension",       # Market volatility, loss aversion
    "neutral_or_calm",            # Rational, detached inquiry
    "anticipation_or_interest",   # Exploring new financial options
    "sadness_or_grief",           # Loss-related (caught by gate, but fallback)
    "joy_or_contentment",         # Positive financial news, satisfaction
    "anger_or_frustration",       # Service complaint, dissatisfaction
    "trust_or_acceptance",        # Confidence in advisor or institution
]

# ── Intent Labels (Financial Services Taxonomy) ───────────────────────────────
INTENT_LABELS = [
    # Investment management
    "increase_investment_contribution",
    "decrease_investment_contribution",
    "inquire_about_investment_performance",
    # Policy management
    "cancel_policy",
    "purchase_new_policy",
    "modify_coverage",
    # Withdrawals and assistance
    "make_withdrawal",
    "hardship_withdrawal",
    # Information seeking
    "general_inquiry",
    "request_explanation",
    "seek_advice",
    "compare_options",
]

# ── Situation Labels (Business Perspective) ───────────────────────────────────
SITUATION_LABELS = [
    "positive_for_business",   # User wants to invest more, buy new policy
    "neutral_for_business",    # Informational query, no business impact
    "negative_for_business",   # User wants to cancel, reduce, or withdraw
]

# Lazy-loaded classifier (shared with ethics_gate for memory efficiency)
_classifier = None


def _get_classifier():
    """Reuse the DeBERTa v3 classifier instance from ethics_gate."""
    global _classifier
    if _classifier is None:
        # Import from ethics_gate to reuse the same singleton
        from backend.pipeline.ethics_gate import _get_classifier as get_gate_clf
        _classifier = get_gate_clf()
    return _classifier


def classify(message: str) -> dict:
    """
    Classify a user message across emotion, intent, and situation dimensions.

    IMPORTANT: Only call this when ethics_gate.evaluate() returned APPROVED.
    Calling on BLOCKED/AMBIGUOUS messages wastes compute and is architecturally wrong.

    Args:
        message: Raw user message text

    Returns:
        dict with:
          - emotion: str (top emotion label)
          - emotion_confidence: float
          - intent: str (top intent label)
          - intent_confidence: float
          - situation: str (top situation label)
          - situation_confidence: float

    Example:
        >>> classify("I'm worried about increasing my 401k with market volatility")
        {
            "emotion": "anxiety_or_worry",
            "emotion_confidence": 0.89,
            "intent": "increase_investment_contribution",
            "intent_confidence": 0.76,
            "situation": "positive_for_business",
            "situation_confidence": 0.82
        }
    """
    clf = _get_classifier()

    # Run all 3 zero-shot classifications
    emotion_result = clf(message, candidate_labels=EMOTION_LABELS)
    intent_result = clf(message, candidate_labels=INTENT_LABELS)
    situation_result = clf(message, candidate_labels=SITUATION_LABELS)

    return {
        "emotion": emotion_result["labels"][0],
        "emotion_confidence": round(emotion_result["scores"][0], 4),
        "intent": intent_result["labels"][0],
        "intent_confidence": round(intent_result["scores"][0], 4),
        "situation": situation_result["labels"][0],
        "situation_confidence": round(situation_result["scores"][0], 4),
    }
