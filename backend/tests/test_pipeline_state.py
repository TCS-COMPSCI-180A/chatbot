"""
test_pipeline_state.py — Tests for pipeline_state.py
backend/tests/test_pipeline_state.py

Tests all shared helpers: _safe_parse, _extract_usage, CollectiveState fields.

Run:
    pytest tests/test_pipeline_state.py -v
"""

import operator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from pipeline.pipeline_state import (
    CollectiveState,
    _extract_usage,
    _safe_parse,
)


# =============================================================================
# _safe_parse
# =============================================================================

class TestSafeParse:

    def test_valid_json(self):
        result = _safe_parse('{"emotion": "neutral_or_calm", "confidence": 0.9}')
        assert result["emotion"] == "neutral_or_calm"
        assert result["confidence"] == 0.9

    def test_empty_string_returns_empty_dict(self):
        assert _safe_parse("") == {}

    def test_none_like_whitespace_returns_empty_dict(self):
        assert _safe_parse("   ") == {}

    def test_json_wrapped_in_markdown_fences(self):
        """LLMs sometimes wrap JSON in ```json ... ```"""
        raw = '```json\n{"emotion": "anxiety_or_worry"}\n```'
        # _safe_parse uses brace extraction as fallback
        result = _safe_parse(raw)
        assert result.get("emotion") == "anxiety_or_worry"

    def test_json_with_leading_text(self):
        """LLM adds preamble before JSON."""
        raw = 'Here is the result:\n{"intent": "make_withdrawal"}'
        result = _safe_parse(raw)
        assert result.get("intent") == "make_withdrawal"

    def test_totally_invalid_returns_empty_dict(self):
        assert _safe_parse("this is not json at all") == {}

    def test_partial_json_no_closing_brace(self):
        assert _safe_parse('{"emotion": "calm"') == {}

    def test_nested_json(self):
        raw = '{"outer": {"inner": 1}}'
        result = _safe_parse(raw)
        assert result["outer"]["inner"] == 1

    def test_json_with_list(self):
        raw = '{"violations": ["aml_breach", "kyc_incomplete"]}'
        result = _safe_parse(raw)
        assert result["violations"] == ["aml_breach", "kyc_incomplete"]


# =============================================================================
# _extract_usage
# =============================================================================

class TestExtractUsage:

    def test_normal_usage_extraction(self):
        meta = SimpleNamespace(
            prompt_token_count=100,
            candidates_token_count=50,
            total_token_count=150,
        )
        response = SimpleNamespace(usage_metadata=meta)
        result = _extract_usage(response)
        assert result == {"prompt": 100, "completion": 50, "total": 150}

    def test_missing_usage_metadata_returns_zeros(self):
        response = SimpleNamespace()  # no usage_metadata attribute
        result = _extract_usage(response)
        assert result == {"prompt": 0, "completion": 0, "total": 0}

    def test_none_token_counts_become_zero(self):
        meta = SimpleNamespace(
            prompt_token_count=None,
            candidates_token_count=None,
            total_token_count=None,
        )
        response = SimpleNamespace(usage_metadata=meta)
        result = _extract_usage(response)
        assert result == {"prompt": 0, "completion": 0, "total": 0}

    def test_mock_response_with_no_metadata(self):
        response = MagicMock(spec=[])  # no attributes
        result = _extract_usage(response)
        assert result == {"prompt": 0, "completion": 0, "total": 0}


# =============================================================================
# CollectiveState  (structural checks)
# =============================================================================

class TestCollectiveState:

    def test_minimal_state_is_valid(self):
        state: CollectiveState = {
            "current_query": "hello",
            "trace_log":     [],
            "metadata":      {},
        }
        assert state["current_query"] == "hello"

    def test_trace_log_uses_operator_add(self):
        """
        Verify the Annotated reducer works for trace_log.
        LangGraph uses operator.add to merge trace_log entries.
        """
        a = [{"node": "classifier"}]
        b = [{"node": "ethics_gate"}]
        merged = operator.add(a, b)
        assert len(merged) == 2
        assert merged[0]["node"] == "classifier"
        assert merged[1]["node"] == "ethics_gate"

    def test_state_accepts_all_expected_fields(self):
        state: CollectiveState = {
            "session_id":         "s1",
            "user_id":            "u1",
            "current_query":      "test",
            "chat_history":       [],
            "route_decision":     "domain",
            "confidence":         0.9,
            "tools_used":         ["llm"],
            "reasoning":          "test reasoning",
            "status":             "classified",
            "ethics_decision":    "pass",
            "risk_level":         "low",
            "route_signal":       "allow",
            "generated_response": None,
            "critic_feedback":    None,
            "final_response":     None,
            "trace_log":          [],
            "metadata":           {},
        }
        assert state["route_decision"] == "domain"
        assert state["ethics_decision"] == "pass"
