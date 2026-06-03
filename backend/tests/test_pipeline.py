"""
test_pipeline.py — Integration tests for the full LangGraph pipeline
backend/tests/test_pipeline.py

Both classifier and ethics_gate do `from google import genai` and call
`genai.Client(...)`. Since they share the same genai module, we patch
`google.genai.Client` once and use side_effect to return different mock
clients per call (first call = classifier, second call = ethics gate).

Run:
    pytest tests/test_pipeline.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from conftest import json_response, make_empty_response


# =============================================================================
# HELPERS
# =============================================================================

def _merge(original: dict, node_output: dict) -> dict:
    """Mimics LangGraph state merge: trace_log uses operator.add, rest last-writer-wins."""
    merged = dict(original)
    for k, v in node_output.items():
        if k == "trace_log":
            merged["trace_log"] = merged.get("trace_log", []) + v
        elif k == "metadata" and isinstance(v, dict):
            sanitized = {}
            for mk, mv in v.items():
                if isinstance(mv, dict):
                    sanitized[mk] = {
                        sk: (sv if isinstance(sv, (str, int, float, bool, type(None))) else 0)
                        for sk, sv in mv.items()
                    }
                else:
                    sanitized[mk] = mv
            merged[k] = sanitized
        else:
            merged[k] = v
    return merged


def _make_clf_client(emotion, intent, situation, confidence=0.9):
    """Classifier mock client: returns canned LLM response."""
    m = MagicMock()
    m.models.generate_content.return_value = json_response({
        "emotion": emotion, "intent": intent, "situation": situation,
        "confidence": confidence, "reasoning": "test",
    })
    return m


def _make_eg_client(decision, risk="low"):
    """Ethics gate mock client: returns canned LLM response."""
    m = MagicMock()
    m.models.generate_content.return_value = json_response({
        "ethics_decision": decision, "risk_level": risk,
        "reasoning": "test", "violations": [], "tools_used": [],
    })
    return m


def _make_eg_client_fail():
    """Ethics gate mock client that raises on generate_content."""
    m = MagicMock()
    m.models.generate_content.side_effect = Exception("API down")
    return m


def _run_pipeline(base_state, clf_client, eg_client):
    """
    Run classifier then ethics_gate with separate mock clients.
    Patches google.genai.Client with side_effect=[clf_client, eg_client]
    so the first instantiation goes to the classifier and second to the gate.
    """
    from pipeline.classifier  import classifier_node
    from pipeline.ethics_gate import ethics_gate_node

    with patch("google.genai.Client", side_effect=[clf_client, eg_client]):
        clf_out   = classifier_node(base_state)
        after_clf = _merge(base_state, clf_out)
        eg_out    = ethics_gate_node(after_clf)
        final     = _merge(after_clf, eg_out)

    return clf_out, after_clf, eg_out, final


# =============================================================================
# APPROVED PATH
# =============================================================================

class TestApprovedPath:

    def test_approved_path_end_to_end(self, base_state):
        clf_client = _make_clf_client("neutral_or_calm", "make_withdrawal", "neutral_for_business")
        eg_client  = _make_eg_client("pass")

        _, _, _, final = _run_pipeline(base_state, clf_client, eg_client)

        assert final["route_decision"]  == "domain"
        assert final["ethics_decision"] == "pass"
        assert final["route_signal"]    == "allow"

    def test_trace_log_has_two_entries(self, base_state):
        clf_client = _make_clf_client("neutral_or_calm", "make_withdrawal", "neutral_for_business")
        eg_client  = _make_eg_client("pass")

        _, _, _, final = _run_pipeline(base_state, clf_client, eg_client)

        assert len(final["trace_log"]) == 2
        nodes = [e["node"] for e in final["trace_log"]]
        assert "classifier"  in nodes
        assert "ethics_gate" in nodes

    def test_metadata_has_both_subkeys(self, base_state):
        clf_client = _make_clf_client("neutral_or_calm", "make_withdrawal", "neutral_for_business")
        eg_client  = _make_eg_client("pass")

        _, _, _, final = _run_pipeline(base_state, clf_client, eg_client)

        assert "classifier"  in final["metadata"]
        assert "ethics_gate" in final["metadata"]


# =============================================================================
# BLOCKED PATH (keyword)
# =============================================================================

class TestBlockedPath:

    def test_keyword_block_skips_ethics_gate_llm(self, keyword_block_state):
        """Keyword block fires before any LLM call — only classifier needs a mock."""
        from pipeline.classifier  import classifier_node
        from pipeline.ethics_gate import ethics_gate_node

        clf_client = _make_clf_client("sadness_or_grief", "make_withdrawal", "negative_for_business")

        with patch("google.genai.Client", return_value=clf_client) as mock_cls:
            clf_out   = classifier_node(keyword_block_state)
            after_clf = _merge(keyword_block_state, clf_out)
            call_count_before = mock_cls.call_count
            eg_out    = ethics_gate_node(after_clf)
            # ethics gate should not have created a new client
            assert mock_cls.call_count == call_count_before

        assert eg_out["ethics_decision"] == "blocked"
        assert eg_out["route_signal"]    == "block"

    def test_blocked_path_trace_log_has_two_entries(self, keyword_block_state):
        from pipeline.classifier  import classifier_node
        from pipeline.ethics_gate import ethics_gate_node

        clf_client = _make_clf_client("sadness_or_grief", "make_withdrawal", "negative_for_business")

        with patch("google.genai.Client", return_value=clf_client):
            clf_out   = classifier_node(keyword_block_state)
            after_clf = _merge(keyword_block_state, clf_out)
            eg_out    = ethics_gate_node(after_clf)
            final     = _merge(after_clf, eg_out)

        assert len(final["trace_log"]) == 2


# =============================================================================
# DISTRESS PATH
# =============================================================================

class TestDistressPath:

    def test_distress_routes_ethical_then_blocked(self, distress_state):
        clf_client = _make_clf_client("anxiety_or_worry", "make_withdrawal", "negative_for_business", 0.88)
        eg_client  = _make_eg_client("blocked", "high")

        _, _, _, final = _run_pipeline(distress_state, clf_client, eg_client)

        assert final["route_decision"]  == "ethical"
        assert final["ethics_decision"] == "blocked"
        assert final["route_signal"]    == "block"


# =============================================================================
# FAILURE RESILIENCE
# =============================================================================

class TestFailureResilience:

    def test_classifier_llm_failure_still_produces_valid_state(self, base_state):
        from pipeline.classifier import classifier_node

        clf_client = MagicMock()
        clf_client.models.generate_content.return_value = make_empty_response()

        with patch("google.genai.Client", return_value=clf_client):
            result = classifier_node(base_state)

        assert "route_decision" in result
        assert "trace_log"      in result
        assert "status"         in result

    def test_ethics_gate_llm_failure_defaults_to_ambiguous(self, base_state):
        clf_client = _make_clf_client("neutral_or_calm", "make_withdrawal", "neutral_for_business")
        eg_client  = _make_eg_client_fail()

        _, after_clf, eg_out, _ = _run_pipeline(base_state, clf_client, eg_client)

        assert eg_out["ethics_decision"] == "ambiguous"
        assert eg_out["route_signal"]    == "human"

    def test_pipeline_always_has_two_trace_entries_even_on_errors(self, base_state):
        clf_client = MagicMock()
        clf_client.models.generate_content.return_value = make_empty_response()
        eg_client  = MagicMock()
        eg_client.models.generate_content.return_value = make_empty_response()

        _, _, _, final = _run_pipeline(base_state, clf_client, eg_client)

        assert len(final["trace_log"]) == 2


# =============================================================================
# STATE IMMUTABILITY
# =============================================================================

class TestStateImmutability:

    def test_classifier_does_not_mutate_input(self, base_state):
        from pipeline.classifier import classifier_node

        clf_client = _make_clf_client("neutral_or_calm", "make_withdrawal", "neutral_for_business")
        original_trace = list(base_state["trace_log"])
        original_meta  = dict(base_state["metadata"])

        with patch("google.genai.Client", return_value=clf_client):
            classifier_node(base_state)

        assert base_state["trace_log"] == original_trace
        assert base_state["metadata"]  == original_meta

    def test_ethics_gate_does_not_mutate_input(self, keyword_block_state):
        from pipeline.ethics_gate import ethics_gate_node

        original_trace = list(keyword_block_state["trace_log"])
        original_meta  = dict(keyword_block_state["metadata"])

        ethics_gate_node(keyword_block_state)

        assert keyword_block_state["trace_log"] == original_trace
        assert keyword_block_state["metadata"]  == original_meta

    def test_prior_trace_entries_preserved(self):
        prior_entry = {"node": "entry", "timestamp": 0.0, "status": "entry_complete"}
        state = {
            "session_id":    "s1",
            "current_query": "test",
            "chat_history":  [],
            "trace_log":     [prior_entry],
            "metadata":      {},
        }

        clf_client = _make_clf_client("neutral_or_calm", "make_withdrawal", "neutral_for_business")
        eg_client  = _make_eg_client("pass")

        _, _, _, final = _run_pipeline(state, clf_client, eg_client)

        nodes = [e["node"] for e in final["trace_log"]]
        assert "entry"       in nodes
        assert "classifier"  in nodes
        assert "ethics_gate" in nodes