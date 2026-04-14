"""
Per-document-type extractors that pull key financial figures from raw text using regex.
"""

from __future__ import annotations


def extract_banking_figures(text: str, doc_type: str) -> dict:
    """Dispatch to the right extractor based on document type and return key figures."""
    extractors = {
        "bank_statement":        _extract_bank_statement,
        "loan_agreement":        _extract_loan_agreement,
        "mortgage_statement":    _extract_mortgage_statement,
        "credit_card_statement": _extract_credit_card_statement,
        "cd_savings_statement":  _extract_cd_savings_statement,
        "credit_report":         _extract_credit_report,
    }

    extractor = extractors.get(doc_type)

    # unknown or unhandled doc type — return empty, pipeline handles this gracefully
    if extractor is None:
        return {}

    return extractor(text)


# --- private extractors, one per doc type ---

def _extract_bank_statement(text: str) -> dict:
    """Pull balance, fees, and overdraft info from a bank statement."""
    raise NotImplementedError


def _extract_loan_agreement(text: str) -> dict:
    """Pull principal, APR, payment, and term from a loan agreement."""
    raise NotImplementedError


def _extract_mortgage_statement(text: str) -> dict:
    """Pull balance, rate, payment, and escrow from a mortgage statement."""
    raise NotImplementedError


def _extract_credit_card_statement(text: str) -> dict:
    """Pull balance, APR, limit, and utilization from a credit card statement."""
    raise NotImplementedError


def _extract_cd_savings_statement(text: str) -> dict:
    """Pull balance, APY, and maturity date from a CD or savings statement."""
    raise NotImplementedError


def _extract_credit_report(text: str) -> dict:
    """Pull FICO score, utilization, and derogatory marks from a credit report."""
    raise NotImplementedError
