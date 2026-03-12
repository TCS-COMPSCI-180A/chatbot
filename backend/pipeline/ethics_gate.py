"""
Ethics Gate — backend/pipeline/ethics_gate.py
==============================================
Pipeline Step 1: Fast, cheap gatekeeper.
Blocks persuasion attempts when user context is vulnerable.

Two-layer approach:
  Layer 1: Hard-coded keyword rules  →  instant, deterministic, zero false-negatives
  Layer 2: DeBERTa v3 Zero-Shot     →  catches nuanced vulnerability not in keyword list

Returns:
  { "decision": "BLOCKED" | "APPROVED" | "AMBIGUOUS", ... }
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# LAYER 1 — Hard-coded keyword blocklist
# FCA Vulnerability Mapping: Financial Conduct Authority (FCA) Consumer Duty
# (2023) requires firms to identify and protect customers in vulnerable
# circumstances. These keywords map to the four FCA vulnerability drivers:
#   - Life events   : bereavement, job loss
#   - Health        : suicide, mental distress
#   - Resilience    : bankruptcy, foreclosure, can't afford
#   - Capability    : (handled by zero-shot model layer)
# =============================================================================
HARD_BLOCK_KEYWORDS: list[str] = [
    # --- Bereavement / Life Events ---
    "passed away",
    "death",
    "died",
    "funeral",
    "bereavement",
    "grieving",
    # --- Mental Health / Crisis ---
    "suicide",
    # --- Financial Distress / Resilience ---
    "bankruptcy",
    "foreclosure",
    "can't afford",
    # --- Employment / Income Shock ---
    "lost my job",
    "laid off",
]

# =============================================================================
# LAYER 2 — Zero-shot candidate labels (DeBERTa v3)
# =============================================================================
VULNERABILITY_LABELS: list[str] = [
    "this person is vulnerable or distressed",
    "this is a routine financial inquiry",
    "the context is unclear",
]

# Confidence threshold: below this, vulnerable label → AMBIGUOUS not BLOCKED
VULNERABILITY_THRESHOLD: float = 0.60

# =============================================================================
# Singleton model loader — loaded once, reused across all requests
# =============================================================================
_classifier = None


def _get_classifier():
    """Lazy-load DeBERTa v3 zero-shot classifier."""
    global _classifier
    if _classifier is None:
        from transformers import pipeline as hf_pipeline
        logger.info("Loading DeBERTa v3 zero-shot classifier…")
        _classifier = hf_pipeline(
            task="zero-shot-classification",
            model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0",
            device=-1,  # CPU; set device=0 for GPU
        )
        logger.info("DeBERTa v3 loaded successfully.")
    return _classifier


# =============================================================================
# Public API
# =============================================================================
def evaluate(message: str) -> dict:
    """
    Evaluate an incoming user message through the Ethics Gate.

    Parameters
    ----------
    message : str
        Raw user message text.

    Returns
    -------
    dict
        decision   : "BLOCKED" | "APPROVED" | "AMBIGUOUS"
        reason     : machine-readable reason code
        confidence : float  0.0–1.0
        layer      : "keyword" | "model"
        raw        : full model output (None for keyword matches)

    Examples
    --------
    >>> evaluate("My spouse passed away")["decision"]
    'BLOCKED'
    >>> evaluate("I want to increase my 401k")["decision"]
    'APPROVED'
    >>> evaluate("Not sure what to do")["decision"]
    'AMBIGUOUS'
    """
    # ------------------------------------------------------------------
    # Guard: empty / whitespace input
    # ------------------------------------------------------------------
    if not message or not message.strip():
        logger.warning("Ethics Gate received empty message.")
        return _result("AMBIGUOUS", "empty_message", 1.0, "keyword")

    message_lower = message.lower()

    # ------------------------------------------------------------------
    # LAYER 1: Keyword scan
    # O(n) string search — completes in microseconds.
    # A keyword match is a hard BLOCK: model is never called.
    # ------------------------------------------------------------------
    for keyword in HARD_BLOCK_KEYWORDS:
        if keyword in message_lower:
            logger.info(f"[EthicsGate] BLOCKED by keyword: '{keyword}'")
            return _result("BLOCKED", f"keyword:{keyword}", 1.0, "keyword")

    # ------------------------------------------------------------------
    # LAYER 2: Zero-shot model
    # Catches nuanced phrasing like "struggling financially" not in keyword
    # list. Fail-safe: any model error → AMBIGUOUS (never silently APPROVED).
    # ------------------------------------------------------------------
    try:
        clf = _get_classifier()
        raw = clf(
            sequences=message,
            candidate_labels=VULNERABILITY_LABELS,
            multi_label=False,
        )
    except Exception as exc:
        logger.error(f"[EthicsGate] Model inference failed: {exc}", exc_info=True)
        return _result("AMBIGUOUS", "model_error", 0.0, "model")

    top_label: str  = raw["labels"][0]
    top_score: float = raw["scores"][0]

    logger.debug(f"[EthicsGate] top_label='{top_label}'  score={top_score:.3f}")

    if "vulnerable" in top_label:
        if top_score >= VULNERABILITY_THRESHOLD:
            return _result("BLOCKED",   "model:vulnerable_or_distressed", top_score, "model", raw)
        else:
            # Below threshold → not confident enough to APPROVE, stay safe
            return _result("AMBIGUOUS", "model:vulnerable_low_confidence", top_score, "model", raw)

    if "unclear" in top_label:
        return _result("AMBIGUOUS", "model:context_unclear", top_score, "model", raw)

    # "routine financial inquiry"
    return _result("APPROVED", "model:routine_financial_inquiry", top_score, "model", raw)


# =============================================================================
# Internal helpers
# =============================================================================
def _result(
    decision: str,
    reason: str,
    confidence: float,
    layer: str,
    raw: Optional[dict] = None,
) -> dict:
    """Build a standardised Ethics Gate result dict."""
    return {
        "decision":   decision,    # BLOCKED | APPROVED | AMBIGUOUS
        "reason":     reason,      # machine-readable code
        "confidence": confidence,  # 0.0 – 1.0
        "layer":      layer,       # keyword | model
        "raw":        raw,         # full model output for audit logging
    }
