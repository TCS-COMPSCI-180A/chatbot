"""
pipeline.py — LangGraph Graph Assembly
backend/pipeline/pipeline.py

Wires all nodes following the architecture diagram:
  Entry → Classifier → Ethics Gate → Generator / Human Review → Critic → DB Logger

USAGE
------
    from pipeline.pipeline import compiled_graph

    result = compiled_graph.invoke({
        "session_id":    "sess-001",
        "user_id":       "user-123",
        "current_query": "I want to withdraw all my savings",
        "chat_history":  [],
        "trace_log":     [],
        "metadata":      {},
    })

    print(result["route_decision"])    # general | domain | ethical
    print(result["ethics_decision"])   # pass | blocked | ambiguous
    print(result["route_signal"])      # allow | block | human
    print(result["final_response"])
    print(result["trace_log"])
"""

from __future__ import annotations

from pipeline.pipeline_state import CollectiveState
from pipeline.classifier  import classifier_node
from pipeline.ethics_gate import ethics_gate_node, route_after_ethics


# =========================================================
# STUB NODES  (teammates implement these)
# =========================================================

def entry_node(state: CollectiveState) -> dict:
    """Validates input, initialises state, appends user message to chat_history."""
    return {
        "status": "entry_complete",
        "chat_history": list(state.get("chat_history", [])) + [
            {"role": "user", "content": state.get("current_query", "")}
        ],
    }


def generator_node(state: CollectiveState) -> dict:
    """Generates response via Gemini + selected strategy. Teammate implements."""
    ethics = state.get("ethics_decision", "pass")
    if ethics == "blocked":
        return {
            "generated_response": "I'm sorry, I'm unable to assist with that request.",
            "status": "generated",
        }
    return {
        "generated_response": f"[Generator response for: {state.get('current_query', '')}]",
        "status": "generated",
    }


def human_review_node(state: CollectiveState) -> dict:
    """Routes ambiguous queries to human reviewer. Teammate implements."""
    return {"status": "reviewed"}


def critic_node(state: CollectiveState) -> dict:
    """Critiques generated response, rewrites once if needed. Teammate implements."""
    return {
        "critic_feedback": {
            "score": 10.0, "violations": [], "passed": True, "revised_response": None,
        },
        "status": "reviewed",
    }


def db_logger_node(state: CollectiveState) -> dict:
    """Persists conversation and decision trace to PostgreSQL. Teammate implements."""
    return {
        "final_response": state.get("generated_response"),
        "status": "logged",
    }


# =========================================================
# GRAPH ASSEMBLY
# =========================================================

def build_graph():
    from langgraph.graph import StateGraph

    graph = StateGraph(CollectiveState)

    graph.add_node("entry",        entry_node)
    graph.add_node("classifier",   classifier_node)
    graph.add_node("ethics_gate",  ethics_gate_node)
    graph.add_node("generator",    generator_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("critic",       critic_node)
    graph.add_node("db_logger",    db_logger_node)

    graph.add_edge("entry",      "classifier")
    graph.add_edge("classifier", "ethics_gate")

    graph.add_conditional_edges(
        "ethics_gate",
        route_after_ethics,
        {
            "allow": "generator",      # pass     → generate response
            "block": "generator",      # blocked  → generator handles refusal
            "human": "human_review",   # ambiguous → human review
        }
    )

    graph.add_edge("human_review", "generator")
    graph.add_edge("generator",    "critic")
    graph.add_edge("critic",       "db_logger")

    graph.set_entry_point("entry")
    return graph.compile()


try:
    compiled_graph = build_graph()
except ImportError:
    compiled_graph = None
