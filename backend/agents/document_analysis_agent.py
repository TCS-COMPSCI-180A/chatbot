"""
Document Analysis Agent — LangGraph node.

Runs when gate_decision == "APPROVED" and has_document == True.
Executes in parallel with the Classifier Agent.

Responsibilities:
  - Retrieve relevant document chunks for the user's query
  - Compute derived financial metrics from extracted figures
  - Look up current market rates for comparison
  - Produce a list of grounded, specific observations (document_insights)
    that the Generator Agent must cite in its response

Output written to BankingPipelineState:
  - document_insights: list[str]
"""

from __future__ import annotations


def run_document_analysis(state: dict) -> dict:
    """LangGraph node: analyse an uploaded document and produce grounded insights.

    Reads from state:
        message           (str)  — the user's current message
        document_doc_id   (str)  — UUID for chunk retrieval
        document_figures  (dict) — pre-extracted key figures from ingestion
        document_type     (str)  — document type label

    Writes to state:
        document_insights (list[str]) — specific, citable observations
                                        grounded in the customer's document

    Args:
        state: BankingPipelineState dict passed through the LangGraph graph.

    Returns:
        Partial state dict containing document_insights.
    """
    raise NotImplementedError
