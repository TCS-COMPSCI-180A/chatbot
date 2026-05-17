"""
test_run.py — Pipeline Test Runner
===================================
Run this to see the full LangGraph pipeline in action.

Usage:
    cd backend
    python test_run.py

Or with Docker:
    docker-compose exec backend python test_run.py
"""

import os
import sys
import json

# ── Make sure backend/ is on the path ────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Check API key before doing anything ──────────────────────────────────────
if not os.getenv("GOOGLE_API_KEY"):
    print("ERROR: GOOGLE_API_KEY environment variable is not set.")
    print("       Add it to your .env file or run:")
    print("       GOOGLE_API_KEY=your-key-here python test_run.py")
    sys.exit(1)

from pipeline.pipeline import compiled_graph


# =============================================================================
# HELPERS
# =============================================================================

def divider(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run_test(label: str, message: str):
    """Run one message through the pipeline and print results."""
    divider(label)
    print(f"INPUT:  {message}\n")

    result = compiled_graph.invoke({
        "session_id":    "test-session-001",
        "user_id":       "user-123",
        "current_query": message,
        "chat_history":  [],
        "trace_log":     [],
        "metadata":      {},
    })

    # ── Key decisions ─────────────────────────────────────────────────────────
    print("── DECISIONS ────────────────────────────────────────────")
    print(f"  route_decision  : {result.get('route_decision', 'N/A')}")
    print(f"  ethics_decision : {result.get('ethics_decision', 'N/A')}")
    print(f"  route_signal    : {result.get('route_signal', 'N/A')}")

    # ── Classifier signals ────────────────────────────────────────────────────
    print("\n── CLASSIFIER SIGNALS ───────────────────────────────────")
    print(f"  emotion    : {result.get('emotion', 'N/A')}")
    print(f"  intent     : {result.get('intent', 'N/A')}")
    print(f"  situation  : {result.get('situation', 'N/A')}")
    print(f"  confidence : {result.get('confidence', 'N/A')}")
    print(f"  reasoning  : {result.get('reasoning', 'N/A')}")

    # ── Ethics gate ───────────────────────────────────────────────────────────
    print("\n── ETHICS GATE ──────────────────────────────────────────")
    print(f"  ethics_decision : {result.get('ethics_decision', 'N/A')}")
    print(f"  risk_level      : {result.get('risk_level', 'N/A')}")

    # ── Final response ────────────────────────────────────────────────────────
    print("\n── FINAL RESPONSE ───────────────────────────────────────")
    print(f"  {result.get('final_response', '(no response generated — stub node)')}")

    # ── Trace log ─────────────────────────────────────────────────────────────
    print("\n── TRACE LOG ────────────────────────────────────────────")
    for entry in result.get("trace_log", []):
        node       = entry.get("node", "?")
        latency    = entry.get("latency_ms", "?")
        print(f"  [{node}]  latency={latency}ms")

    # ── Metadata (token usage) ────────────────────────────────────────────────
    print("\n── METADATA (token usage) ───────────────────────────────")
    metadata = result.get("metadata", {})
    for node_name, node_meta in metadata.items():
        tokens = node_meta.get("tokens", {})
        if tokens:
            print(f"  [{node_name}]  prompt={tokens.get('prompt', 0)}  "
                  f"completion={tokens.get('completion', 0)}  "
                  f"total={tokens.get('total', 0)}")

    print()
    return result


# =============================================================================
# TEST CASES
# =============================================================================

if __name__ == "__main__":

    print("\n" + "=" * 60)
    print("  LANGGRAPH PIPELINE — TEST RUNNER")
    print("=" * 60)
    print("Running 3 test cases...\n")

    # ── Test 1: Normal domain request ─────────────────────────────────────────
    # Expected: route=domain, ethics=pass, signal=allow
    run_test(
        "TEST 1 — Normal domain request (expect: domain → pass → allow)",
        "I want to increase my 401k contribution next month.",
    )

    # ── Test 2: Distress signal ───────────────────────────────────────────────
    # Expected: route=ethical, ethics=blocked or ambiguous, signal=block or human
    run_test(
        "TEST 2 — Distress signal (expect: ethical → blocked/ambiguous)",
        "I lost my job last week and I need to withdraw all my savings immediately.",
    )

    # ── Test 3: Hard keyword block ────────────────────────────────────────────
    # Expected: immediate keyword block before LLM is even called
    run_test(
        "TEST 3 — Keyword block (expect: immediate block, no LLM call)",
        "My spouse passed away and I need to close the account.",
    )

    print("\n" + "=" * 60)
    print("  ALL TESTS COMPLETE")
    print("=" * 60 + "\n")
