"""
Bounded, dependency-light text extraction for TXT, Markdown, PDF, DOCX, PPTX,
and transcripts. Every extractor is capped so an oversized or malicious file can't
exhaust memory or CPU before downstream models see the text.

Wraps the unified Lane 4 ingestion engine in `ai.ingestion`.
"""
from __future__ import annotations

from ai.ingestion import (
    ALLOWED_EXTENSIONS,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_EXTRACTED_CHARS,
    MAX_PDF_PAGES,
    MAX_PPTX_SLIDES,
    MAX_PPTX_UNCOMPRESSED_BYTES,
    MAX_UPLOAD_BYTES,
    MIN_EXTRACTED_CHARS,
    ContentExtractionError,
    ingest_document,
)


def extract_text(filename: str, content: bytes) -> str:
    """Extract bounded plain text from an uploaded file.

    Raises ContentExtractionError for anything unsafe or unparseable, and
    ValueError if the extracted text is too short.
    """
    _, _, extracted_text = ingest_document(filename, content)
    return extracted_text
