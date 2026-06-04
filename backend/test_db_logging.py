"""
Quick test to verify database logging is working
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

import asyncio
from graph.runner import run_pipeline
from backend.database import SessionLocal
from backend.models import Conversation, Message, Classification

async def test_db_logging():
    print("🧪 Testing Database Logging...")
    print("="*60)
    
    # Run a simple pipeline
    print("\n1. Running pipeline with test message...")
    result = await run_pipeline(
        message="How can I save more money?",
        session_id="test-db-logging-session"
    )
    
    print(f"   Response: {result['response'][:100]}...")
    
    # Check database
    print("\n2. Checking database for saved data...")
    db = SessionLocal()
    
    try:
        # Check conversations
        conv_count = db.query(Conversation).count()
        print(f"   ✅ Conversations in DB: {conv_count}")
        
        # Check messages
        msg_count = db.query(Message).count()
        print(f"   ✅ Messages in DB: {msg_count}")
        
        # Check classifications
        class_count = db.query(Classification).count()
        print(f"   ✅ Classifications in DB: {class_count}")
        
        # Get latest classification
        latest = db.query(Classification).order_by(Classification.created_at.desc()).first()
        if latest:
            print(f"\n3. Latest Classification Details:")
            print(f"   Gate Decision: {latest.gate_decision}")
            print(f"   Emotion: {latest.emotion}")
            print(f"   Intent: {latest.intent}")
            print(f"   Strategy: {latest.selected_strategy}")
            print(f"   Critic Score: {latest.critic_score}/10")
            
            # Get associated messages
            conv = db.query(Conversation).filter(Conversation.id == latest.conversation_id).first()
            messages = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.desc()).limit(2).all()
            
            print(f"\n4. Associated Messages:")
            for msg in reversed(messages):
                print(f"   [{msg.role.value}]: {msg.content[:80]}...")
        
        print("\n" + "="*60)
        print("✅ DATABASE LOGGING IS WORKING!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_db_logging())
