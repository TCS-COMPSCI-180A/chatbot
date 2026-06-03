"""
End-to-End Test with Document Upload

Tests the full pipeline with a mock bank statement document:
1. Document ingestion (parse, classify, extract figures, chunk, embed)
2. Classifier (emotion, intent, situation)
3. Ethics gate (should APPROVE)
4. Document analysis (retrieve relevant chunks, build insights)
5. Strategy selection (should choose document_grounded/statement_analysis)
6. Generator (should cite ≥2 specific figures from document)
7. Critic (should validate citations are real, not fabricated)

Usage (from chatbot/ directory):
    cd /Users/Rounak/chatbot
    python3 backend/test_e2e_with_document.py
"""

import os
import sys

# Add parent directory to path so 'backend' module can be imported
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(parent_dir, ".env"), override=True)

import asyncio


# Mock bank statement PDF content (as text)
MOCK_BANK_STATEMENT_TEXT = """
TCS BANK
Monthly Statement
Account Holder: John Doe
Account Number: ****1234
Statement Period: February 1 - February 28, 2026

ACCOUNT SUMMARY
─────────────────────────────────────────
Beginning Balance:        $1,250.00
Ending Balance:           $  340.00
Average Daily Balance:    $  340.00

FEES CHARGED
─────────────────────────────────────────
Overdraft Fees (3x):      $  312.00
Monthly Maintenance Fee:  $   12.00
Total Fees:               $  324.00

INTEREST EARNED
─────────────────────────────────────────
Savings Interest (0.01% APY): $0.12

TRANSACTIONS (Last 30 Days)
─────────────────────────────────────────
02/01  Paycheck Deposit       +$2,450.00
02/05  Rent Payment            -$1,200.00
02/07  Overdraft Fee           -$  104.00
02/10  Groceries               -$  156.00
02/12  Netflix Subscription    -$   15.00
02/15  Spotify Subscription    -$   10.00
02/18  Overdraft Fee           -$  104.00
02/20  Utilities               -$  120.00
02/25  Overdraft Fee           -$  104.00
02/28  Amazon Prime            -$   14.00

IMPORTANT NOTICES
─────────────────────────────────────────
• Your average balance of $340 is below the $500 minimum
  required to waive the $12 monthly maintenance fee.
• You incurred 3 overdraft fees this month totaling $312.
• Consider our overdraft protection service to avoid future fees.
• Current market rate for High-Yield Savings Accounts: 4.2% APY
  (Your current savings rate: 0.01% APY)
"""


def create_mock_pdf_bytes():
    """
    Load a sample bank statement PDF for testing.

    SETUP INSTRUCTIONS:
    1. Create a PDF with the mock statement text (lines 28-72 above)
    2. Update the path below to point to your PDF file
    3. Or use any bank statement PDF you have available
    """
    # TODO: Update this path to your local PDF file
    pdf_path = "/Users/Rounak/Downloads/Banking statement.pdf"

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(
            f"PDF not found at: {pdf_path}\n"
            f"Please create a sample bank statement PDF and update the path in create_mock_pdf_bytes()"
        )

    with open(pdf_path, "rb") as f:
        return f.read()


async def test_full_pipeline_with_document():
    """Run the full LangGraph pipeline with a mock bank statement upload."""

    print("\n" + "=" * 80)
    print("  END-TO-END TEST: Document Upload → Analysis → Citation")
    print("=" * 80)

    # Import the pipeline runner
    from graph.runner import run_pipeline

    # Test message: asking for advice (should trigger document-grounded strategy)
    message = "How can I save more money based on my bank statement?"

    print(f"\nUSER MESSAGE:")
    print(f"  \"{message}\"")
    print(f"\nUPLOADED DOCUMENT:")
    print(f"  Mock bank statement (PDF)")
    print(f"  - Account balance: $340")
    print(f"  - Overdraft fees: $312 (3 occurrences)")
    print(f"  - Monthly fee: $12")
    print(f"  - Current APY: 0.01% (market: 4.2%)")

    # Create mock document bytes
    # NOTE: This is simplified - in production, this would be actual PDF bytes
    # We'll need to stub the document ingestion for this test
    document_bytes = create_mock_pdf_bytes()

    print(f"\n{'─' * 80}")
    print("RUNNING PIPELINE...")
    print(f"{'─' * 80}\n")

    try:
        # Run the pipeline
        result = await run_pipeline(
            message=message,
            session_id="test-document-session",
            document_bytes=document_bytes
        )

        response = result.get("response", "")
        debug = result.get("debug", {})

        # Display results
        print("\n" + "=" * 80)
        print("  PIPELINE RESULTS")
        print("=" * 80)

        print(f"\n📊 CLASSIFICATION:")
        print(f"  Emotion:   {debug.get('emotion', 'N/A')}")
        print(f"  Intent:    {debug.get('intent', 'N/A')}")
        print(f"  Situation: {debug.get('situation', 'N/A')}")

        print(f"\n🛡️  ETHICS GATE:")
        print(f"  Decision: {debug.get('gate_decision', 'N/A')}")
        print(f"  Reason:   {debug.get('gate_reason', 'N/A')}")

        print(f"\n📁 DOCUMENT:")
        print(f"  Uploaded:  {debug.get('has_document', False)}")
        print(f"  Type:      {debug.get('document_type', 'N/A')}")

        print(f"\n🎯 STRATEGY:")
        print(f"  Path: {debug.get('strategy_path', 'N/A')}")

        print(f"\n⚖️  CRITIC:")
        print(f"  Score:      {debug.get('critic_score', 'N/A')}/10")
        print(f"  Violations: {debug.get('critic_violations', [])}")
        print(f"  Rewrites:   {debug.get('rewrite_count', 0)}")

        print(f"\n💬 FINAL RESPONSE:")
        print(f"  {response}")

        # Validation checks
        print(f"\n{'─' * 80}")
        print("VALIDATION CHECKS:")
        print(f"{'─' * 80}")

        checks = []

        # Check 1: Document was processed
        if debug.get('has_document'):
            checks.append(("✅", "Document was processed"))
        else:
            checks.append(("❌", "Document was NOT processed"))

        # Check 2: Document-grounded strategy selected
        strategy = debug.get('strategy_path', '')
        if 'document_grounded' in strategy or 'statement_analysis' in strategy:
            checks.append(("✅", f"Document-grounded strategy selected: {strategy}"))
        else:
            checks.append(("⚠️ ", f"Expected document-grounded strategy, got: {strategy}"))

        # Check 3: Response cites specific figures
        response_lower = response.lower()
        cited_figures = []
        expected_figures = ['312', '340', '500', '12', '1,248', '4.2', '0.01']

        for fig in expected_figures:
            if fig in response or fig.replace(',', '') in response.replace(',', ''):
                cited_figures.append(fig)

        if len(cited_figures) >= 2:
            checks.append(("✅", f"Response cites ≥2 specific figures: {cited_figures}"))
        else:
            checks.append(("❌", f"Response should cite ≥2 figures, found: {cited_figures}"))

        # Check 4: Critic score passed
        critic_score = debug.get('critic_score', 0)
        if critic_score >= 7.0:
            checks.append(("✅", f"Critic score passed: {critic_score}/10"))
        else:
            checks.append(("❌", f"Critic score failed: {critic_score}/10 (threshold: 7.0)"))

        # Check 5: No generic advice phrases
        generic_phrases = ['many customers', 'statistics show', 'most people']
        found_generic = [p for p in generic_phrases if p in response_lower]

        if not found_generic:
            checks.append(("✅", "No generic advice phrases (uses specific document data)"))
        else:
            checks.append(("⚠️ ", f"Found generic phrases: {found_generic}"))

        # Check 6: Ends with a question
        if response.strip().endswith('?'):
            checks.append(("✅", "Response ends with an engaging question"))
        else:
            checks.append(("⚠️ ", "Response should end with a question"))

        # Print all checks
        for icon, message in checks:
            print(f"  {icon} {message}")

        # Final verdict
        passed = sum(1 for icon, _ in checks if icon == "✅")
        total = len(checks)

        print(f"\n{'═' * 80}")
        if passed == total:
            print(f"  🎉 ALL CHECKS PASSED ({passed}/{total})")
        elif passed >= total * 0.7:
            print(f"  ⚠️  PARTIAL PASS ({passed}/{total}) - Review warnings")
        else:
            print(f"  ❌ FAILED ({passed}/{total})")
        print(f"{'═' * 80}\n")

        return result

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print("\n🧪 Running End-to-End Document Pipeline Test...")
    print("This tests the full flow: upload → ingestion → analysis → generation → validation\n")

    asyncio.run(test_full_pipeline_with_document())
