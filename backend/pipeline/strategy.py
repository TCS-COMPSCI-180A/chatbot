"""
Strategy Selector - Chooses persuasion strategy based on classification
Uses emotion-first approach without compliance overrides
"""

import yaml
import os
from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Get strategies directory path
STRATEGIES_DIR = os.path.join(os.path.dirname(__file__), "..", "strategies")


def load_strategy(strategy_path: str) -> Dict:
    """
    Load strategy YAML file

    Args:
        strategy_path: Relative path like "soft_persuasion/social_proof" or "blocked/bereavement"

    Returns:
        Parsed YAML dict with strategy configuration

    Raises:
        FileNotFoundError: If strategy file doesn't exist
    """
    full_path = os.path.join(STRATEGIES_DIR, f"{strategy_path}.yaml")

    if not os.path.exists(full_path):
        logger.error(f"Strategy file not found: {full_path}")
        raise FileNotFoundError(f"Strategy not found: {strategy_path}")

    with open(full_path, 'r') as f:
        strategy = yaml.safe_load(f)

    logger.info(f"Loaded strategy: {strategy.get('name', strategy_path)}")
    return strategy


def select_strategy(gate: Dict, classification: Dict = None) -> str:
    """
    Select appropriate strategy based on gate decision and classification

    Decision logic:
    1. BLOCKED → bereavement or high_risk (no classifier needed)
    2. AMBIGUOUS → ambiguous (no classifier needed)
    3. APPROVED → emotion-first selection (classifier required)

    Args:
        gate: Ethics gate decision dict with 'decision', 'reason', 'confidence'
        classification: Classification results (only required if APPROVED)

    Returns:
        Strategy path (e.g., "soft_persuasion/social_proof")
    """

    # STEP 1: Handle BLOCKED cases
    if gate["decision"] == "BLOCKED":
        # Special handling for bereavement (most sensitive)
        if "bereavement" in gate.get("reason", ""):
            logger.info("Strategy: blocked/bereavement (loss/death detected)")
            return "blocked/bereavement"
        else:
            # All other vulnerability cases
            logger.info(f"Strategy: blocked/high_risk (reason: {gate.get('reason')})")
            return "blocked/high_risk"

    # STEP 2: Handle AMBIGUOUS cases
    if gate["decision"] == "AMBIGUOUS":
        logger.info("Strategy: blocked/ambiguous (context unclear, asking questions)")
        return "blocked/ambiguous"

    # STEP 3: Handle APPROVED cases (requires classification)
    if classification is None:
        raise ValueError("Classification required for APPROVED gate decision")

    emotion = classification["emotion"]
    intent = classification["intent"]

    logger.info(f"Classification: emotion={emotion}, intent={intent}")

    # Emotion-first strategy selection (no compliance override)

    # High anxiety/fear/worry → Social proof
    if "anxiety" in emotion or "worry" in emotion or "fear" in emotion or "apprehension" in emotion:
        logger.info("Strategy: soft_persuasion/social_proof (anxiety detected)")
        return "soft_persuasion/social_proof"

    # Calm + advice-seeking → Authority
    if ("trust" in emotion or "confidence" in emotion) and "advice" in intent:
        logger.info("Strategy: soft_persuasion/authority (calm advice-seeking)")
        return "soft_persuasion/authority"

    # Default: informational (safe fallback)
    logger.info("Strategy: neutral/informational (default fallback)")
    return "neutral/informational"


# For testing
if __name__ == "__main__":
    # Test YAML loading
    print("Testing strategy loading...")

    strategies = [
        "blocked/bereavement",
        "blocked/high_risk",
        "blocked/ambiguous",
        "soft_persuasion/social_proof",
        "soft_persuasion/authority",
        "neutral/informational"
    ]

    for strategy_path in strategies:
        try:
            strategy = load_strategy(strategy_path)
            print(f"✓ {strategy_path}: {strategy['name']}")
        except Exception as e:
            print(f"✗ {strategy_path}: {e}")

    print("\nTesting strategy selection...")

    # Test BLOCKED
    gate = {"decision": "BLOCKED", "reason": "bereavement_detected"}
    result = select_strategy(gate)
    print(f"BLOCKED (bereavement): {result}")

    gate = {"decision": "BLOCKED", "reason": "high_risk_detected"}
    result = select_strategy(gate)
    print(f"BLOCKED (high_risk): {result}")

    # Test AMBIGUOUS
    gate = {"decision": "AMBIGUOUS", "reason": "context_unclear"}
    result = select_strategy(gate)
    print(f"AMBIGUOUS: {result}")

    # Test APPROVED
    gate = {"decision": "APPROVED"}
    classification = {"emotion": "anxiety or worry", "intent": "increase investment"}
    result = select_strategy(gate, classification)
    print(f"APPROVED (anxiety): {result}")

    classification = {"emotion": "trust or confidence", "intent": "seek financial advice"}
    result = select_strategy(gate, classification)
    print(f"APPROVED (trust + advice): {result}")

    classification = {"emotion": "neutral or calm", "intent": "ask general question"}
    result = select_strategy(gate, classification)
    print(f"APPROVED (neutral): {result}")
