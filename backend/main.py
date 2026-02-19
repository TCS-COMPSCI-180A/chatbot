"""
FastAPI Backend for Ethical Persuasion Chatbot
Main application entry point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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


@app.get("/")
async def root():
    """Root endpoint - Health check"""
    return {
        "status": "ok",
        "message": "Ethical Persuasion Chatbot API is running",
        "version": "0.1.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "database": "connected",  # TODO: Add actual DB health check
        "environment": os.getenv("ENVIRONMENT", "development")
    }


@app.get("/api/v1/chat")
async def chat_endpoint():
    """Placeholder chat endpoint"""
    return {
        "message": "Chat endpoint - Coming soon",
        "status": "not_implemented"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
