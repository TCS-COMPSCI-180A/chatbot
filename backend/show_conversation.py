"""
Show the full conversation from the history test
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

from backend.database import SessionLocal
from backend.models import Conversation, Message

db = SessionLocal()

# Find the test conversation
conversation = db.query(Conversation).filter(
    Conversation.user_id == "test-history-session"
).first()

if not conversation:
    print("No conversation found")
    exit()

# Get all messages in chronological order
messages = db.query(Message).filter(
    Message.conversation_id == conversation.id
).order_by(Message.created_at.asc()).all()

print("="*80)
print(f"  CONVERSATION: {conversation.user_id}")
print("="*80)
print()

for i, msg in enumerate(messages, 1):
    role_icon = "👤" if msg.role.value == "user" else "🤖"
    print(f"{role_icon} MESSAGE {i} [{msg.role.value.upper()}]:")
    print(f"   {msg.content}")
    print()

db.close()
