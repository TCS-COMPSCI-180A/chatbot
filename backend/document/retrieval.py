"""
Semantic chunk retrieval using pgvector cosine similarity.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def retrieve_relevant_chunks(query: str, doc_id: str, top_k: int = 4) -> list[str]:
    """Embed the query and return the top_k most relevant chunks from the document."""
    if not query or not query.strip() or not doc_id:
        return []

    top_k = max(1, min(int(top_k), 12))

    try:
        import os
        from google import genai
        from database import SessionLocal

        # Embed query using Gemini gemini-embedding-001 (768 dimensions)
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        response = client.models.embed_content(
            model="models/gemini-embedding-001",
            contents=query,
            config={"output_dimensionality": 768}
        )
        embedding = response.embeddings[0].values

        db = SessionLocal()
        try:
            rows = db.execute(
                text(
                    """
                    SELECT chunk_text
                    FROM document_chunks
                    WHERE doc_id = :doc_id AND embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:embedding AS vector)
                    LIMIT :top_k
                    """
                ),
                {
                    "doc_id": doc_id,
                    "embedding": _vector_literal(embedding),
                    "top_k": top_k,
                },
            ).fetchall()
        finally:
            db.close()

        return [row[0] for row in rows]
    except Exception as exc:
        logger.warning("[Retrieval] Vector retrieval failed; falling back to lexical retrieval: %s", exc)
        return _lexical_fallback(query=query, doc_id=doc_id, top_k=top_k)


def get_session_document_id(session_id: str) -> str | None:
    """Return the most recent document id associated with a session."""
    if not session_id:
        return None

    try:
        from database import SessionLocal
        from models import DocumentChunk

        db = SessionLocal()
        try:
            row = (
                db.query(DocumentChunk.doc_id)
                .filter(DocumentChunk.session_id == str(session_id))
                .order_by(DocumentChunk.created_at.desc())
                .first()
            )
        finally:
            db.close()

        return row[0] if row else None
    except Exception as exc:
        logger.warning("[Retrieval] Could not load session document id: %s", exc)
        return None


def get_session_document_context(session_id: str) -> dict | None:
    """Return the latest document context stored for a session."""
    if not session_id:
        return None

    try:
        from database import SessionLocal
        from models import Classification, Conversation

        db = SessionLocal()
        try:
            row = (
                db.query(
                    Classification.document_doc_id,
                    Classification.document_type,
                )
                .join(Conversation, Classification.conversation_id == Conversation.id)
                .filter(Conversation.user_id == str(session_id))
                .filter(Classification.document_doc_id.isnot(None))
                .filter(Classification.document_doc_id != "")
                .order_by(Classification.created_at.desc(), Classification.id.desc())
                .first()
            )
        finally:
            db.close()

        if row:
            return {
                "document_doc_id": row[0],
                "document_type": row[1],
            }
    except Exception as exc:
        logger.warning("[Retrieval] Could not load session document context: %s", exc)

    doc_id = get_session_document_id(session_id)
    if doc_id:
        return {
            "document_doc_id": doc_id,
            "document_type": None,
        }

    return None


def _lexical_fallback(query: str, doc_id: str, top_k: int) -> list[str]:
    """Small fallback for local demos when embeddings or pgvector are unavailable."""
    try:
        from database import SessionLocal
        from models import DocumentChunk

        db = SessionLocal()
        try:
            chunks = (
                db.query(DocumentChunk.chunk_text)
                .filter(DocumentChunk.doc_id == doc_id)
                .order_by(DocumentChunk.chunk_index.asc())
                .all()
            )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("[Retrieval] Lexical fallback failed: %s", exc)
        return []

    query_terms = {term.lower() for term in query.split() if len(term) > 2}
    ranked = []
    for index, (chunk_text,) in enumerate(chunks):
        chunk_terms = chunk_text.lower()
        score = sum(1 for term in query_terms if term in chunk_terms)
        ranked.append((score, -index, chunk_text))

    ranked.sort(reverse=True)
    return [chunk for _, _, chunk in ranked[:top_k]]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"
