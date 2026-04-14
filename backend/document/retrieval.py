"""
Semantic chunk retrieval using pgvector cosine similarity.
"""

from __future__ import annotations


def retrieve_relevant_chunks(query: str, doc_id: str, top_k: int = 4) -> list[str]:
    """Embed the query and return the top_k most relevant chunks from the document."""
    raise NotImplementedError
