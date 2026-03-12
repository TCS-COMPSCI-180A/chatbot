"""
Ethics Gate - Step 1 of the pipeline.
STUB — full implementation is handled separately (Issue #7).

This file exposes get_classifier() which classifier.py depends on.
The teammate implementing Issue #7 must:
  - Keep get_classifier() returning a HuggingFace zero-shot-classification pipeline
  - Model: MoritzLaurer/deberta-v3-base-zeroshot-v2.0
  - Implement evaluate(message) returning {"decision": "BLOCKED"|"AMBIGUOUS"|"APPROVED", ...}
"""

# TODO (Issue #7): Implement full ethics gate logic here.
# classifier.py imports get_classifier() from this module — keep that function name and return type.

_classifier_instance = None


def get_classifier():
    """
    Returns the shared zero-shot classification pipeline (DeBERTa v3).
    Loaded lazily and cached for reuse across all pipeline steps.
    """
    global _classifier_instance
    if _classifier_instance is None:
        from transformers import pipeline as hf_pipeline
        _classifier_instance = hf_pipeline(
            "zero-shot-classification",
            model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
        )
    return _classifier_instance


def evaluate(message: str) -> dict:  # noqa: ARG001
    """
    TODO (Issue #7): Implement ethics gate evaluation.
    Must return a dict with at minimum:
        {"decision": "BLOCKED" | "AMBIGUOUS" | "APPROVED", "reason": str, "confidence": float}
    """
    raise NotImplementedError("Ethics Gate not yet implemented — see Issue #7")
