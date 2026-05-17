-- Migration 001: Add document_chunks table and update classifications
-- Run this against your PostgreSQL instance before starting the application.
-- Requires PostgreSQL 13+ with the pgvector extension available.

-- Step 1: Enable pgvector extension (safe to run multiple times)
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: Add document context columns to classifications table
ALTER TABLE classifications
    ADD COLUMN IF NOT EXISTS document_type   VARCHAR(100),
    ADD COLUMN IF NOT EXISTS document_doc_id VARCHAR(36);

-- Step 3: Create document_chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    id          SERIAL PRIMARY KEY,
    doc_id      VARCHAR(36)  NOT NULL,          -- UUID grouping all chunks for one upload
    session_id  VARCHAR(255),
    chunk_index INTEGER,                         -- position within the document
    chunk_text  TEXT         NOT NULL,
    embedding   vector(1536),                    -- text-embedding-3-small (1536 dims)
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Step 4: Index for fast session/doc lookups
CREATE INDEX IF NOT EXISTS document_chunks_doc_id_idx
    ON document_chunks (doc_id);

CREATE INDEX IF NOT EXISTS document_chunks_session_id_idx
    ON document_chunks (session_id);

-- Step 5: IVFFlat index for approximate nearest-neighbour search
--         Lists=100 is a reasonable default for up to ~1M vectors.
--         Re-index with a higher value if the table grows significantly.
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
