"""
Document ingestion pipeline - handles parsing, classifying, chunking, and embedding uploaded banking documents.
"""

from __future__ import annotations

import io
import logging

import pdfplumber
import pytesseract
from PIL import Image, ImageFilter, ImageOps
from pdfminer.pdfdocument import PDFPasswordIncorrect

logger = logging.getLogger(__name__)

# labels we pass to DeBERTa for zero-shot document classification
DOCUMENT_TYPE_LABELS: list[str] = [
    "bank statement",
    "loan agreement",
    "mortgage statement",
    "credit card statement",
    "certificate of deposit or savings statement",
    "credit report",
    "foreclosure notice",
    "bankruptcy filing",
]

# converts plain english labels back to snake_case for the db/state
_LABEL_TO_TYPE: dict[str, str] = {
    "bank statement":                                 "bank_statement",
    "loan agreement":                                 "loan_agreement",
    "mortgage statement":                             "mortgage_statement",
    "credit card statement":                          "credit_card_statement",
    "certificate of deposit or savings statement":    "cd_savings_statement",
    "credit report":                                  "credit_report",
    "foreclosure notice":                             "foreclosure_notice",
    "bankruptcy filing":                              "bankruptcy_filing",
}


def parse_pdf_document(file_bytes: bytes) -> str:
    """Extract text from a PDF, falling back to OCR if there's no text layer."""
    try:
        # wrap bytes in BytesIO so pdfplumber can read it without a temp file
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages]
    except PDFPasswordIncorrect as exc:
        raise ValueError("password_protected_pdf") from exc
    except Exception as exc:
        logger.warning("[Ingestion] PDF parse failed; trying OCR fallback: %s", exc)
        return ocr_image_document(file_bytes)

    text = "\n".join(pages).strip()

    # no text means its probably a scanned image, use OCR instead
    if not text:
        logger.info("[Ingestion] No text layer found — falling back to OCR.")
        text = ocr_image_document(file_bytes)

    return text


def ocr_image_document(file_bytes: bytes) -> str:
    """Extract text from a scanned image using Tesseract OCR."""
    try:
        image = Image.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError("unsupported_or_unreadable_document") from exc

    # grayscale improves OCR accuracy by removing color noise
    image = ImageOps.grayscale(image)

    # sharpening helps tesseract read low-contrast text
    image = image.filter(ImageFilter.SHARPEN)

    text = pytesseract.image_to_string(image, lang="eng")
    return text.strip()


def classify_banking_document(text: str) -> str:
    """Identify what type of banking document this is using DeBERTa zero-shot classification."""
    if not text or not text.strip():
        logger.warning("[DocumentClassifier] Empty text — returning unknown.")
        return "unknown"

    # only need the first 1000 chars, doc type is always clear from the header
    sample = text[:1000]

    try:
        # Load DeBERTa for zero-shot classification
        from transformers import pipeline
        clf = pipeline(
            "zero-shot-classification",
            model="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
            device=-1  # CPU
        )
        result = clf(
            sequences=sample,
            candidate_labels=DOCUMENT_TYPE_LABELS,
            multi_label=False,
        )
    except Exception as exc:
        logger.error(f"[DocumentClassifier] Classification failed: {exc}", exc_info=True)
        return "unknown"

    top_label: str = result["labels"][0]
    top_score: float = result["scores"][0]

    logger.debug(f"[DocumentClassifier] top='{top_label}' score={top_score:.3f}")

    # below 0.4 confidence we don't trust the result
    if top_score < 0.4:
        return "unknown"

    return _LABEL_TO_TYPE.get(top_label, "unknown")


def extract_banking_figures(text: str, doc_type: str) -> dict:
    """Pull structured banking figures from parsed document text."""
    try:
        from backend.document.extractors import extract_banking_figures as extract
    except ImportError:
        from document.extractors import extract_banking_figures as extract

    return extract(text, doc_type)


def chunk_and_embed_document(text: str, session_id: str) -> str:
    """Split document into 512-token chunks, embed each with Gemini gemini-embedding-001 (768 dims), and store in pgvector. Returns doc_id."""
    import os
    import uuid
    from google import genai
    try:
        from backend.database import SessionLocal
        from backend.models import DocumentChunk
    except ImportError:
        from database import SessionLocal
        from models import DocumentChunk

    doc_id = str(uuid.uuid4())
    chunks = _chunk_text(text)
    logger.info(f"[Ingestion] {len(chunks)} chunks to embed for doc_id={doc_id}")

    if not chunks:
        logger.warning("[Ingestion] No chunks produced for doc_id=%s", doc_id)
        return doc_id

    # Initialize Gemini client
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    db = SessionLocal()

    try:
        for i, chunk in enumerate(chunks):
            try:
                # embed one chunk at a time; if embeddings are unavailable,
                # still persist text chunks so lexical retrieval can work.
                response = client.models.embed_content(
                    model="models/gemini-embedding-001",
                    contents=chunk,
                    config={"output_dimensionality": 768}
                )
                # Gemini returns embedding as .values (list of floats)
                vector = response.embeddings[0].values
            except Exception as exc:
                logger.warning("[Ingestion] Embedding failed for chunk %s; storing text only: %s", i, exc)
                vector = None

            db.add(DocumentChunk(
                doc_id=doc_id,
                session_id=session_id,
                chunk_index=i,
                chunk_text=chunk,
                embedding=vector,
            ))

        db.commit()
        logger.info(f"[Ingestion] Stored {len(chunks)} chunks for doc_id={doc_id}")
    except Exception as exc:
        db.rollback()
        logger.error(f"[Ingestion] Failed to embed/store chunks: {exc}", exc_info=True)
        raise
    finally:
        db.close()

    return doc_id


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Split text into overlapping word-based chunks (~512 tokens each)."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        # step forward by chunk_size minus overlap so adjacent chunks share context
        start += chunk_size - overlap

    return chunks
