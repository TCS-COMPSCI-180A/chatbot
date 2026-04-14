"""
Banking document figure extractors.

Pulls structured key figures from raw document text on a per-doc-type basis.
Uses regex patterns as the primary extraction method, with an LLM fallback
for fields that are inconsistently formatted across issuers.
"""

from __future__ import annotations


def extract_banking_figures(text: str, doc_type: str) -> dict:
    """Extract structured financial figures from document text.

    Dispatches to a doc-type-specific extractor based on doc_type.
    Returns an empty dict for unrecognised doc types rather than raising.

    Args:
        text:     Raw text of the document (from parse_pdf_document or OCR).
        doc_type: Document type string returned by classify_banking_document.
                  Expected values:
                    bank_statement | loan_agreement | mortgage_statement |
                    credit_card_statement | cd_savings_statement | credit_report

    Returns:
        Dict of extracted figures. Keys vary by doc_type:

        bank_statement:
            current_balance, avg_balance, total_fees, overdraft_count,
            overdraft_total, top_merchants (list)

        loan_agreement:
            principal, apr, monthly_payment, term_months,
            remaining_balance, prepayment_penalty

        mortgage_statement:
            principal_balance, interest_rate, monthly_payment,
            escrow_balance, payoff_amount

        credit_card_statement:
            balance, apr, min_payment, credit_limit,
            utilization_pct, statement_date

        cd_savings_statement:
            balance, apy, maturity_date, interest_earned

        credit_report:
            fico_score, utilization_pct, derogatory_marks
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Private per-doc-type extractors (called by extract_banking_figures)
# ---------------------------------------------------------------------------

def _extract_bank_statement(text: str) -> dict:
    """Extract figures from a bank statement."""
    raise NotImplementedError


def _extract_loan_agreement(text: str) -> dict:
    """Extract figures from a loan agreement."""
    raise NotImplementedError


def _extract_mortgage_statement(text: str) -> dict:
    """Extract figures from a mortgage statement."""
    raise NotImplementedError


def _extract_credit_card_statement(text: str) -> dict:
    """Extract figures from a credit card statement."""
    raise NotImplementedError


def _extract_cd_savings_statement(text: str) -> dict:
    """Extract figures from a CD or savings statement."""
    raise NotImplementedError


def _extract_credit_report(text: str) -> dict:
    """Extract figures from a credit report."""
    raise NotImplementedError
