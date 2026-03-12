"""
Strategy Selector - Step 3 of the pipeline.

Selects which YAML strategy to apply based on:
  1. Gate decision (BLOCKED/AMBIGUOUS bypass all logic)
  2. Compliance overrides (certain intents always blocked even if gate=APPROVED)
  3. Emotion-first selection (primary signal for strategy choice)
  4. Intent refinement (secondary: narrows within emotion-matched strategies)

Research basis:
  - Cialdini (1984) - Influence: The Psychology of Persuasion (principles framework)
  - Behavioral economics: emotion is stronger framing signal than intent
  - FCA compliance: cancel_policy and hardship_withdrawal never persuaded
"""

import os
import yaml
from typing import Optional

# Base directory for strategy YAML files (relative to this file)
_STRATEGIES_DIR = os.path.join(os.path.dirname(__file__), "..", "strategies")

# ── Compliance Overrides ──────────────────────────────────────────────────────
# These intents ALWAYS get high_risk treatment regardless of gate decision.
# Never persuade users who are cancelling or making hardship withdrawals.
COMPLIANCE_OVERRIDE_INTENTS = {
    "cancel_policy",
    "hardship_withdrawal",
}

# ── Emotion → Strategy Mapping (Cialdini-backed) ─────────────────────────────
# Primary signal: emotion determines the persuasion approach.
_EMOTION_STRATEGY_MAP = {
    "anxiety_or_worry":       "soft_persuasion/social_proof",   # Reassure with peer data
    "fear_or_apprehension":   "soft_persuasion/social_proof",   # Reduce fear with evidence
    "anticipation_or_interest": "soft_persuasion/authority",    # Feed curiosity with expertise
    "trust_or_acceptance":    "soft_persuasion/authority",      # Reinforce trust with guidance
    "joy_or_contentment":     "neutral/informational",          # No extra push needed
    "anger_or_frustration":   "neutral/informational",          # Don't persuade upset users
    "sadness_or_grief":       "blocked/high_risk",              # Fallback if gate missed it
    # neutral_or_calm handled separately (intent-dependent)
}


def load_strategy(strategy_path: str) -> dict:
    """
    Load a strategy YAML file by its relative path (without .yaml extension).

    Args:
        strategy_path: Path relative to strategies/ dir.
                       e.g. "soft_persuasion/social_proof"

    Returns:
        Parsed YAML as dict.

    Raises:
        FileNotFoundError: If the strategy file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    full_path = os.path.join(_STRATEGIES_DIR, f"{strategy_path}.yaml")
    with open(full_path, "r") as f:
        return yaml.safe_load(f)


def select_strategy(gate: dict, classification: Optional[dict]) -> str:
    """
    Select the appropriate strategy path based on gate decision and classification.

    Selection priority (highest wins):
      1. Gate BLOCKED/AMBIGUOUS → always use blocked strategy
      2. Compliance override intents → always use high_risk
      3. Emotion-first mapping
      4. Default: informational

    Args:
        gate: Result from ethics_gate.evaluate()
        classification: Result from classifier.classify(), or None if gate != APPROVED

    Returns:
        Strategy path string, e.g. "soft_persuasion/social_proof"

    Examples:
        >>> select_strategy({"decision": "BLOCKED", "reason": "bereavement:died"}, None)
        "blocked/bereavement"

        >>> select_strategy({"decision": "AMBIGUOUS", ...}, None)
        "blocked/ambiguous"

        >>> select_strategy(
        ...     {"decision": "APPROVED", ...},
        ...     {"emotion": "anxiety_or_worry", "intent": "increase_investment_contribution", ...}
        ... )
        "soft_persuasion/social_proof"
    """
    decision = gate["decision"]
    reason = gate.get("reason", "")

    # ── Priority 1: Gate blocked/ambiguous overrides everything ───────────────
    if decision == "BLOCKED":
        if "bereavement" in reason:
            return "blocked/bereavement"
        return "blocked/high_risk"

    if decision == "AMBIGUOUS":
        return "blocked/ambiguous"

    # ── From here: decision == "APPROVED" ─────────────────────────────────────

    if not classification:
        return "neutral/informational"

    intent = classification.get("intent", "")

    # ── Priority 2: Compliance overrides (FCA requirement) ────────────────────
    if intent in COMPLIANCE_OVERRIDE_INTENTS:
        return "blocked/high_risk"

    # ── Priority 3: Emotion-first selection ───────────────────────────────────
    emotion = classification.get("emotion", "")

    # Special case: neutral/calm depends on what the user is trying to do
    if emotion == "neutral_or_calm":
        if intent in {"seek_advice", "request_explanation", "compare_options"}:
            return "soft_persuasion/authority"
        return "neutral/informational"

    strategy = _EMOTION_STRATEGY_MAP.get(emotion)
    if strategy:
        return strategy

    # ── Priority 4: Default ───────────────────────────────────────────────────
    return "neutral/informational"
