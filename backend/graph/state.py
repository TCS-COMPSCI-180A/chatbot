"""
BankingPipelineState — shared state object passed through the LangGraph graph.

All nodes read from and write to this single state. LangGraph merges each
node's returned dict into the running state before passing it to the next node.

Follows Section 7 of updated_design.md, extended with per-node fields visible
in the Banking_Assistant_Diagram (classifier's should_persuade, critic's
suggestions/feedback, generator's constraints/retrieved_docs).
"""

from typing import TypedDict, Optional


class BankingPipelineState(TypedDict):

    # ── Input ─────────────────────────────────────────────────────────────────
    message: str
    session_id: str
    document_bytes: Optional[bytes]          # raw upload, None if no document
    conversation_history: Optional[list]     # previous messages for context

    # ── Document Processing ───────────────────────────────────────────────────
    has_document: bool
    document_text: Optional[str]             # full parsed text
    document_type: Optional[str]             # e.g. "bank_statement"
    document_figures: Optional[dict]         # key numbers extracted from doc
    document_doc_id: Optional[str]           # pgvector doc UUID
    document_insights: Optional[list]        # grounded observations for generator

    # ── Classifier Agent ─────────────────────────────────────────────────────
    emotion: Optional[str]                   # Plutchik label
    intent: Optional[str]                    # banking intent label
    situation: Optional[str]                 # business perspective
    classification_reasoning: Optional[str]  # LLM chain-of-thought
    should_persuade: Optional[bool]          # classifier's recommendation

    # ── Ethics Gate ──────────────────────────────────────────────────────────
    gate_decision: Optional[str]             # BLOCKED | APPROVED | AMBIGUOUS
    gate_reason: Optional[str]               # machine-readable reason code
    gate_confidence: Optional[float]         # 0.0–1.0

    # ── Strategy ─────────────────────────────────────────────────────────────
    strategy_path: Optional[str]             # e.g. "soft_persuasion/social_proof"
    strategy_config: Optional[dict]          # parsed YAML dict
    strategy_reasoning: Optional[str]

    # ── Generator Agent ──────────────────────────────────────────────────────
    response_draft: Optional[str]
    retrieved_docs: Optional[list]           # RAG chunks used (future use)
    constraints: Optional[list]              # active prohibited list

    # ── Critic Agent ─────────────────────────────────────────────────────────
    critic_score: Optional[float]            # 0.0–10.0
    critic_violations: Optional[list]
    critic_reasoning: Optional[str]
    critic_suggestions: Optional[list]       # improvement hints for rewrite
    critic_feedback: Optional[str]           # free-text feedback
    rewrite_count: int                       # enforced max: 1

    # ── Output ───────────────────────────────────────────────────────────────
    final_response: Optional[str]
    debug_trace: dict                        # full audit log, written to DB
