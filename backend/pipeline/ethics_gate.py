"""
Ethics Gate - Step 1 of the pipeline.
STUB — implementation is handled by teammate (Issue #7).

This file exposes _get_classifier() which classifier.py depends on to share
the DeBERTa v3 model instance across pipeline steps.

Teammate implementing Issue #7 must:
  - Keep _get_classifier() returning a HuggingFace zero-shot-classification pipeline
  - Model: MoritzLaurer/deberta-v3-base-zeroshot-v2.0
  - Implement evaluate(message) returning:
      {"decision": "BLOCKED"|"AMBIGUOUS"|"APPROVED", "reason": str, "confidence": float, "layer": str}
"""

_classifier = None


def _get_classifier():
    """
    Lazy singleton for the DeBERTa v3 zero-shot classifier.
    Loaded once and reused by classifier.py, critic.py, and this module.
    Model: MoritzLaurer/deberta-v3-base-zeroshot-v2.0
    """
    global _classifier
    if _classifier is None:
        from transformers import pipeline  # type: ignore[import]
        _classifier = pipeline(
            "zero-shot-classification",
            model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
            device=-1,
        )
    return _classifier


def evaluate(message: str) -> dict:
    """
    TODO (Issue #7): Implement ethics gate evaluation.
    Must return:
        {"decision": "BLOCKED"|"AMBIGUOUS"|"APPROVED", "reason": str, "confidence": float, "layer": str}
    """
    raise NotImplementedError("Ethics Gate not yet implemented — see Issue #7")
