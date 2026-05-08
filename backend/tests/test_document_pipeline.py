from unittest.mock import patch

from backend.agents.document_analysis_agent import calculate_banking_metrics, run_document_analysis
from backend.document.extractors import extract_banking_figures
from backend.document.ingestion import _chunk_text


def test_bank_statement_extraction_and_metrics():
    text = """
    Checking Statement
    Ending Balance: $1,250.25
    Average Daily Balance: $900.00
    Monthly Maintenance Fee $12.00
    Overdraft Fee $35.00
    NSF Fee $35.00
    Debit Grocery Mart $82.40
    Debit Grocery Mart $24.10
    """

    figures = extract_banking_figures(text, "bank_statement")
    metrics = calculate_banking_metrics(figures, "bank_statement")

    assert figures["current_balance"] == 1250.25
    assert figures["avg_balance"] == 900.0
    assert figures["total_fees"] == 82.0
    assert figures["overdraft_total"] == 70.0
    assert figures["overdraft_count"] == 2
    assert metrics["annualized_fees"] == 984.0
    assert metrics["overdraft_risk_score"] == 40


def test_credit_card_extraction_computes_utilization():
    text = """
    Credit Card Statement
    New Balance: $2,400.00
    Credit Limit: $6,000.00
    Purchase APR: 24.99%
    Minimum Payment Due: $72.00
    """

    figures = extract_banking_figures(text, "credit_card_statement")
    metrics = calculate_banking_metrics(figures, "credit_card_statement")

    assert figures["balance"] == 2400.0
    assert figures["credit_limit"] == 6000.0
    assert figures["utilization_pct"] == 40.0
    assert metrics["utilization_category"] == "fair"
    assert metrics["monthly_interest_cost"] == 49.98


def test_document_analysis_returns_grounded_insights_without_llm_or_db():
    state = {
        "has_document": True,
        "message": "How can I save on fees?",
        "document_doc_id": None,
        "document_type": "bank_statement",
        "document_figures": {
            "current_balance": 1250.25,
            "total_fees": 82.0,
            "overdraft_total": 70.0,
            "overdraft_count": 2,
        },
    }

    with patch.dict("os.environ", {"GOOGLE_API_KEY": ""}, clear=False):
        result = run_document_analysis(state)

    assert "document_insights" in result
    assert any("$82.00" in insight for insight in result["document_insights"])
    assert any("2 overdraft" in insight for insight in result["document_insights"])


def test_chunk_text_overlaps():
    chunks = _chunk_text(" ".join(str(i) for i in range(20)), chunk_size=8, overlap=2)

    assert chunks[0].split() == ["0", "1", "2", "3", "4", "5", "6", "7"]
    assert chunks[1].split()[:2] == ["6", "7"]
