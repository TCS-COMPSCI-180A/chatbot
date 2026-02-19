-- Initialize PostgreSQL database with pgvector extension
-- This script runs automatically when the database is first created

-- Create pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension installation
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Create initial schema (optional - can be handled by backend migrations)
-- Uncomment and modify as needed for your application

-- Example table with vector column:
-- CREATE TABLE IF NOT EXISTS conversations (
--     id SERIAL PRIMARY KEY,
--     user_id VARCHAR(255) NOT NULL,
--     message TEXT NOT NULL,
--     embedding vector(1536),  -- OpenAI embeddings dimension
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- Create index for vector similarity search (optional)
-- CREATE INDEX IF NOT EXISTS conversations_embedding_idx 
-- ON conversations USING ivfflat (embedding vector_cosine_ops);

COMMENT ON EXTENSION vector IS 'Vector similarity search for PostgreSQL';
