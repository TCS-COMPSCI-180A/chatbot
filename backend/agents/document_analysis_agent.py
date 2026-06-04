"""
Document Analysis Agent - LangGraph node that runs in parallel with the Classifier Agent.
Retrieves relevant document chunks and produces grounded insights for the Generator.
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import Any

logger = logging.getLogger(__name__)


STATEMENT_DOC_TYPES = {"bank_statement", "credit_card_statement", "cd_savings_statement", "credit_report"}
LOAN_DOC_TYPES = {"loan_agreement", "mortgage_statement"}


def run_document_analysis(state: dict) -> dict:
    """Retrieve relevant chunks from the uploaded document and return a list of specific, grounded insights."""
    if not state.get("has_document"):
        return {"document_insights": []}

    doc_id = state.get("document_doc_id")
    message = state.get("message", "")
    figures = state.get("document_figures") or {}
    doc_type = state.get("document_type") or "unknown"

    chunks = []
    if doc_id:
        from document.retrieval import retrieve_relevant_chunks

        chunks = retrieve_relevant_chunks(message, doc_id, top_k=4)

    metrics = calculate_banking_metrics(figures, doc_type)
    rates = get_current_banking_rates(_rate_product_for_doc(doc_type))
    deterministic_insights = _build_deterministic_insights(doc_type, figures, metrics, rates)

    llm_insights = _llm_insights(
        message=message,
        doc_type=doc_type,
        figures=figures,
        metrics=metrics,
        rates=rates,
        chunks=chunks,
    )

    insights = _dedupe_preserve_order(llm_insights + deterministic_insights)

    return {
        "document_insights": insights[:8],
        "document_analysis_chunks": chunks,
        "document_metrics": metrics,
        "document_rates": rates,
    }


def calculate_banking_metrics(figures: dict, doc_type: str) -> dict:
    """Compute derived banking metrics from extracted figures."""
    metrics: dict[str, Any] = {}

    if doc_type == "bank_statement":
        total_fees = _num(figures.get("total_fees"), 0.0)
        overdraft_total = _num(figures.get("overdraft_total"), 0.0)
        balance = _num(figures.get("avg_balance") or figures.get("current_balance"), 0.0)
        metrics["annualized_fees"] = round(total_fees * 12, 2) if total_fees else 0.0
        metrics["annualized_overdraft_total"] = round(overdraft_total * 4, 2) if overdraft_total else 0.0
        metrics["fee_pct_of_balance"] = round(total_fees / balance * 100, 2) if balance > 0 and total_fees else None
        metrics["overdraft_risk_score"] = min(100, int(_num(figures.get("overdraft_count"), 0) * 20))

    elif doc_type in {"loan_agreement", "mortgage_statement"}:
        principal = _num(figures.get("remaining_balance") or figures.get("principal") or figures.get("principal_balance"), 0.0)
        apr = _num(figures.get("apr") or figures.get("interest_rate"), 0.0)
        payment = _num(figures.get("monthly_payment"), 0.0)
        term_months = int(_num(figures.get("term_months"), 0))
        monthly_rate = apr / 100 / 12 if apr else 0.0
        metrics["effective_monthly_rate"] = round(monthly_rate * 100, 4) if monthly_rate else None
        if principal and monthly_rate and payment > principal * monthly_rate:
            payoff_months = -math.log(1 - principal * monthly_rate / payment) / math.log(1 + monthly_rate)
            metrics["estimated_payoff_months"] = round(payoff_months)
            metrics["total_interest_remaining"] = round(payment * payoff_months - principal, 2)
        elif principal and term_months and payment:
            metrics["total_interest_remaining"] = round(payment * term_months - principal, 2)

    elif doc_type == "credit_card_statement":
        balance = _num(figures.get("balance"), 0.0)
        apr = _num(figures.get("apr"), 0.0)
        minimum = _num(figures.get("min_payment"), 0.0)
        utilization = _num(figures.get("utilization_pct"), 0.0)
        metrics["monthly_interest_cost"] = round(balance * (apr / 100 / 12), 2) if balance and apr else None
        metrics["utilization_category"] = "good" if utilization < 30 else "fair" if utilization < 50 else "poor"
        if balance and apr and minimum > balance * (apr / 100 / 12):
            monthly_rate = apr / 100 / 12
            payoff_months = -math.log(1 - balance * monthly_rate / minimum) / math.log(1 + monthly_rate)
            metrics["payoff_months_at_min_payment"] = round(payoff_months)

    elif doc_type == "cd_savings_statement":
        balance = _num(figures.get("balance"), 0.0)
        apy = _num(figures.get("apy"), 0.0)
        metrics["estimated_annual_interest"] = round(balance * apy / 100, 2) if balance and apy else None

    return {key: value for key, value in metrics.items() if value is not None}


def get_current_banking_rates(product_type: str) -> dict:
    """Static quarterly lookup table for illustrative comparisons, not live offers."""
    rates = {
        "hysa": {"apy": 4.2, "source": "illustrative_national_comparison_2026_q2"},
        "cd_12_month": {"apy": 4.8, "source": "illustrative_national_comparison_2026_q2"},
        "mortgage_30yr": {"rate": 6.9, "source": "illustrative_national_comparison_2026_q2"},
        "personal_loan": {"apr_range": [9.5, 24.0], "source": "illustrative_national_comparison_2026_q2"},
        "credit_card": {"apr": 21.5, "source": "illustrative_national_comparison_2026_q2"},
    }
    return rates.get(product_type, {"source": "no_rate_comparison_available"})


def _llm_insights(
    message: str,
    doc_type: str,
    figures: dict,
    metrics: dict,
    rates: dict,
    chunks: list[str],
) -> list[str]:
    """Ask Gemini for grounded observations when configured; otherwise return an empty list."""
    if not os.getenv("GOOGLE_API_KEY") or not chunks:
        return []

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        prompt = f"""
Return JSON only: a list of 3-5 concise document-grounded insights.
Every insight must cite a figure from the provided figures, metrics, rates, or chunks.
Do not invent numbers.

User question: {message}
Document type: {doc_type}
Figures: {json.dumps(figures)}
Metrics: {json.dumps(metrics)}
Rates: {json.dumps(rates)}
Chunks: {json.dumps(chunks[:4])}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=500,
                response_mime_type="application/json",
            ),
        )
        parsed = json.loads(response.text)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    except Exception as exc:
        logger.info("[DocumentAnalysis] LLM insight generation skipped/failed: %s", exc)

    return []


def _build_deterministic_insights(doc_type: str, figures: dict, metrics: dict, rates: dict) -> list[str]:
    insights: list[str] = []

    if doc_type == "bank_statement":
        if "current_balance" in figures:
            insights.append(f"Your statement shows a current balance of {_money(figures['current_balance'])}.")
        if "avg_balance" in figures:
            insights.append(f"Your average daily balance is {_money(figures['avg_balance'])}.")
        if _num(figures.get("total_fees"), 0.0) > 0:
            insights.append(
                f"Your statement shows {_money(figures['total_fees'])} in fees, about {_money(metrics.get('annualized_fees', 0))} annualized at the same pace."
            )
        if _num(figures.get("overdraft_total"), 0.0) > 0:
            insights.append(
                f"Your statement shows {figures.get('overdraft_count', 0)} overdraft/NSF events totaling {_money(figures['overdraft_total'])}."
            )

    elif doc_type == "credit_card_statement":
        if "balance" in figures:
            insights.append(f"Your statement balance is {_money(figures['balance'])}.")
        if "credit_limit" in figures and "utilization_pct" in figures:
            insights.append(
                f"Your credit limit is {_money(figures['credit_limit'])}, putting utilization at {figures['utilization_pct']}%."
            )
        if "min_payment" in figures:
            insights.append(f"Your minimum payment due is {_money(figures['min_payment'])}.")
        if metrics.get("monthly_interest_cost") is not None:
            insights.append(f"At the listed APR, estimated monthly interest is about {_money(metrics['monthly_interest_cost'])}.")

    elif doc_type in LOAN_DOC_TYPES:
        balance_key = "principal_balance" if doc_type == "mortgage_statement" else "remaining_balance"
        balance = figures.get(balance_key) or figures.get("principal")
        if balance:
            insights.append(f"The document shows a loan balance of {_money(balance)}.")
        rate = figures.get("interest_rate") or figures.get("apr")
        if rate:
            insights.append(f"The document lists an interest/APR rate of {rate}%.")
        if figures.get("monthly_payment"):
            insights.append(f"Your monthly payment is {_money(figures['monthly_payment'])}.")
        if metrics.get("total_interest_remaining") is not None:
            insights.append(f"Estimated remaining interest is about {_money(metrics['total_interest_remaining'])} if the payment pattern holds.")

    elif doc_type == "cd_savings_statement":
        if figures.get("balance"):
            insights.append(f"The statement shows a balance of {_money(figures['balance'])}.")
        if figures.get("apy"):
            insights.append(f"The listed APY is {figures['apy']}%; the illustrative HYSA comparison rate is {rates.get('apy')}%.")
        if metrics.get("estimated_annual_interest") is not None:
            insights.append(f"Estimated annual interest at the listed APY is {_money(metrics['estimated_annual_interest'])}.")

    elif doc_type == "credit_report":
        if figures.get("credit_score"):
            insights.append(f"Your credit report shows a score of {figures['credit_score']}.")
        if figures.get("utilization_pct") is not None:
            insights.append(f"Your reported utilization is {figures['utilization_pct']}%.")
        insights.append(f"The report includes {figures.get('derogatory_marks', 0)} derogatory-mark references found during extraction.")

    if rates.get("source") and rates.get("source") != "no_rate_comparison_available":
        insights.append(f"Rate comparisons are illustrative from {rates['source']}, not a guaranteed offer.")

    return insights


def _rate_product_for_doc(doc_type: str) -> str:
    if doc_type == "credit_card_statement":
        return "credit_card"
    if doc_type == "cd_savings_statement":
        return "cd_12_month"
    if doc_type == "mortgage_statement":
        return "mortgage_30yr"
    if doc_type == "loan_agreement":
        return "personal_loan"
    return "hysa"


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _money(value: Any) -> str:
    return f"${_num(value):,.2f}"


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        normalized = " ".join(item.split()).lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(item)
    return result
