"""
Test conversation history retrieval and context-aware responses
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

import asyncio
from graph.runner import run_pipeline

async def test_conversation_history():
    print("🧪 Testing Conversation History...")
    print("="*60)
    
    session_id = "test-history-session"
    
    # First message
    print("\n1. First message (no history yet)...")
    result1 = await run_pipeline(
        message="What are your savings account rates?",
        session_id=session_id
    )
    print(f"   Response: {result1['response'][:100]}...")
    
    # Second message (should have history now)
    print("\n2. Second message (should reference first)...")
    result2 = await run_pipeline(
        message="What about CDs?",
        session_id=session_id
    )
    print(f"   Response: {result2['response'][:150]}...")
    
    # Third message (should have both previous messages)
    print("\n3. Third message (should have full context)...")
    result3 = await run_pipeline(
        message="Which one would you recommend for someone like me?",
        session_id=session_id
    )
    print(f"   Response: {result3['response'][:150]}...")
    
    print("\n" + "="*60)
    print("✅ CONVERSATION HISTORY TEST COMPLETE!")
    print("="*60)
    print("\nCheck that:")
    print("  - Second message understood 'CDs' in context of savings")
    print("  - Third message referenced previous discussion")
    print("  - Responses are coherent across turns")

if __name__ == "__main__":
    asyncio.run(test_conversation_history())
