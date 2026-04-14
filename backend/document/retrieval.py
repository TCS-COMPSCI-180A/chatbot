"""
Semantic retrieval over stored document chunks.

Queries the document_chunks table using pgvector cosine similarity
to find the most relevant chunks for a given natural language query.
"""

from __future__ import annotations


def retrieve_relevant_chunks(query: str, doc_id: str, top_k: int = 4) -> list[str]:
    """Retrieve the top-k most relevant document chunks for a query.

    Embeds the query using text-embedding-3-small, then performs a
    cosine similarity search against all chunks belonging to doc_id
    in the document_chunks table.

    Args:
        query:  Natural language query (typically the user's message).
        doc_id: UUID string returned by chunk_and_embed_document —
                scopes the search to one uploaded document.
        top_k:  Number of chunks to return. Defaults to 4.

    Returns:
        List of chunk_text strings ordered by relevance (most relevant first).
    """
    raise NotImplementedError
