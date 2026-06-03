"""Per-document-type extractors that pull key banking figures from raw text."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any


Money = int | float


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

    figures = extractor(_normalize_text(text))
    figures["extraction_confidence"] = _confidence(figures)
    return figures


# --- private extractors, one per doc type ---

def _extract_bank_statement(text: str) -> dict:
    """Pull balance, fees, and overdraft info from a bank statement."""
    figures = {}

    figures["current_balance"] = _first_money(
        text,
        [
            r"(?:ending|available|closing|current)\s+balance[:\s]+\$?([\d,]+(?:\.\d{2})?)",
            r"balance\s+as\s+of\s+\S+[:\s]+\$?([\d,]+(?:\.\d{2})?)",
        ],
    )
    figures["avg_balance"] = _first_money(
        text,
        [r"(?:average|avg)\s+(?:daily\s+)?balance[:\s]+\$?([\d,]+(?:\.\d{2})?)"],
    )

    fee_matches = _money_after_keywords(text, ["fee", "fees", "service charge", "maintenance charge"])
    overdraft_matches = _money_after_keywords(text, ["overdraft", "nsf"])
    figures["total_fees"] = round(sum(fee_matches), 2) if fee_matches else None
    figures["overdraft_total"] = round(sum(overdraft_matches), 2) if overdraft_matches else 0.0
    figures["overdraft_count"] = len(overdraft_matches)

    merchants = re.findall(
        r"(?:pos|debit|ach|card|purchase|payment)\s+([a-z][a-z0-9 &'./-]{2,40})\s+\$?[\d,]+(?:\.\d{2})?",
        text,
        re.IGNORECASE,
    )
    if merchants:
        figures["top_merchants"] = [name.strip().title() for name, _ in Counter(merchants).most_common(5)]

    return _drop_empty(figures)


def _extract_loan_agreement(text: str) -> dict:
    """Pull principal, APR, payment, and term from a loan agreement."""
    figures = {}

    figures["principal"] = _first_money(text, [r"(?:loan\s+amount|principal)[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    figures["remaining_balance"] = _first_money(text, [r"(?:remaining|outstanding|unpaid)\s+balance[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    figures["apr"] = _first_percent(text, [r"(?:annual\s+percentage\s+rate|apr)[:\s]+([\d.]+)\s*%?"])
    figures["monthly_payment"] = _first_money(text, [r"(?:monthly\s+)?payment[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    figures["term_months"] = _term_months(text)
    figures["prepayment_penalty"] = bool(re.search(r"prepayment\s+penalt|early\s+payoff\s+fee", text, re.IGNORECASE))
    return _drop_empty(figures)


def _extract_mortgage_statement(text: str) -> dict:
    """Pull balance, rate, payment, and escrow from a mortgage statement."""
    figures = {}

    figures["principal_balance"] = _first_money(
        text,
        [r"(?:outstanding|unpaid|principal)\s+balance[:\s]+\$?([\d,]+(?:\.\d{2})?)"],
    )
    figures["interest_rate"] = _first_percent(text, [r"interest\s+rate[:\s]+([\d.]+)\s*%?"])
    figures["monthly_payment"] = _first_money(text, [r"(?:monthly\s+)?payment[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    figures["escrow_balance"] = _first_money(text, [r"escrow(?:\s+balance)?[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    figures["payoff_amount"] = _first_money(text, [r"payoff\s+(?:amount|quote)[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    return _drop_empty(figures)


def _extract_credit_card_statement(text: str) -> dict:
    """Pull balance, APR, limit, and utilization from a credit card statement."""
    figures = {}

    figures["balance"] = _first_money(text, [r"(?:current|statement|new)\s+balance[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    figures["apr"] = _first_percent(text, [r"(?:purchase\s+)?apr[:\s]+([\d.]+)\s*%?"])
    figures["min_payment"] = _first_money(text, [r"(?:minimum|min)\s+payment(?:\s+due)?[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    figures["credit_limit"] = _first_money(text, [r"credit\s+limit[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    figures["statement_date"] = _first_date(text)

    # compute utilization if we have both
    if figures.get("balance") and figures.get("credit_limit") and figures["credit_limit"] > 0:
        figures["utilization_pct"] = round(figures["balance"] / figures["credit_limit"] * 100, 1)

    return _drop_empty(figures)


def _extract_cd_savings_statement(text: str) -> dict:
    """Pull balance, APY, and maturity date from a CD or savings statement."""
    figures = {}

    figures["balance"] = _first_money(text, [r"(?:account|current|available)\s+balance[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    figures["apy"] = _first_percent(text, [r"apy[:\s]+([\d.]+)\s*%?"])
    figures["interest_earned"] = _first_money(text, [r"interest\s+earned[:\s]+\$?([\d,]+(?:\.\d{2})?)"])
    figures["maturity_date"] = _first_match(text, [r"maturity\s+date[:\s]+([a-z0-9,/\- ]{6,24})"])
    return _drop_empty(figures)


def _extract_credit_report(text: str) -> dict:
    """Pull FICO score, utilization, and derogatory marks from a credit report."""
    figures = {}

    score = _first_match(text, [r"(?:fico|credit)\s+score[:\s]+(\d{3})"])
    if score:
        figures["credit_score"] = int(score)

    figures["utilization_pct"] = _first_percent(text, [r"(?:credit\s+)?utilization[:\s]+([\d.]+)\s*%?"])

    # count derogatory marks (late payments, collections, etc.)
    derogatory = re.findall(r"(?:derogatory|late\s+payment|collection|charge.?off)", text, re.IGNORECASE)
    figures["derogatory_marks"] = len(derogatory)

    return _drop_empty(figures)


# --- helpers ---

def _to_float(value: str) -> float:
    """Strip commas and cast to float."""
    return float(value.replace(",", ""))


def _normalize_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text or "")


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _first_money(text: str, patterns: list[str]) -> float | None:
    value = _first_match(text, patterns)
    return _to_float(value) if value else None


def _first_percent(text: str, patterns: list[str]) -> float | None:
    value = _first_match(text, patterns)
    return float(value) if value else None


def _money_after_keywords(text: str, keywords: list[str]) -> list[float]:
    keyword_pattern = "|".join(re.escape(keyword) for keyword in keywords)
    matches = re.findall(
        rf"(?:{keyword_pattern})[a-z\s:-]{{0,35}}\$?([\d,]+(?:\.\d{{2}})?)",
        text,
        re.IGNORECASE,
    )
    return [_to_float(match) for match in matches]


def _term_months(text: str) -> int | None:
    match = re.search(r"(?:loan\s+)?term[:\s]+(\d+)\s*(months?|years?)", text, re.IGNORECASE)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2).lower()
    return amount * 12 if unit.startswith("year") else amount


def _first_date(text: str) -> str | None:
    raw = _first_match(
        text,
        [
            r"statement\s+date[:\s]+([a-z0-9,/\- ]{6,24})",
            r"closing\s+date[:\s]+([a-z0-9,/\- ]{6,24})",
        ],
    )
    if not raw:
        return None

    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return raw


def _drop_empty(figures: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in figures.items() if value is not None}


def _confidence(figures: dict[str, Any]) -> float:
    signal_count = len([key for key, value in figures.items() if value not in (None, "", [], {})])
    return round(min(0.95, 0.25 + signal_count * 0.12), 2)
