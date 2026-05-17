"""
Classifier Node — backend/pipeline/classifier.py
=================================================
Pipeline Step 2 (per diagram): Classifier Agent — LLM + Tool Calling.

Uses Gemini to extract emotion, intent, and situation signals from the user
message, then applies a deterministic Python routing engine to decide:
  general | domain | ethical

The LLM extracts signals only — Python decides the route.

Tool available to LLM:
  domain_lookup  — checks whether an intent belongs to a known financial domain

Both interfaces work:
  - Direct call:     classifier.classify(message, chat_history)
  - LangGraph node:  classifier_node(state) → dict
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from pipeline.pipeline_state import (
    CollectiveState,
    RouteDecision,
    _safe_parse,
    _extract_usage,
)

# =========================================================
# CONFIG
# =========================================================
MODEL = "gemini-2.5-flash"
HITL_CONFIDENCE_THRESHOLD: float = 0.5

_ALLOWED_WRITE_KEYS: frozenset[str] = frozenset({
    "route_decision", "confidence", "reasoning", "tools_used",
    "status", "emotion", "intent", "situation",
    "trace_log", "metadata",
})

# =========================================================
# SYSTEM PROMPT
# =========================================================
SYSTEM_PROMPT = """
You are a financial routing signal extractor operating inside a multi-agent pipeline.

YOUR ROLE:
- Extract structured perception signals from the user's message.
- You do NOT decide routing — the Python rules engine does that.
- You MAY call the `domain_lookup` tool if uncertain whether an intent
  belongs to a known financial domain.

OUTPUT FORMAT (when NOT calling a tool) — return ONLY valid JSON:
{
  "emotion":        "one of the emotion labels",
  "intent":         "one of the intent labels",
  "situation":      "positive_for_business | neutral_for_business | negative_for_business",
  "confidence":     0.0-1.0,
  "reasoning":      "short explanation"
}

EMOTION LABELS:
  anxiety_or_worry, fear_or_apprehension, neutral_or_calm,
  anticipation_or_interest, sadness_or_grief, joy_or_contentment,
  anger_or_frustration, trust_or_acceptance

INTENT LABELS:
  increase_investment_contribution, decrease_investment_contribution,
  inquire_about_investment_performance, cancel_policy, purchase_new_policy,
  modify_coverage, make_withdrawal, hardship_withdrawal,
  general_inquiry, request_explanation, seek_advice, compare_options

SITUATION LABELS:
  positive_for_business  — user wants to invest more, buy new policy
  neutral_for_business   — informational, no business impact
  negative_for_business  — user wants to cancel, reduce, or withdraw

RULES:
- DO NOT output route_decision — Python decides routing.
- DO NOT make ethical judgements here — that is the ethics gate's job.
- confidence reflects your certainty about the extracted signals.
"""

# =========================================================
# TOOL DECLARATION
# =========================================================
DOMAIN_LOOKUP_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="domain_lookup",
            description=(
                "Check whether a given intent string belongs to a known "
                "financial domain category. Returns is_domain (bool) and "
                "category (str | null)."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "intent": types.Schema(
                        type=types.Type.STRING,
                        description="The intent string to classify.",
                    )
                },
                required=["intent"],
            ),
        )
    ]
)

# =========================================================
# DOMAIN LOOKUP  (local truth table)
# =========================================================
_DOMAIN_INTENTS: set[str] = {
    "increase_investment_contribution",
    "decrease_investment_contribution",
    "inquire_about_investment_performance",
    "purchase_new_policy",
    "modify_coverage",
    "make_withdrawal",
    "seek_advice",
    "compare_options",
    "request_explanation",
}

_DISTRESS_EMOTIONS: set[str] = {
    "anxiety_or_worry",
    "fear_or_apprehension",
    "sadness_or_grief",
}


def _execute_domain_lookup(intent: str) -> dict:
    is_domain = intent in _DOMAIN_INTENTS
    return {"is_domain": is_domain, "category": "financial_action" if is_domain else None}


# =========================================================
# ROUTING LOGIC  (Python only — LLM never decides route)
# =========================================================

def _decide_route(emotion: str, intent: str, situation: str) -> RouteDecision:
    """
    Deterministic routing from extracted signals.

    Rules (priority order):
      1. Distress emotion → ethical (needs ethics gate review)
      2. Negative situation (cancel/withdraw/hardship) → ethical
      3. Known domain intent → domain
      4. Fallback → general
    """
    if emotion in _DISTRESS_EMOTIONS:
        return "ethical"
    if situation == "negative_for_business":
        return "ethical"
    if intent in _DOMAIN_INTENTS:
        return "domain"
    return "general"


# =========================================================
# CHAT HISTORY FORMATTER
# =========================================================

def _format_chat_history(chat_history: list) -> str:
    if not chat_history:
        return ""
    lines = ["<chat_history>"]
    for msg in chat_history[-10:]:
        lines.append(f"{msg.get('role', 'unknown').upper()}: {msg.get('content', '')}")
    lines.append("</chat_history>")
    return "\n".join(lines)


# =========================================================
# PUBLIC API — direct call interface
# =========================================================

def classify(message: str, chat_history: list | None = None) -> dict:
    """
    Classify a user message using Gemini LLM + optional tool calling.

    Args:
        message:      Raw user message text
        chat_history: Optional prior conversation for context

    Returns:
        dict with emotion, intent, situation, confidence, route_decision,
        reasoning, tools_used

    Example:
        >>> classify("I'm worried about my 401k")
        {
            "emotion": "anxiety_or_worry",
            "intent": "inquire_about_investment_performance",
            "situation": "neutral_for_business",
            "confidence": 0.88,
            "route_decision": "ethical",
            "reasoning": "...",
            "tools_used": ["llm_signal_classifier"],
        }
    """
    chat_history = chat_history or []
    tools_used: list[str] = []
    total_usage: dict[str, int] = {"prompt": 0, "completion": 0, "total": 0}

    history_block = _format_chat_history(chat_history)
    user_content = (
        f"{history_block}\n\nCURRENT MESSAGE: {message}"
        if history_block else f"CURRENT MESSAGE: {message}"
    )

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    messages: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=user_content)])
    ]

    response = client.models.generate_content(
        model=MODEL,
        contents=messages,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0,
            max_output_tokens=512,
            tools=[DOMAIN_LOOKUP_TOOL],
        ),
    )
    for k, v in _extract_usage(response).items():
        total_usage[k] += v

    if not response.candidates:
        return _error_result("No model response", tools_used)

    tools_used.append("llm_signal_classifier")
    candidate = response.candidates[0]
    parts = candidate.content.parts

    tool_call_part = next(
        (p for p in parts if getattr(p, "function_call", None)), None
    )

    if tool_call_part is not None:
        fn_call  = tool_call_part.function_call
        fn_args  = dict(fn_call.args)
        tools_used.append(f"tool:{fn_call.name}")

        tool_result = (
            _execute_domain_lookup(fn_args.get("intent", ""))
            if fn_call.name == "domain_lookup"
            else {"error": f"Unknown tool: {fn_call.name}"}
        )

        messages.append(types.Content(role="model", parts=parts))
        messages.append(types.Content(
            role="user",
            parts=[types.Part(function_response=types.FunctionResponse(
                name=fn_call.name, response=tool_result,
            ))],
        ))

        response2 = client.models.generate_content(
            model=MODEL,
            contents=messages,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0,
                max_output_tokens=512,
            ),
        )
        for k, v in _extract_usage(response2).items():
            total_usage[k] += v

        raw_text = (
            "".join(
                p.text for p in response2.candidates[0].content.parts
                if getattr(p, "text", None)
            ).strip()
            if response2.candidates else ""
        )
    else:
        raw_text = "".join(p.text for p in parts if getattr(p, "text", None)).strip()

    data = _safe_parse(raw_text)

    emotion    = data.get("emotion", "neutral_or_calm")
    intent     = data.get("intent", "general_inquiry")
    situation  = data.get("situation", "neutral_for_business")
    confidence = float(data.get("confidence", 0.0))
    reasoning  = data.get("reasoning", "")

    route = _decide_route(emotion, intent, situation)

    return {
        "emotion":        emotion,
        "intent":         intent,
        "situation":      situation,
        "confidence":     confidence,
        "route_decision": route,
        "reasoning":      reasoning,
        "tools_used":     tools_used,
        "token_usage":    total_usage,
    }


def _error_result(reason: str, tools_used: list) -> dict:
    return {
        "emotion":        "",
        "intent":         "",
        "situation":      "",
        "confidence":     0.0,
        "route_decision": "general",
        "reasoning":      reason,
        "tools_used":     tools_used,
        "token_usage":    {"prompt": 0, "completion": 0, "total": 0},
        "error":          reason,
    }


# =========================================================
# LANGGRAPH NODE
# =========================================================

def classifier_node(state: CollectiveState) -> Dict[str, Any]:
    """
    LangGraph node: Classifier Agent.

    Reads from state : current_query, chat_history, metadata
    Writes to state  : route_decision, confidence, tools_used, reasoning,
                       emotion, intent, situation, status,
                       trace_log (single new entry), metadata
    """
    t_start = time.perf_counter()

    message       = state.get("current_query", "")
    chat_history  = state.get("chat_history", [])
    existing_meta = dict(state.get("metadata", {}))

    # Empty input guard
    if not message or not message.strip():
        latency_ms  = round((time.perf_counter() - t_start) * 1000, 1)
        trace_entry = {
            "node": "classifier", "timestamp": time.time(),
            "latency_ms": latency_ms, "route_decision": "general",
            "reasoning": "Empty input — fallback to general", "error": True,
        }
        meta = {**existing_meta, "classifier": {"latency_ms": latency_ms, "error": "empty_input"}}
        return {k: v for k, v in {
            "route_decision": "general", "confidence": 0.0,
            "tools_used": [], "reasoning": "Empty input — fallback to general",
            "status": "error", "trace_log": [trace_entry], "metadata": meta,
        }.items() if k in _ALLOWED_WRITE_KEYS}

    result     = classify(message, chat_history)
    latency_ms = round((time.perf_counter() - t_start) * 1000, 1)

    trace_entry = {
        "node":           "classifier",
        "timestamp":      time.time(),
        "latency_ms":     latency_ms,
        "route_decision": result["route_decision"],
        "emotion":        result["emotion"],
        "intent":         result["intent"],
        "situation":      result["situation"],
        "confidence":     result["confidence"],
        "reasoning":      result["reasoning"],
        "tools_used":     result["tools_used"],
        "token_usage":    result.get("token_usage", {}),
    }

    meta = {**existing_meta, "classifier": {
        "latency_ms":     latency_ms,
        "route_decision": result["route_decision"],
        "emotion":        result["emotion"],
        "intent":         result["intent"],
        "tokens":         result.get("token_usage", {}),
    }}

    payload = {
        "route_decision": result["route_decision"],
        "confidence":     result["confidence"],
        "tools_used":     result["tools_used"],
        "reasoning":      result["reasoning"],
        "status":         "classified",
        "emotion":        result["emotion"],
        "intent":         result["intent"],
        "situation":      result["situation"],
        "trace_log":      [trace_entry],
        "metadata":       meta,
    }

    return {k: v for k, v in payload.items() if k in _ALLOWED_WRITE_KEYS}
