"""
Orchestrator - Coordinates all pipeline components
Handles BLOCKED, AMBIGUOUS, and APPROVED flows
"""

from typing import Dict, Optional
import logging

# Import pipeline components (these will be created by team members)
try:
    from backend.pipeline import ethics_gate, classifier, strategy, generator, critic
except ImportError:
    try:
        # For running standalone during development
        import ethics_gate, classifier, strategy, generator, critic
    except ImportError:
        # Mock for testing before all components are ready
        ethics_gate = None
        classifier = None
        strategy = None
        generator = None
        critic = None

# Ensure strategy is imported
if strategy is None:
    try:
        from backend.pipeline import strategy
    except ImportError:
        import strategy

logger = logging.getLogger(__name__)


async def run_pipeline(message: str, conversation_id: Optional[int] = None) -> Dict:
    """
    Run full AI pipeline for a user message

    Pipeline flow:
    1. Ethics Gate (always runs first)
    2. If BLOCKED → skip to blocked strategy
    3. If AMBIGUOUS → skip to ambiguous strategy
    4. If APPROVED → run classifier → select strategy → generate → validate with critic

    Args:
        message: User's input text
        conversation_id: Optional conversation ID for context

    Returns:
        Dict with:
        - response: Final text to show user
        - debug: Full decision trace for auditability
    """
    logger.info(f"========== Starting pipeline for message: {message[:50]}... ==========")

    # STEP 1: Ethics Gate (always runs first)
    logger.info("STEP 1: Running ethics gate...")

    if ethics_gate is None:
        logger.error("Ethics gate not implemented yet - using mock")
        gate = {"decision": "APPROVED", "reason": "mock", "confidence": 1.0}
    else:
        gate = ethics_gate.evaluate(message)

    logger.info(f"Gate decision: {gate['decision']} (reason: {gate.get('reason')}, confidence: {gate.get('confidence')})")

    # Initialize result structure
    result = {
        "response": None,
        "debug": {
            "gate_decision": gate["decision"],
            "gate_reason": gate.get("reason"),
            "gate_confidence": gate.get("confidence"),
            "classification": None,
            "strategy": None,
            "critic_score": None,
            "critic_violations": None
        }
    }

    # STEP 2: Handle BLOCKED flow (skip classifier)
    if gate["decision"] == "BLOCKED":
        logger.info("STEP 2: BLOCKED flow - skipping classifier, going straight to strategy")

        # Select blocked strategy
        strategy_path = strategy.select_strategy(gate)
        strategy_config = strategy.load_strategy(strategy_path)

        logger.info(f"STEP 3: Generating response with strategy: {strategy_path}")

        if generator is None:
            logger.error("Generator not implemented yet - using mock response")
            response = f"[BLOCKED - Mock response for: {message}]"
        else:
            response = generator.generate(message, {}, strategy_config)

        result["response"] = response
        result["debug"]["strategy"] = strategy_path
        result["debug"]["classification"] = None  # Explicitly skipped
        result["debug"]["critic_score"] = None  # No critic for blocked

        logger.info(f"========== Pipeline complete (BLOCKED) ==========")
        return result

    # STEP 3: Handle AMBIGUOUS flow (skip classifier)
    elif gate["decision"] == "AMBIGUOUS":
        logger.info("STEP 2: AMBIGUOUS flow - skipping classifier, asking clarifying questions")

        # Use ambiguous strategy
        strategy_path = strategy.select_strategy(gate)
        strategy_config = strategy.load_strategy(strategy_path)

        logger.info(f"STEP 3: Generating response with strategy: {strategy_path}")

        if generator is None:
            logger.error("Generator not implemented yet - using mock response")
            response = f"[AMBIGUOUS - Mock response for: {message}]"
        else:
            response = generator.generate(message, {}, strategy_config)

        result["response"] = response
        result["debug"]["strategy"] = strategy_path
        result["debug"]["classification"] = None  # Explicitly skipped
        result["debug"]["critic_score"] = None  # No critic for clarification

        logger.info(f"========== Pipeline complete (AMBIGUOUS) ==========")
        return result

    # STEP 4: Handle APPROVED flow (full pipeline)
    else:
        logger.info("STEP 2: APPROVED flow - running full pipeline")

        # Run classifier
        logger.info("STEP 3: Running classifier...")

        if classifier is None:
            logger.error("Classifier not implemented yet - using mock")
            classification = {
                "emotion": "neutral or calm",
                "intent": "ask general question",
                "situation": "neutral for business"
            }
        else:
            classification = classifier.classify(message)

        logger.info(f"Classification: emotion={classification['emotion']}, intent={classification['intent']}, situation={classification.get('situation')}")

        # Select strategy
        logger.info("STEP 4: Selecting strategy...")
        strategy_path = strategy.select_strategy(gate, classification)
        strategy_config = strategy.load_strategy(strategy_path)

        # Generate response
        logger.info(f"STEP 5: Generating response with strategy: {strategy_path}")

        if generator is None:
            logger.error("Generator not implemented yet - using mock response")
            response = f"[APPROVED - Mock response for: {message}]"
        else:
            response = generator.generate(message, classification, strategy_config)

        # Validate with critic
        logger.info("STEP 6: Validating response with critic...")

        if critic is None:
            logger.error("Critic not implemented yet - using mock validation")
            critic_result = {"score": 10.0, "violations": [], "approved": True}
        else:
            critic_result = critic.validate(response, strategy_config)

        logger.info(f"Critic score: {critic_result['score']}/10, violations: {len(critic_result.get('violations', []))}, approved: {critic_result.get('approved')}")

        # Bounded rewrite if needed (max 1 rewrite)
        if not critic_result.get("approved", True) and critic_result["score"] < 7.0:
            logger.warning(f"STEP 7: Response failed validation - rewriting once")
            logger.warning(f"Violations: {critic_result['violations']}")

            if generator is None:
                logger.error("Generator not available for rewrite - using original response")
            else:
                response = generator.generate(message, classification, strategy_config, rewrite=True)
                # Re-validate after rewrite
                if critic is not None:
                    critic_result = critic.validate(response, strategy_config)
                    logger.info(f"Post-rewrite critic score: {critic_result['score']}/10")

        result["response"] = response
        result["debug"]["classification"] = classification
        result["debug"]["strategy"] = strategy_path
        result["debug"]["critic_score"] = critic_result.get("score")
        result["debug"]["critic_violations"] = critic_result.get("violations")

        logger.info(f"========== Pipeline complete (APPROVED) ==========")
        return result


# For testing
if __name__ == "__main__":
    import asyncio

    async def test_orchestrator():
        """Test orchestrator with mock components"""

        print("Testing orchestrator...")
        print()

        # Test with a simple message
        result = await run_pipeline("I want to increase my 401k contribution")

        print("Result:")
        print(f"Response: {result['response']}")
        print(f"Debug: {result['debug']}")

    # Run test
    asyncio.run(test_orchestrator())
