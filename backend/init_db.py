"""
Database initialization script.

Creates all tables defined in models.py and enables pgvector extension.

Usage (from chatbot/ directory):
    cd /Users/Rounak/chatbot
    python3 backend/init_db.py
"""

import sys
import os

# Add parent directory to path for backend imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(parent_dir, ".env"), override=True)

from sqlalchemy import text
from backend.database import engine, Base
from backend.models import Conversation, Message, Classification, DocumentChunk

print("=" * 80)
print("  DATABASE INITIALIZATION")
print("=" * 80)
print()

# Step 1: Enable pgvector extension
print("Step 1: Enabling pgvector extension...")
try:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    print("✅ pgvector extension enabled")
except Exception as e:
    print(f"❌ Failed to enable pgvector: {e}")
    print("   Make sure PostgreSQL is running and you have the pgvector extension installed")
    sys.exit(1)

print()

# Step 2: Create all tables
print("Step 2: Creating database tables...")
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully:")
    print("   - conversations")
    print("   - messages")
    print("   - classifications")
    print("   - document_chunks")
except Exception as e:
    print(f"❌ Failed to create tables: {e}")
    sys.exit(1)

print()
print("=" * 80)
print("  ✅ DATABASE INITIALIZATION COMPLETE")
print("=" * 80)
print()
print("You can now run the backend with: uvicorn main:app --reload")
print()
