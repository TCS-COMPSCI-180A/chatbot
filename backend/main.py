"""
FastAPI Backend for Ethical Persuasion Chatbot
Main application entry point
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

# Import database and models
from backend.database import engine, Base, get_db
from backend import models

# Import routers
from backend.routers import conversations, chat

# Load environment variables
load_dotenv()

# Create database tables (comment out for testing without PostgreSQL)
# Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Ethical Persuasion Chatbot API",
    description="Backend API for the ethical persuasion chatbot application",
    version="0.1.0",
)

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(conversations.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    """Root endpoint - Health check"""
    return {
        "status": "ok",
        "message": "Ethical Persuasion Chatbot API is running",
        "version": "0.1.0"
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "environment": os.getenv("ENVIRONMENT", "development")
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
