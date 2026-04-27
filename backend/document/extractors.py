"""
Per-document-type extractors that pull key financial figures from raw text using regex.
"""

from __future__ import annotations

import re


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
    figures = {}

    # ending/available balance
    bal = re.search(r"(?:ending|available|closing)\s+balance[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if bal:
        figures["balance"] = _to_float(bal.group(1))

    # total fees
    fee = re.search(r"(?:total\s+)?fees?[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if fee:
        figures["total_fees"] = _to_float(fee.group(1))

    # overdraft flag + amount
    od = re.search(r"overdraft[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if od:
        figures["overdraft_amount"] = _to_float(od.group(1))
    else:
        figures["overdraft_amount"] = 0.0

    return figures


def _extract_loan_agreement(text: str) -> dict:
    """Pull principal, APR, payment, and term from a loan agreement."""
    figures = {}

    principal = re.search(r"(?:loan\s+amount|principal)[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if principal:
        figures["principal"] = _to_float(principal.group(1))

    apr = re.search(r"(?:annual\s+percentage\s+rate|apr)[:\s]+([\d.]+)\s*%?", text, re.IGNORECASE)
    if apr:
        figures["apr"] = float(apr.group(1))

    payment = re.search(r"(?:monthly\s+)?payment[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if payment:
        figures["monthly_payment"] = _to_float(payment.group(1))

    term = re.search(r"(?:loan\s+)?term[:\s]+(\d+)\s*(?:months?|years?)", text, re.IGNORECASE)
    if term:
        figures["term"] = term.group(1)

    return figures


def _extract_mortgage_statement(text: str) -> dict:
    """Pull balance, rate, payment, and escrow from a mortgage statement."""
    figures = {}

    balance = re.search(r"(?:outstanding|unpaid|principal)\s+balance[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if balance:
        figures["balance"] = _to_float(balance.group(1))

    rate = re.search(r"interest\s+rate[:\s]+([\d.]+)\s*%?", text, re.IGNORECASE)
    if rate:
        figures["interest_rate"] = float(rate.group(1))

    payment = re.search(r"(?:monthly\s+)?payment[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if payment:
        figures["monthly_payment"] = _to_float(payment.group(1))

    escrow = re.search(r"escrow[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if escrow:
        figures["escrow"] = _to_float(escrow.group(1))

    return figures


def _extract_credit_card_statement(text: str) -> dict:
    """Pull balance, APR, limit, and utilization from a credit card statement."""
    figures = {}

    balance = re.search(r"(?:current|statement|new)\s+balance[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if balance:
        figures["balance"] = _to_float(balance.group(1))

    apr = re.search(r"(?:purchase\s+)?apr[:\s]+([\d.]+)\s*%?", text, re.IGNORECASE)
    if apr:
        figures["apr"] = float(apr.group(1))

    limit = re.search(r"credit\s+limit[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if limit:
        figures["credit_limit"] = _to_float(limit.group(1))

    # compute utilization if we have both
    if "balance" in figures and "credit_limit" in figures and figures["credit_limit"] > 0:
        figures["utilization_pct"] = round(figures["balance"] / figures["credit_limit"] * 100, 1)

    return figures


def _extract_cd_savings_statement(text: str) -> dict:
    """Pull balance, APY, and maturity date from a CD or savings statement."""
    figures = {}

    balance = re.search(r"(?:account|current|available)\s+balance[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if balance:
        figures["balance"] = _to_float(balance.group(1))

    apy = re.search(r"apy[:\s]+([\d.]+)\s*%?", text, re.IGNORECASE)
    if apy:
        figures["apy"] = float(apy.group(1))

    maturity = re.search(r"maturity\s+date[:\s]+([\d/\-]+)", text, re.IGNORECASE)
    if maturity:
        figures["maturity_date"] = maturity.group(1)

    return figures


def _extract_credit_report(text: str) -> dict:
    """Pull FICO score, utilization, and derogatory marks from a credit report."""
    figures = {}

    # FICO / credit score
    score = re.search(r"(?:fico|credit)\s+score[:\s]+(\d{3})", text, re.IGNORECASE)
    if score:
        figures["credit_score"] = int(score.group(1))

    utilization = re.search(r"(?:credit\s+)?utilization[:\s]+([\d.]+)\s*%?", text, re.IGNORECASE)
    if utilization:
        figures["utilization_pct"] = float(utilization.group(1))

    # count derogatory marks (late payments, collections, etc.)
    derogatory = re.findall(r"(?:derogatory|late\s+payment|collection|charge.?off)", text, re.IGNORECASE)
    figures["derogatory_marks"] = len(derogatory)

    return figures


# --- helpers ---

def _to_float(value: str) -> float:
    """Strip commas and cast to float."""
    return float(value.replace(",", ""))
