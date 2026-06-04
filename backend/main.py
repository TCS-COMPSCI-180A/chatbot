"""
FastAPI Backend for Ethical Persuasion Chatbot
Main application entry point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from sqlalchemy import text

from database import engine, Base
import models  # registers all ORM classes with Base

from routers import chat, conversations

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Ethical Persuasion Chatbot API",
    description="Backend API for the ethical persuasion chatbot application",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [o.rstrip("/") for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(conversations.router)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Ethical Persuasion Chatbot API is running",
        "version": "0.1.0"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development")
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
