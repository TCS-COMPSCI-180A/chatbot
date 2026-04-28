"""
Document ingestion pipeline - handles parsing, classifying, chunking, and embedding uploaded banking documents.
"""

from __future__ import annotations

import io
import logging

import pdfplumber
import pytesseract
from PIL import Image, ImageFilter, ImageOps

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
    # wrap bytes in BytesIO so pdfplumber can read it without a temp file
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]

    text = "\n".join(pages).strip()

    # no text means its probably a scanned image, use OCR instead
    if not text:
        logger.info("[Ingestion] No text layer found — falling back to OCR.")
        text = ocr_image_document(file_bytes)

    return text


def ocr_image_document(file_bytes: bytes) -> str:
    """Extract text from a scanned image using Tesseract OCR."""
    image = Image.open(io.BytesIO(file_bytes))

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
        # reuse the ethics gate's model instance so we don't load DeBERTa twice
        from backend.pipeline.ethics_gate import _get_classifier
        clf = _get_classifier()
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


def chunk_and_embed_document(text: str, session_id: str) -> str:
    """Split document into 512-token chunks, embed each with OpenAI, and store in pgvector. Returns doc_id."""
    import uuid
    from openai import OpenAI
    from backend.database import SessionLocal
    from backend.models import DocumentChunk

    doc_id = str(uuid.uuid4())
    chunks = _chunk_text(text)
    logger.info(f"[Ingestion] {len(chunks)} chunks to embed for doc_id={doc_id}")

    client = OpenAI()
    db = SessionLocal()

    try:
        for i, chunk in enumerate(chunks):
            # embed one chunk at a time
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=chunk,
            )
            vector = response.data[0].embedding

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
