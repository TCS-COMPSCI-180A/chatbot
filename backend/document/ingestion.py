"""
Document ingestion pipeline.

Handles the full lifecycle of an uploaded banking document:
  1. parse_pdf_document     — extract raw text from a PDF
  2. ocr_image_document     — extract text from an image via OCR
  3. classify_banking_document — identify the document type
  4. chunk_and_embed_document  — chunk text, embed, store in pgvector
"""

from __future__ import annotations


def parse_pdf_document(file_bytes: bytes) -> str:
    """Extract raw text from a PDF file.

    Uses PDFPlumber for text-layer PDFs. Falls back to OCR via
    ocr_image_document() if no text layer is detected.

    Args:
        file_bytes: Raw bytes of the uploaded PDF file.

    Returns:
        Full extracted text as a single string.
    """
    raise NotImplementedError


def ocr_image_document(file_bytes: bytes) -> str:
    """Extract text from an image (JPG, PNG, TIFF) using Tesseract OCR.

    Pre-processes the image for contrast and deskew before passing
    to pytesseract to improve accuracy on scanned documents.

    Args:
        file_bytes: Raw bytes of the uploaded image file.

    Returns:
        Extracted text as a single string.
    """
    raise NotImplementedError


def classify_banking_document(text: str) -> str:
    """Identify the type of banking document from its content.

    Uses DeBERTa v3 zero-shot classification against a fixed set of
    banking document labels.

    Args:
        text: Raw text extracted from the document.

    Returns:
        One of: bank_statement | loan_agreement | mortgage_statement |
        credit_card_statement | cd_savings_statement | credit_report |
        foreclosure_notice | bankruptcy_filing | unknown
    """
    raise NotImplementedError


def chunk_and_embed_document(text: str, session_id: str) -> str:
    """Split a document into chunks, embed each chunk, and store in pgvector.

    Chunks are 512 tokens with a 50-token overlap. Each chunk is embedded
    using OpenAI text-embedding-3-small (1536 dims) and stored as a row
    in the document_chunks table.

    Args:
        text:       Full document text to chunk and embed.
        session_id: Session identifier — stored on each chunk for later
                    retrieval within the same conversation.

    Returns:
        doc_id: A UUID string that groups all chunks for this upload.
                Pass this to retrieve_relevant_chunks() for retrieval.
    """
    raise NotImplementedError
