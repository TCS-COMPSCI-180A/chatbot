"""
Test conversation history with PDF document upload
This test demonstrates explicit use of conversation context across turns
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

import asyncio
from graph.runner import run_pipeline

async def test_pdf_with_history():
    print("🧪 Testing Conversation History with PDF Document")
    print("="*80)

    session_id = "test-pdf-history-session"

    # Read the actual banking statement PDF
    pdf_path = "/Users/Rounak/Downloads/Banking statement.pdf"
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    print(f"📄 Loaded PDF: {len(pdf_bytes)} bytes")

    # Turn 1: Upload bank statement and ask about fees
    print("\n📄 TURN 1: Upload bank statement PDF and ask about fees...")
    result1 = await run_pipeline(
        message="I just got my bank statement and I'm confused about the fees. Can you help?",
        session_id=session_id,
        document_bytes=pdf_bytes
    )
    print(f"\n👤 USER: I just got my bank statement and I'm confused about the fees. Can you help?")
    print(f"🤖 ASSISTANT: {result1['response']}\n")
    print(f"📊 Debug: document_type={result1['debug'].get('document_type')}, "
          f"gate={result1['debug'].get('gate_decision')}, "
          f"emotion={result1['debug'].get('emotion')}")

    # Turn 2: Follow-up question that REQUIRES context from turn 1
    print("\n" + "="*80)
    print("💬 TURN 2: Ask follow-up that requires remembering the document...")
    result2 = await run_pipeline(
        message="How much am I paying in total for those charges?",
        session_id=session_id
    )
    print(f"\n👤 USER: How much am I paying in total for those charges?")
    print(f"🤖 ASSISTANT: {result2['response']}\n")
    print(f"📊 Debug: gate={result2['debug'].get('gate_decision')}, "
          f"strategy={result2['debug'].get('strategy_path')}")

    # Turn 3: Another follow-up that references both previous turns
    print("\n" + "="*80)
    print("💬 TURN 3: Ask for recommendation based on previous discussion...")
    result3 = await run_pipeline(
        message="What should I do to avoid these fees in the future?",
        session_id=session_id
    )
    print(f"\n👤 USER: What should I do to avoid these fees in the future?")
    print(f"🤖 ASSISTANT: {result3['response']}\n")
    print(f"📊 Debug: gate={result3['debug'].get('gate_decision')}, "
          f"critic_score={result3['debug'].get('critic_score')}")

    print("\n" + "="*80)
    print("✅ TEST COMPLETE - Check if:")
    print("  1. Turn 2 calculated/referenced fees WITHOUT asking for the statement again")
    print("  2. Turn 3 referenced the specific fees from earlier conversation")
    print("  3. Responses show continuity and don't repeat already-stated information")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_pdf_with_history())
