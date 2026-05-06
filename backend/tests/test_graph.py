"""
Integration test — LangGraph graph and routing layer.

Verifies that state flows correctly through the graph for all three gate
outcomes using mock nodes so the tests never touch real models or APIs.

Run:
    pytest backend/tests/test_graph.py -v
"""

import pytest
from unittest.mock import patch, MagicMock

from graph.routing import route_after_gate, route_after_critic
from graph.state import BankingPipelineState


# =============================================================================
# Helpers
# =============================================================================
def make_state(**overrides) -> BankingPipelineState:
    """Return a minimal valid BankingPipelineState with sensible defaults."""
    base: BankingPipelineState = {
        "message":               "test message",
        "session_id":            "test-session",
        "document_bytes":        None,
        "has_document":          False,
        "document_text":         None,
        "document_type":         None,
        "document_figures":      None,
        "document_doc_id":       None,
        "document_insights":     None,
        "emotion":               "neutral_or_calm",
        "intent":                "general_banking_inquiry",
        "situation":             "neutral_for_business",
        "classification_reasoning": None,
        "should_persuade":       None,
        "gate_decision":         "APPROVED",
        "gate_reason":           "model:routine_financial_inquiry",
        "gate_confidence":       0.92,
        "strategy_path":         None,
        "strategy_config":       None,
        "strategy_reasoning":    None,
        "response_draft":        None,
        "retrieved_docs":        None,
        "constraints":           None,
        "critic_score":          None,
        "critic_violations":     None,
        "critic_reasoning":      None,
        "critic_suggestions":    None,
        "critic_feedback":       None,
        "rewrite_count":         0,
        "final_response":        None,
        "debug_trace":           {},
    }
    base.update(overrides)
    return base


# =============================================================================
# Routing — after ethics gate
# =============================================================================
class TestRouteAfterGate:

    def test_blocked_routes_to_db_logger(self):
        state = make_state(gate_decision="BLOCKED")
        assert route_after_gate(state) == "db_logger"

    def test_approved_routes_to_generator(self):
        state = make_state(gate_decision="APPROVED")
        assert route_after_gate(state) == "generator"

    def test_ambiguous_routes_to_generator(self):
        state = make_state(gate_decision="AMBIGUOUS")
        assert route_after_gate(state) == "generator"

    def test_none_gate_defaults_to_generator(self):
        state = make_state(gate_decision=None)
        assert route_after_gate(state) == "generator"


# =============================================================================
# Routing — after critic
# =============================================================================
class TestRouteAfterCritic:

    def test_passing_score_routes_to_db_logger(self):
        state = make_state(critic_score=8.5, rewrite_count=0)
        assert route_after_critic(state) == "db_logger"

    def test_exact_threshold_routes_to_db_logger(self):
        state = make_state(critic_score=7.0, rewrite_count=0)
        assert route_after_critic(state) == "db_logger"

    def test_failing_score_no_rewrites_routes_to_generator(self):
        state = make_state(critic_score=5.0, rewrite_count=0)
        assert route_after_critic(state) == "generator"

    def test_failing_score_at_rewrite_limit_routes_to_db_logger(self):
        state = make_state(critic_score=4.0, rewrite_count=1)
        assert route_after_critic(state) == "db_logger"

    def test_none_score_defaults_to_pass(self):
        state = make_state(critic_score=None, rewrite_count=0)
        assert route_after_critic(state) == "db_logger"


# =============================================================================
# Graph — full state flow with mock nodes
# =============================================================================
MOCK_CLASSIFY = {
    "emotion": "anxiety_or_worry",
    "emotion_confidence": 0.85,
    "intent": "inquire_about_loan_terms",
    "intent_confidence": 0.78,
    "situation": "neutral_for_business",
    "situation_confidence": 0.71,
}

MOCK_GATE_APPROVED = {
    "decision": "APPROVED",
    "reason": "model:routine_financial_inquiry",
    "confidence": 0.91,
    "layer": "model",
    "raw": None,
}

MOCK_GATE_BLOCKED = {
    "decision": "BLOCKED",
    "reason": "keyword:passed away",
    "confidence": 1.0,
    "layer": "keyword",
    "raw": None,
}

MOCK_GATE_AMBIGUOUS = {
    "decision": "AMBIGUOUS",
    "reason": "model:context_unclear",
    "confidence": 0.72,
    "layer": "model",
    "raw": None,
}

MOCK_STRATEGY_CONFIG = {
    "name": "Social Proof",
    "principle": "peer reassurance",
    "tone": "empathetic",
    "compliant_framing": ["Many of our customers..."],
    "prohibited": ["guaranteed returns"],
    "directives": ["Be concise"],
}

MOCK_CRITIC_PASS = {
    "score": 8.5,
    "violations": [],
    "passed": True,
    "raw_classification": {},
}

MOCK_CRITIC_FAIL = {
    "score": 5.0,
    "violations": ["Prohibited phrase: 'guaranteed returns'"],
    "passed": False,
    "raw_classification": {},
}


def _mock_classify(_message):
    return MOCK_CLASSIFY


def _mock_gate_evaluate(_message):
    return MOCK_GATE_APPROVED


def _mock_select_strategy(_gate, _clf=None):
    return "soft_persuasion/social_proof"


def _mock_load_strategy(_path):
    return MOCK_STRATEGY_CONFIG


def _mock_generate(_message, _clf, _strategy, rewrite=False, **_kw):
    prefix = "[rewrite] " if rewrite else ""
    return f"{prefix}Here is our answer about loan terms."


def _mock_score_response(_response, _strategy, _gate):
    return MOCK_CRITIC_PASS


class TestGraphStateFlow:
    """Run the compiled graph with mock pipeline components."""

    @pytest.fixture(autouse=True)
    def _patch_pipeline(self):
        patches = [
            patch("graph.graph.clf_module.classify",     _mock_classify,         create=True),
            patch("graph.graph.ethics_gate.evaluate",    _mock_gate_evaluate,    create=True),
            patch("graph.graph.strat_module.select_strategy", _mock_select_strategy, create=True),
            patch("graph.graph.strat_module.load_strategy",   _mock_load_strategy,   create=True),
            patch("graph.graph.gen_module.generate",     _mock_generate,         create=True),
            patch("graph.graph.critic_module.score_response", _mock_score_response, create=True),
        ]
        # We patch the module-level imports inside node functions via sys.modules
        # use patch.object-on-the-module approach instead
        yield

    def _run_graph(self, message="What are your loan rates?", **overrides):
        """
        Run the graph by calling each node function directly in sequence,
        simulating what LangGraph does internally. This keeps the test
        independent of LangGraph internals while still verifying state flow.
        """
        from graph.graph import (
            entry_node,
            classifier_node,
            ethics_gate_node,
            generator_node,
            critic_node,
            db_logger_node,
        )

        state = make_state(message=message, **overrides)

        # Simulate sequential execution
        state.update(entry_node(state))
        state.update(classifier_node(state))
        state.update(ethics_gate_node(state))

        gate_next = route_after_gate(state)
        if gate_next == "generator":
            state.update(generator_node(state))
            state.update(critic_node(state))
            critic_next = route_after_critic(state)
            if critic_next == "generator":
                state.update(generator_node(state))
                state.update(critic_node(state))

        state.update(db_logger_node(state))
        return state

    def test_approved_flow_sets_final_response(self):
        with (
            patch("pipeline.classifier.classify", return_value=MOCK_CLASSIFY),
            patch("pipeline.ethics_gate.evaluate", return_value=MOCK_GATE_APPROVED),
            patch("pipeline.strategy.select_strategy", return_value="soft_persuasion/social_proof"),
            patch("pipeline.strategy.load_strategy", return_value=MOCK_STRATEGY_CONFIG),
            patch("pipeline.generator.generate", return_value="Here is our answer."),
            patch("pipeline.critic.score_response", return_value=MOCK_CRITIC_PASS),
        ):
            state = self._run_graph("What are your loan rates?")

        assert state["final_response"] is not None
        assert state["final_response"] != ""
        assert state["gate_decision"] == "APPROVED"

    def test_blocked_flow_skips_generator(self):
        with (
            patch("pipeline.classifier.classify", return_value=MOCK_CLASSIFY),
            patch("pipeline.ethics_gate.evaluate", return_value=MOCK_GATE_BLOCKED),
        ):
            from graph.graph import (
                entry_node, classifier_node, ethics_gate_node, db_logger_node,
            )
            state = make_state(message="My spouse passed away")
            state.update(entry_node(state))
            state.update(classifier_node(state))
            state.update(ethics_gate_node(state))

            # BLOCKED → db_logger (no generator call)
            assert route_after_gate(state) == "db_logger"

            state.update(db_logger_node(state))

        assert state["gate_decision"] == "BLOCKED"
        assert state["final_response"] is not None
        assert state["response_draft"] is None  # generator was never called

    def test_ambiguous_flow_routes_to_generator(self):
        from graph.graph import ethics_gate_node

        with patch("pipeline.ethics_gate.evaluate", return_value=MOCK_GATE_AMBIGUOUS):
            state = make_state()
            state.update(ethics_gate_node(state))

        assert state["gate_decision"] == "AMBIGUOUS"
        assert route_after_gate(state) == "generator"

    def test_rewrite_loop_increments_rewrite_count(self):
        """
        Failing critic on first attempt → route sends back to generator.
        The rewrite_count is incremented by generator_node on the SECOND call
        (when response_draft is already set), not by the critic.
        """
        with (
            patch("pipeline.strategy.select_strategy", return_value="soft_persuasion/social_proof"),
            patch("pipeline.strategy.load_strategy", return_value=MOCK_STRATEGY_CONFIG),
            patch("pipeline.generator.generate", return_value="bad response"),
            patch("pipeline.critic.score_response", return_value=MOCK_CRITIC_FAIL),
        ):
            from graph.graph import generator_node, critic_node

            state = make_state(gate_decision="APPROVED")

            # First generation: response_draft was None → rewrite_count stays 0
            state.update(generator_node(state))
            assert state["rewrite_count"] == 0

            state.update(critic_node(state))  # fails, rewrite_count unchanged
            assert state["rewrite_count"] == 0
            assert route_after_critic(state) == "generator"  # one rewrite allowed

            # Rewrite: response_draft is now set → generator increments rewrite_count
            state.update(generator_node(state))
            assert state["rewrite_count"] == 1

            state.update(critic_node(state))  # fails again
            assert route_after_critic(state) == "db_logger"  # max rewrites done

    def test_max_rewrite_forces_db_logger(self):
        """After rewrite_count reaches 1, critic failure must route to db_logger."""
        state = make_state(critic_score=3.0, rewrite_count=1)
        assert route_after_critic(state) == "db_logger"

    def test_debug_trace_populated(self):
        with (
            patch("pipeline.classifier.classify", return_value=MOCK_CLASSIFY),
            patch("pipeline.ethics_gate.evaluate", return_value=MOCK_GATE_APPROVED),
            patch("pipeline.strategy.select_strategy", return_value="soft_persuasion/social_proof"),
            patch("pipeline.strategy.load_strategy", return_value=MOCK_STRATEGY_CONFIG),
            patch("pipeline.generator.generate", return_value="A helpful response."),
            patch("pipeline.critic.score_response", return_value=MOCK_CRITIC_PASS),
        ):
            state = self._run_graph()

        trace = state.get("debug_trace") or {}
        assert "gate_decision" in trace
        assert "critic_score" in trace
        assert "strategy_path" in trace


# =============================================================================
# State schema completeness
# =============================================================================
class TestStateSchema:

    def test_all_required_keys_present(self):
        state = make_state()
        required = [
            "message", "session_id", "has_document",
            "gate_decision", "gate_reason", "gate_confidence",
            "emotion", "intent", "situation",
            "strategy_path", "strategy_config",
            "response_draft", "critic_score", "critic_violations",
            "rewrite_count", "final_response", "debug_trace",
        ]
        for key in required:
            assert key in state, f"Missing state key: {key}"

    def test_rewrite_count_starts_at_zero(self):
        from graph.graph import entry_node
        state = make_state()
        result = entry_node(state)
        assert result["rewrite_count"] == 0

    def test_has_document_set_from_bytes(self):
        from graph.graph import entry_node
        state = make_state(document_bytes=b"fake pdf content")
        result = entry_node(state)
        assert result["has_document"] is True

    def test_has_document_false_when_no_bytes(self):
        from graph.graph import entry_node
        state = make_state(document_bytes=None)
        result = entry_node(state)
        assert result["has_document"] is False


# =============================================================================
# Graph compilation smoke test
# =============================================================================
class TestGraphCompiles:

    def test_create_graph_returns_compiled_graph(self):
        from graph.graph import create_graph
        g = create_graph()
        assert g is not None

    def test_get_graph_returns_singleton(self):
        from graph import graph as graph_module
        graph_module._graph = None  # reset singleton
        g1 = graph_module.get_graph()
        g2 = graph_module.get_graph()
        assert g1 is g2
