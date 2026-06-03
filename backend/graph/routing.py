"""
Routing functions for LangGraph conditional edges.

route_after_gate  — decides what happens after the Ethics State Agent runs.
route_after_critic — decides whether to rewrite or finalize after the Critic.

Following Banking_Assistant_Diagram:
  BLOCKED  → db_logger   (pre-defined empathetic response, no LLM generation)
  APPROVED / AMBIGUOUS → generator

After critic:
  score ≥ 7.0 OR rewrite_count ≥ 1  → db_logger  (finalize)
  score < 7.0 AND rewrite_count == 0 → generator  (one rewrite allowed)
"""

from graph.state import BankingPipelineState


def route_after_gate(state: BankingPipelineState) -> str:
    """
    Called after ethics_gate node. Returns the name of the next node.

    BLOCKED  → "db_logger"  (compassionate canned response already set in state)
    APPROVED → "generator"
    AMBIGUOUS → "generator" (ambiguous strategy will be selected inside generator)
    """
    gate_decision = state.get("gate_decision") or "APPROVED"
    if gate_decision == "BLOCKED":
        return "db_logger"
    return "generator"


def route_after_critic(state: BankingPipelineState) -> str:
    """
    Called after critic node. Returns the name of the next node.

    rewrite_count tracks how many rewrites the generator has COMPLETED
    (incremented inside generator_node on its 2nd+ call, not by the critic).

    Passes if score ≥ 7.0 (design-spec threshold).
    Allows exactly one rewrite: once rewrite_count reaches 1 we force-pass.
    """
    score = state.get("critic_score")
    if score is None:
        score = 10.0

    rewrite_count = state.get("rewrite_count") or 0

    if score >= 7.0:
        return "db_logger"
    if rewrite_count >= 1:
        return "db_logger"   # one rewrite already done — force pass
    return "generator"       # trigger the one allowed rewrite
