"""
Test Strategy Agent - Member 4's work

Tests the strategy selection logic with mocked state data.
No dependencies on document analysis, classifier, or other components.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load .env file and OVERRIDE any shell env vars
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'), override=True)

from agents.strategy_agent import strategy_node, load_strategy
import agents.strategy_agent as strategy_agent_module

# Clear the cached Gemini client so it reloads with the new API key
strategy_agent_module._gemini_client = None


def test_blocked_human_handoff():
    """Test: BLOCKED gate → human handoff (no AI response)"""
    print("\n" + "="*70)
    print("TEST 1: BLOCKED gate → human handoff")
    print("="*70)

    state = {
        "message": "My spouse passed away, I need to cancel our account",
        "gate_decision": "BLOCKED",
        "gate_reason": "keyword:passed away",
        "emotion": None,
        "intent": None,
        "situation": None,
        "has_document": False,
        "document_type": None
    }

    result = strategy_node(state)

    print(f"✓ Human handoff: {result['human_handoff']}")
    print(f"✓ Handoff reason: {result['handoff_reason']}")
    print(f"✓ Strategy path: {result['strategy_path']}")
    print(f"✓ Reasoning: {result['strategy_reasoning'][:100]}...")

    assert result["human_handoff"] == True, "Should trigger human handoff"
    assert result["strategy_path"] is None, "No strategy for BLOCKED cases"
    print("\n✅ PASSED: BLOCKED correctly routes to human handoff\n")


def test_ambiguous_clarification():
    """Test: AMBIGUOUS gate → clarification strategy"""
    print("\n" + "="*70)
    print("TEST 2: AMBIGUOUS gate → ask clarifying questions")
    print("="*70)

    state = {
        "message": "Not sure what to do with my savings",
        "gate_decision": "AMBIGUOUS",
        "gate_reason": "model:context_unclear",
        "emotion": None,
        "intent": None,
        "situation": None,
        "has_document": False,
        "document_type": None
    }

    result = strategy_node(state)

    print(f"✓ Human handoff: {result['human_handoff']}")
    print(f"✓ Strategy path: {result['strategy_path']}")
    print(f"✓ Strategy name: {result['strategy_config']['name']}")
    print(f"✓ LLM reasoning: {result['strategy_reasoning'][:100]}...")

    assert result["human_handoff"] == False, "AMBIGUOUS doesn't need human"
    assert "ambiguous" in result["strategy_path"], "Should use ambiguous strategy"
    print("\n✅ PASSED: AMBIGUOUS correctly selects clarification strategy\n")


def test_compliance_override_fraud():
    """Test: Fraud report intent → compliance override (even if APPROVED)"""
    print("\n" + "="*70)
    print("TEST 3: Compliance override - fraud report")
    print("="*70)

    state = {
        "message": "I see charges I didn't make on my account",
        "gate_decision": "APPROVED",  # Gate says safe
        "gate_reason": "model:routine_financial_inquiry",
        "emotion": "anger_or_frustration",
        "intent": "report_fraudulent_activity",
        "situation": "negative_for_business",
        "has_document": False,
        "document_type": None
    }

    result = strategy_node(state)

    print(f"✓ Strategy path: {result['strategy_path']}")
    print(f"✓ LLM reasoning: {result['strategy_reasoning'][:150]}...")

    assert "fraud_report" in result["strategy_path"], "Should override to fraud_report"
    print("\n✅ PASSED: Compliance override works (fraud escalation)\n")


def test_document_grounded_path():
    """Test: Document present + advice-seeking → document_grounded strategy"""
    print("\n" + "="*70)
    print("TEST 4: Document-grounded path (statement analysis)")
    print("="*70)

    state = {
        "message": "How can I save more money based on my statement?",
        "gate_decision": "APPROVED",
        "gate_reason": "model:routine_financial_inquiry",
        "emotion": "neutral_or_calm",
        "intent": "seek_banking_advice",
        "situation": "neutral_for_business",
        "has_document": True,
        "document_type": "bank_statement"
    }

    result = strategy_node(state)

    print(f"✓ Strategy path: {result['strategy_path']}")
    print(f"✓ LLM reasoning: {result['strategy_reasoning'][:150]}...")

    assert "document_grounded" in result["strategy_path"], "Should use document-grounded strategy"
    print("\n✅ PASSED: Document-grounded path selected\n")


def test_emotion_first_anxiety():
    """Test: Anxiety emotion → social proof strategy"""
    print("\n" + "="*70)
    print("TEST 5: Emotion-first selection (anxiety → social proof)")
    print("="*70)

    state = {
        "message": "I'm worried about opening a new credit card with current rates",
        "gate_decision": "APPROVED",
        "gate_reason": "model:routine_financial_inquiry",
        "emotion": "anxiety_or_worry",
        "intent": "inquire_about_credit_card",
        "situation": "neutral_for_business",
        "has_document": False,
        "document_type": None
    }

    result = strategy_node(state)

    print(f"✓ Strategy path: {result['strategy_path']}")
    print(f"✓ LLM reasoning: {result['strategy_reasoning'][:150]}...")

    assert "social_proof" in result["strategy_path"], "Anxiety should trigger social proof"
    print("\n✅ PASSED: Emotion-first selection works\n")


def test_default_fallback():
    """Test: No specific match → neutral/informational"""
    print("\n" + "="*70)
    print("TEST 6: Default fallback → neutral/informational")
    print("="*70)

    state = {
        "message": "What is APR?",
        "gate_decision": "APPROVED",
        "gate_reason": "model:routine_financial_inquiry",
        "emotion": "neutral_or_calm",
        "intent": "general_banking_inquiry",
        "situation": "neutral_for_business",
        "has_document": False,
        "document_type": None
    }

    result = strategy_node(state)

    print(f"✓ Strategy path: {result['strategy_path']}")
    print(f"✓ LLM reasoning: {result['strategy_reasoning'][:150]}...")

    assert "informational" in result["strategy_path"], "Should default to informational"
    print("\n✅ PASSED: Default fallback works\n")


def test_yaml_loading():
    """Test: All YAML strategy files load correctly"""
    print("\n" + "="*70)
    print("TEST 7: YAML file loading")
    print("="*70)

    strategies = [
        "blocked/bereavement",
        "blocked/high_risk",
        "blocked/ambiguous",
        "blocked/fraud_report",
        "blocked/financial_hardship",
        "soft_persuasion/social_proof",
        "soft_persuasion/authority",
        "soft_persuasion/reciprocity",
        "document_grounded/statement_analysis",
        "document_grounded/loan_analysis",
        "neutral/informational"
    ]

    for strategy_path in strategies:
        try:
            strategy = load_strategy(strategy_path)
            print(f"✓ {strategy_path:40} → {strategy['name']}")
            assert 'name' in strategy
            assert 'principle' in strategy
            assert 'tone' in strategy
        except Exception as e:
            print(f"✗ {strategy_path:40} → ERROR: {e}")
            raise

    print("\n✅ PASSED: All 11 YAML files load successfully\n")


if __name__ == "__main__":
    print("\n" + "🧪 STRATEGY AGENT TEST SUITE" + "\n")
    print("Testing Member 4's strategy selection logic with mocked state data")

    try:
        test_blocked_human_handoff()
        test_ambiguous_clarification()
        test_compliance_override_fraud()
        test_document_grounded_path()
        test_emotion_first_anxiety()
        test_default_fallback()
        test_yaml_loading()

        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED!")
        print("="*70)
        print("\nStrategy agent is working correctly!")
        print("✓ BLOCKED → human handoff")
        print("✓ AMBIGUOUS → clarification")
        print("✓ Compliance overrides work")
        print("✓ Document-grounded path works")
        print("✓ Emotion-first selection works")
        print("✓ Default fallback works")
        print("✓ All YAML files load\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        raise
