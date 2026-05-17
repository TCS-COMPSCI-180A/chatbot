"""
test_classifier.py — Tests for pipeline/classifier.py
backend/tests/test_classifier.py

Covers:
  - Pure unit tests (_decide_route, _execute_domain_lookup, _format_chat_history)
  - classify() with mocked Gemini (no real API calls)
  - classifier_node() LangGraph node behaviour
  - Edge cases: empty input, no candidates, malformed JSON, tool calls

Run:
    pytest tests/test_classifier.py -v
"""

import json
import sys
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))  # ← add this

from pipeline.classifier import (
    _decide_route,
    _execute_domain_lookup,
    _format_chat_history,
    classifier_node,
    _DOMAIN_INTENTS,
    _DISTRESS_EMOTIONS,
)
from conftest import (
    json_response,
    make_empty_response,
    make_gemini_response,
    make_text_part,
    make_tool_call_part,
)


# =============================================================================
# PURE UNIT TESTS — no mocking needed
# =============================================================================

class TestDecideRoute:

    def test_distress_emotion_routes_ethical(self):
        for emotion in _DISTRESS_EMOTIONS:
            assert _decide_route(emotion, "general_inquiry", "neutral_for_business") == "ethical"

    def test_negative_situation_routes_ethical(self):
        assert _decide_route("neutral_or_calm", "make_withdrawal", "negative_for_business") == "ethical"

    def test_domain_intent_routes_domain(self):
        assert _decide_route("neutral_or_calm", "make_withdrawal", "neutral_for_business") == "domain"

    def test_unknown_intent_routes_general(self):
        assert _decide_route("neutral_or_calm", "general_inquiry", "neutral_for_business") == "general"

    def test_distress_takes_priority_over_domain(self):
        """Distress emotion should override even a known domain intent."""
        assert _decide_route("anxiety_or_worry", "make_withdrawal", "neutral_for_business") == "ethical"

    def test_negative_situation_takes_priority_over_domain(self):
        assert _decide_route("neutral_or_calm", "seek_advice", "negative_for_business") == "ethical"

    def test_all_domain_intents_route_domain(self):
        for intent in _DOMAIN_INTENTS:
            route = _decide_route("neutral_or_calm", intent, "neutral_for_business")
            assert route == "domain", f"Expected domain for intent={intent}, got {route}"

    def test_positive_situation_with_domain_intent_routes_domain(self):
        assert _decide_route("joy_or_contentment", "purchase_new_policy", "positive_for_business") == "domain"

    def test_general_fallback(self):
        assert _decide_route("neutral_or_calm", "general_inquiry", "neutral_for_business") == "general"


class TestExecuteDomainLookup:

    def test_known_intent_returns_true(self):
        result = _execute_domain_lookup("make_withdrawal")
        assert result["is_domain"] is True
        assert result["category"] == "financial_action"

    def test_unknown_intent_returns_false(self):
        result = _execute_domain_lookup("ask_about_weather")
        assert result["is_domain"] is False
        assert result["category"] is None

    def test_empty_string_returns_false(self):
        result = _execute_domain_lookup("")
        assert result["is_domain"] is False

    def test_all_domain_intents_return_true(self):
        for intent in _DOMAIN_INTENTS:
            result = _execute_domain_lookup(intent)
            assert result["is_domain"] is True, f"Expected True for {intent}"


class TestFormatChatHistory:

    def test_empty_history_returns_empty_string(self):
        assert _format_chat_history([]) == ""

    def test_formats_messages_correctly(self):
        history = [
            {"role": "user",      "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = _format_chat_history(history)
        assert "<chat_history>" in result
        assert "USER: Hello" in result
        assert "ASSISTANT: Hi there" in result
        assert "</chat_history>" in result

    def test_truncates_to_last_10_messages(self):
        history = [{"role": "user", "content": f"msg {i}"} for i in range(15)]
        result = _format_chat_history(history)
        assert "msg 14" in result   # last message included
        assert "msg 0"  not in result  # oldest dropped

    def test_handles_missing_role_key(self):
        history = [{"content": "no role here"}]
        result = _format_chat_history(history)
        assert "UNKNOWN:" in result


# =============================================================================
# classify() WITH MOCKED GEMINI
# =============================================================================

class TestClassify:

    @patch("pipeline.classifier.genai.Client")
    def test_happy_path_domain_route(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = json_response({
            "emotion":    "neutral_or_calm",
            "intent":     "make_withdrawal",
            "situation":  "neutral_for_business",
            "confidence": 0.92,
            "reasoning":  "routine withdrawal request",
        })

        from pipeline.classifier import classify
        result = classify("I want to withdraw $500")

        assert result["route_decision"] == "domain"
        assert result["emotion"]        == "neutral_or_calm"
        assert result["intent"]         == "make_withdrawal"
        assert result["confidence"]     == 0.92
        assert "llm_signal_classifier" in result["tools_used"]

    @patch("pipeline.classifier.genai.Client")
    def test_distress_routes_ethical(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = json_response({
            "emotion":    "anxiety_or_worry",
            "intent":     "make_withdrawal",
            "situation":  "negative_for_business",
            "confidence": 0.88,
            "reasoning":  "user appears distressed",
        })

        from pipeline.classifier import classify
        result = classify("I'm so worried, I need to take out all my money")

        assert result["route_decision"] == "ethical"

    @patch("pipeline.classifier.genai.Client")
    def test_no_candidates_returns_error_result(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = make_empty_response()

        from pipeline.classifier import classify
        result = classify("test message")

        assert result["route_decision"] == "general"
        assert "error" in result

    @patch("pipeline.classifier.genai.Client")
    def test_malformed_json_uses_defaults(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = make_gemini_response([
            make_text_part("this is not json at all")
        ])

        from pipeline.classifier import classify
        result = classify("some message")

        # Should fall back to defaults, not crash
        assert result["emotion"]        == "neutral_or_calm"
        assert result["intent"]         == "general_inquiry"
        assert result["route_decision"] in {"general", "domain", "ethical"}

    @patch("pipeline.classifier.genai.Client")
    def test_tool_call_domain_lookup(self, mock_client_cls):
        """LLM calls domain_lookup tool, then returns JSON on second call."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        tool_response = make_gemini_response([
            make_tool_call_part("domain_lookup", {"intent": "make_withdrawal"})
        ])
        final_response = json_response({
            "emotion":    "neutral_or_calm",
            "intent":     "make_withdrawal",
            "situation":  "neutral_for_business",
            "confidence": 0.85,
            "reasoning":  "confirmed domain intent via tool",
        })
        mock_client.models.generate_content.side_effect = [tool_response, final_response]

        from pipeline.classifier import classify
        result = classify("I want to withdraw money")

        assert result["route_decision"] == "domain"
        assert "tool:domain_lookup" in result["tools_used"]

    @patch("pipeline.classifier.genai.Client")
    def test_with_chat_history(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = json_response({
            "emotion":    "trust_or_acceptance",
            "intent":     "seek_advice",
            "situation":  "neutral_for_business",
            "confidence": 0.9,
            "reasoning":  "advice seeking with prior context",
        })

        from pipeline.classifier import classify
        result = classify(
            "What about my pension options?",
            chat_history=[
                {"role": "user",      "content": "I'm planning for retirement"},
                {"role": "assistant", "content": "Great, let me help"},
            ]
        )

        assert result["route_decision"] == "domain"
        # Verify history was included in the prompt
        call_args = mock_client.models.generate_content.call_args
        contents  = call_args[1]["contents"] if "contents" in call_args[1] else call_args[0][1]
        prompt_text = contents[0].parts[0].text
        assert "planning for retirement" in prompt_text

    @patch("pipeline.classifier.genai.Client")
    def test_general_fallback_for_unknown_intent(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = json_response({
            "emotion":    "neutral_or_calm",
            "intent":     "general_inquiry",
            "situation":  "neutral_for_business",
            "confidence": 0.7,
            "reasoning":  "non-financial query",
        })

        from pipeline.classifier import classify
        result = classify("What are your opening hours?")

        assert result["route_decision"] == "general"


# =============================================================================
# classifier_node() LANGGRAPH NODE
# =============================================================================

class TestClassifierNode:

    @patch("pipeline.classifier.genai.Client")
    def test_node_returns_correct_keys(self, mock_client_cls, base_state):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = json_response({
            "emotion": "neutral_or_calm", "intent": "seek_advice",
            "situation": "neutral_for_business", "confidence": 0.9, "reasoning": "test",
        })

        result = classifier_node(base_state)

        assert "route_decision" in result
        assert "confidence"     in result
        assert "status"         in result
        assert "trace_log"      in result
        assert "metadata"       in result

    @patch("pipeline.classifier.genai.Client")
    def test_node_status_is_classified(self, mock_client_cls, base_state):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = json_response({
            "emotion": "neutral_or_calm", "intent": "seek_advice",
            "situation": "neutral_for_business", "confidence": 0.9, "reasoning": "ok",
        })

        result = classifier_node(base_state)
        assert result["status"] == "classified"

    def test_empty_input_returns_error_status(self, empty_state):
        result = classifier_node(empty_state)
        assert result["status"]         == "error"
        assert result["route_decision"] == "general"
        assert result["confidence"]     == 0.0

    def test_empty_input_still_has_trace_log(self, empty_state):
        result = classifier_node(empty_state)
        assert len(result["trace_log"]) == 1
        assert result["trace_log"][0]["node"] == "classifier"

    @patch("pipeline.classifier.genai.Client")
    def test_trace_log_has_single_entry(self, mock_client_cls, base_state):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = json_response({
            "emotion": "neutral_or_calm", "intent": "seek_advice",
            "situation": "neutral_for_business", "confidence": 0.9, "reasoning": "ok",
        })

        result = classifier_node(base_state)
        assert len(result["trace_log"]) == 1
        assert result["trace_log"][0]["node"] == "classifier"

    @patch("pipeline.classifier.genai.Client")
    def test_metadata_has_classifier_subkey(self, mock_client_cls, base_state):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = json_response({
            "emotion": "neutral_or_calm", "intent": "seek_advice",
            "situation": "neutral_for_business", "confidence": 0.9, "reasoning": "ok",
        })

        result = classifier_node(base_state)
        assert "classifier" in result["metadata"]
        assert "latency_ms" in result["metadata"]["classifier"]

    @patch("pipeline.classifier.genai.Client")
    def test_node_does_not_write_disallowed_keys(self, mock_client_cls, base_state):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = json_response({
            "emotion": "neutral_or_calm", "intent": "seek_advice",
            "situation": "neutral_for_business", "confidence": 0.9, "reasoning": "ok",
        })

        result = classifier_node(base_state)

        # These keys belong to other nodes — classifier must not write them
        assert "ethics_decision"    not in result
        assert "route_signal"       not in result
        assert "generated_response" not in result
        assert "final_response"     not in result

    @patch("pipeline.classifier.genai.Client")
    def test_node_preserves_existing_metadata(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = json_response({
            "emotion": "neutral_or_calm", "intent": "seek_advice",
            "situation": "neutral_for_business", "confidence": 0.9, "reasoning": "ok",
        })

        state = {
            "current_query": "test",
            "chat_history":  [],
            "trace_log":     [],
            "metadata":      {"entry": {"session_started": True}},
        }

        result = classifier_node(state)
        # classifier adds its own key but must not remove entry's key
        assert "entry"      in result["metadata"]
        assert "classifier" in result["metadata"]

    def test_node_does_not_mutate_input_state(self, base_state):
        original_trace = list(base_state["trace_log"])
        original_meta  = dict(base_state["metadata"])

        # even without a real API call (empty query), state should not be mutated
        state = {**base_state, "current_query": ""}
        classifier_node(state)

        assert state["trace_log"] == original_trace
        assert state["metadata"]  == original_meta
