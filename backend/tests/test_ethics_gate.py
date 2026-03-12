"""
Test Suite — Ethics Gate
========================
Covers every requirement from the Person 2 task spec.

Run:
    pytest backend/tests/test_ethics_gate.py -v

Required assert cases (from spec):
    assert evaluate("My spouse passed away")["decision"] == "BLOCKED"
    assert evaluate("I want to increase my 401k")["decision"] == "APPROVED"
    assert evaluate("Not sure what to do")["decision"] == "AMBIGUOUS"
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.pipeline.ethics_gate import (
    evaluate,
    HARD_BLOCK_KEYWORDS,
    VULNERABILITY_THRESHOLD,
)
from backend.pipeline.blocked_responses import (
    get_blocked_response,
    resolve_category,
    BlockedCategory,
)


# =============================================================================
# Helpers
# =============================================================================
def mock_model(top_label: str, top_score: float):
    """Return a mock zero-shot classifier with a fixed top result."""
    m = MagicMock()
    m.return_value = {
        "labels": [top_label, "other_label", "another_label"],
        "scores": [top_score, 0.10, 0.05],
    }
    return m


ROUTINE_MODEL  = mock_model("this is a routine financial inquiry", 0.92)
VULNERABLE_MODEL = mock_model("this person is vulnerable or distressed", 0.85)
UNCLEAR_MODEL  = mock_model("the context is unclear", 0.78)


# =============================================================================
# SPEC ASSERT CASES — must pass exactly as written in the task spec
# =============================================================================
class TestSpecAsserts:
    """These three tests are the exact deliverable assertions from the spec."""

    def test_bereavement_blocked(self):
        result = evaluate("My spouse passed away")
        assert result["decision"] == "BLOCKED"

    def test_routine_approved(self):
        with patch("backend.pipeline.ethics_gate._get_classifier", return_value=ROUTINE_MODEL):
            result = evaluate("I want to increase my 401k")
        assert result["decision"] == "APPROVED"

    def test_unclear_ambiguous(self):
        with patch("backend.pipeline.ethics_gate._get_classifier", return_value=UNCLEAR_MODEL):
            result = evaluate("Not sure what to do")
        assert result["decision"] == "AMBIGUOUS"


# =============================================================================
# TASK 2a: Test bereavement keywords → BLOCKED
# =============================================================================
class TestBereavementKeywords:

    BEREAVEMENT_MESSAGES = [
        "My spouse passed away last week",
        "I need help after the death of my father",
        "My mother died recently",
        "I'm calling about a funeral arrangement",
        "We are in a bereavement period",
        "I am grieving and need to cancel the policy",
    ]

    @pytest.mark.parametrize("message", BEREAVEMENT_MESSAGES)
    def test_bereavement_message_blocked(self, message):
        result = evaluate(message)
        assert result["decision"] == "BLOCKED", f"Expected BLOCKED for: '{message}'"
        assert result["layer"] == "keyword"
        assert result["confidence"] == 1.0

    def test_bereavement_reason_contains_keyword(self):
        result = evaluate("My spouse passed away")
        assert result["reason"].startswith("keyword:")

    def test_bereavement_model_never_called(self):
        """Keyword layer must short-circuit before the model is invoked."""
        with patch("backend.pipeline.ethics_gate._get_classifier") as mock_get:
            evaluate("My spouse passed away")
        mock_get.assert_not_called()


# =============================================================================
# TASK 2b: Test routine inquiry → APPROVED
# =============================================================================
class TestRoutineInquiry:

    ROUTINE_MESSAGES = [
        "I want to increase my 401k",
        "What are the contribution limits for a Roth IRA?",
        "Can I add a beneficiary to my policy?",
        "How does dollar-cost averaging work?",
        "I'd like to open a new investment account",
    ]

    @pytest.mark.parametrize("message", ROUTINE_MESSAGES)
    def test_routine_message_approved(self, message):
        with patch("backend.pipeline.ethics_gate._get_classifier", return_value=ROUTINE_MODEL):
            result = evaluate(message)
        assert result["decision"] == "APPROVED", f"Expected APPROVED for: '{message}'"
        assert result["layer"] == "model"

    def test_approved_has_positive_confidence(self):
        with patch("backend.pipeline.ethics_gate._get_classifier", return_value=ROUTINE_MODEL):
            result = evaluate("I want to increase my 401k")
        assert result["confidence"] > 0.5


# =============================================================================
# TASK 2c: Test unclear context → AMBIGUOUS
# =============================================================================
class TestUnclearContext:

    UNCLEAR_MESSAGES = [
        "Not sure what to do",
        "Can you help me?",
        "I need some advice",
        "I don't know where to start",
    ]

    @pytest.mark.parametrize("message", UNCLEAR_MESSAGES)
    def test_unclear_message_ambiguous(self, message):
        with patch("backend.pipeline.ethics_gate._get_classifier", return_value=UNCLEAR_MODEL):
            result = evaluate(message)
        assert result["decision"] == "AMBIGUOUS", f"Expected AMBIGUOUS for: '{message}'"

    def test_vulnerable_below_threshold_is_ambiguous(self):
        """Vulnerable label below confidence threshold → AMBIGUOUS, not BLOCKED."""
        low_conf_vulnerable = mock_model(
            "this person is vulnerable or distressed",
            VULNERABILITY_THRESHOLD - 0.05,
        )
        with patch("backend.pipeline.ethics_gate._get_classifier", return_value=low_conf_vulnerable):
            result = evaluate("I'm feeling a bit unsure about my finances")
        assert result["decision"] == "AMBIGUOUS"


# =============================================================================
# TASK 2d: Verify confidence scores
# =============================================================================
class TestConfidenceScores:

    def test_keyword_block_confidence_is_1(self):
        result = evaluate("My father died yesterday")
        assert result["confidence"] == 1.0

    def test_model_approved_confidence_matches_mock(self):
        model = mock_model("this is a routine financial inquiry", 0.91)
        with patch("backend.pipeline.ethics_gate._get_classifier", return_value=model):
            result = evaluate("Tell me about index funds")
        assert abs(result["confidence"] - 0.91) < 0.001

    def test_model_blocked_confidence_matches_mock(self):
        model = mock_model("this person is vulnerable or distressed", 0.87)
        with patch("backend.pipeline.ethics_gate._get_classifier", return_value=model):
            result = evaluate("I've been struggling a lot recently")
        assert result["decision"] == "BLOCKED"
        assert abs(result["confidence"] - 0.87) < 0.001

    def test_confidence_always_between_0_and_1(self):
        messages = [
            ("passed away", None),
        ]
        for msg, _ in messages:
            result = evaluate(msg)
            assert 0.0 <= result["confidence"] <= 1.0, (
                f"confidence out of range for '{msg}': {result['confidence']}"
            )


# =============================================================================
# All HARD_BLOCK_KEYWORDS — parametrised sweep
# =============================================================================
class TestAllKeywords:

    @pytest.mark.parametrize("keyword", HARD_BLOCK_KEYWORDS)
    def test_keyword_exact_match_blocked(self, keyword):
        result = evaluate(keyword)
        assert result["decision"] == "BLOCKED"

    @pytest.mark.parametrize("keyword", HARD_BLOCK_KEYWORDS)
    def test_keyword_in_sentence_blocked(self, keyword):
        result = evaluate(f"I wanted to tell you that {keyword} happened recently.")
        assert result["decision"] == "BLOCKED"

    @pytest.mark.parametrize("keyword", HARD_BLOCK_KEYWORDS)
    def test_keyword_case_insensitive(self, keyword):
        result = evaluate(keyword.upper())
        assert result["decision"] == "BLOCKED"


# =============================================================================
# Edge Cases
# =============================================================================
class TestEdgeCases:

    def test_empty_string_ambiguous(self):
        assert evaluate("")["decision"] == "AMBIGUOUS"

    def test_whitespace_only_ambiguous(self):
        assert evaluate("   ")["decision"] == "AMBIGUOUS"

    def test_model_error_returns_ambiguous_not_approved(self):
        """Fail-safe: model errors must never silently APPROVE."""
        with patch("backend.pipeline.ethics_gate._get_classifier") as mock_get:
            mock_get.side_effect = RuntimeError("GPU out of memory")
            result = evaluate("Tell me about my account")
        assert result["decision"] == "AMBIGUOUS"
        assert result["reason"] == "model_error"

    def test_result_schema_complete(self):
        result = evaluate("passed away")
        for key in ("decision", "reason", "confidence", "layer", "raw"):
            assert key in result, f"Missing key: {key}"

    def test_keyword_priority_over_model(self):
        """Even if model would return APPROVED, keyword must BLOCK first."""
        with patch("backend.pipeline.ethics_gate._get_classifier") as mock_get:
            mock_get.return_value = ROUTINE_MODEL
            result = evaluate("My spouse died and I need to cancel the policy")
        assert result["decision"] == "BLOCKED"
        assert result["layer"] == "keyword"
        mock_get.assert_not_called()


# =============================================================================
# Blocked Responses — no persuasion language allowed
# =============================================================================
class TestBlockedResponses:

    PROHIBITED_PHRASES = [
        "consider upgrading",
        "great opportunity",
        "don't miss out",
        "recommend you",
        "special offer",
        "you should invest",
    ]

    ALL_BLOCKED_GATE_RESULTS = [
        {"decision": "BLOCKED", "reason": "keyword:passed away"},
        {"decision": "BLOCKED", "reason": "keyword:died"},
        {"decision": "BLOCKED", "reason": "keyword:suicide"},
        {"decision": "BLOCKED", "reason": "keyword:bankruptcy"},
        {"decision": "BLOCKED", "reason": "keyword:lost my job"},
        {"decision": "BLOCKED", "reason": "keyword:can't afford"},
        {"decision": "BLOCKED", "reason": "model:vulnerable_or_distressed"},
        {"decision": "AMBIGUOUS", "reason": "model:context_unclear"},
    ]

    @pytest.mark.parametrize("gate_result", ALL_BLOCKED_GATE_RESULTS)
    def test_no_sales_language_in_blocked_response(self, gate_result):
        response = get_blocked_response(gate_result).lower()
        for phrase in self.PROHIBITED_PHRASES:
            assert phrase not in response, (
                f"Prohibited phrase '{phrase}' found in response for {gate_result}"
            )

    def test_bereavement_response_contains_empathy(self):
        gate = {"decision": "BLOCKED", "reason": "keyword:passed away"}
        response = get_blocked_response(gate).lower()
        assert any(word in response for word in ["sorry", "loss", "difficult"])

    def test_suicide_response_contains_crisis_line(self):
        gate = {"decision": "BLOCKED", "reason": "keyword:suicide"}
        response = get_blocked_response(gate)
        assert "988" in response or "741741" in response

    def test_resolve_category_bereavement(self):
        gate = {"decision": "BLOCKED", "reason": "keyword:passed away"}
        assert resolve_category(gate) == BlockedCategory.BEREAVEMENT

    def test_resolve_category_model_detected(self):
        gate = {"decision": "BLOCKED", "reason": "model:vulnerable_or_distressed"}
        assert resolve_category(gate) == BlockedCategory.HIGH_RISK
