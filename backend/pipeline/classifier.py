"""
Classifier - Step 2 of the pipeline.
Runs 3 zero-shot classifications on APPROVED messages:
  1. Emotion  (Plutchik's 8 + financial context)
  2. Intent   (financial services taxonomy)
  3. Situation (business perspective)

Only called when Ethics Gate decision == "APPROVED".
Reuses the shared DeBERTa v3 instance from ethics_gate to save memory.

Research basis:
  - Emotion:    Plutchik (1980), Psychoevolutionary Theory of Emotion
  - Intent:     WAND Banking Taxonomy + TCS financial services use cases
  - Situation:  Business-ethics conflict detection (FCA FG21/1)
"""

from typing import Dict
import logging

from backend.pipeline.ethics_gate import get_classifier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Label maps: natural-language strings for the zero-shot model (better NLI
# performance) → canonical underscore keys used by strategy selector.
# Source: architecture.md lines 133-190
# ---------------------------------------------------------------------------

EMOTION_LABEL_MAP: Dict[str, str] = {
    "anxiety or worry":          "anxiety_or_worry",
    "fear or apprehension":      "fear_or_apprehension",
    "neutral or calm":           "neutral_or_calm",
    "anticipation or interest":  "anticipation_or_interest",
    "sadness or grief":          "sadness_or_grief",
    "joy or contentment":        "joy_or_contentment",
    "anger or frustration":      "anger_or_frustration",
    "trust or acceptance":       "trust_or_acceptance",
}

INTENT_LABEL_MAP: Dict[str, str] = {
    "increase investment or contribution":       "increase_investment_contribution",
    "decrease investment or contribution":       "decrease_investment_contribution",
    "ask about investment performance":          "inquire_about_investment_performance",
    "cancel a policy":                           "cancel_policy",
    "purchase a new policy or product":          "purchase_new_policy",
    "modify or change coverage":                 "modify_coverage",
    "make a withdrawal":                         "make_withdrawal",
    "request a hardship withdrawal":             "hardship_withdrawal",
    "ask a general question":                    "general_inquiry",
    "request an explanation of something":       "request_explanation",
    "seek financial advice":                     "seek_advice",
    "compare financial options":                 "compare_options",
}

SITUATION_LABEL_MAP: Dict[str, str] = {
    "positive for business":  "positive_for_business",
    "neutral for business":   "neutral_for_business",
    "negative for business":  "negative_for_business",
}


def classify(message: str) -> Dict:
    """
    Classify a user message along 3 dimensions.

    Args:
        message: User input that has already passed the Ethics Gate (APPROVED).

    Returns:
        Dict with:
            emotion           — canonical emotion key  (str)
            emotion_score     — top label confidence   (float)
            intent            — canonical intent key   (str)
            intent_score      — top label confidence   (float)
            situation         — canonical situation key (str)
            situation_score   — top label confidence   (float)
            all_scores        — full score breakdowns for debugging / audit log
                {
                  "emotion":   {canonical_key: score, ...},
                  "intent":    {canonical_key: score, ...},
                  "situation": {canonical_key: score, ...},
                }
    """
    classifier = get_classifier()

    # --- 1. Emotion ---
    logger.info("Classifying emotion...")
    emotion_result = classifier(
        message,
        candidate_labels=list(EMOTION_LABEL_MAP.keys()),
    )
    emotion_raw: str = emotion_result["labels"][0]
    emotion_score: float = emotion_result["scores"][0]
    emotion: str = EMOTION_LABEL_MAP[emotion_raw]

    # --- 2. Intent ---
    logger.info("Classifying intent...")
    intent_result = classifier(
        message,
        candidate_labels=list(INTENT_LABEL_MAP.keys()),
    )
    intent_raw: str = intent_result["labels"][0]
    intent_score: float = intent_result["scores"][0]
    intent: str = INTENT_LABEL_MAP[intent_raw]

    # --- 3. Situation ---
    logger.info("Classifying situation...")
    situation_result = classifier(
        message,
        candidate_labels=list(SITUATION_LABEL_MAP.keys()),
    )
    situation_raw: str = situation_result["labels"][0]
    situation_score: float = situation_result["scores"][0]
    situation: str = SITUATION_LABEL_MAP[situation_raw]

    logger.info(
        f"Classification complete — "
        f"emotion={emotion} ({emotion_score:.3f}), "
        f"intent={intent} ({intent_score:.3f}), "
        f"situation={situation} ({situation_score:.3f})"
    )

    return {
        "emotion": emotion,
        "emotion_score": round(emotion_score, 4),
        "intent": intent,
        "intent_score": round(intent_score, 4),
        "situation": situation,
        "situation_score": round(situation_score, 4),
        "all_scores": {
            "emotion": {
                EMOTION_LABEL_MAP[label]: round(score, 4)
                for label, score in zip(emotion_result["labels"], emotion_result["scores"])
            },
            "intent": {
                INTENT_LABEL_MAP[label]: round(score, 4)
                for label, score in zip(intent_result["labels"], intent_result["scores"])
            },
            "situation": {
                SITUATION_LABEL_MAP[label]: round(score, 4)
                for label, score in zip(situation_result["labels"], situation_result["scores"])
            },
        },
    }
