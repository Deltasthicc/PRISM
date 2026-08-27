"""
Bounded, dependency-light text extraction for TXT, Markdown, PDF, and DOCX
uploads. Every extractor is capped so an oversized or malicious file can't
exhaust memory or CPU before quiz_generator.py ever sees the text -- this is
the boundary the roadmap's "5 MB limit, 100-page PDF limit, DOCX
zip-expansion guard" controls live in.

This does not replace a real content-safety pipeline (malware/CDR scanning,
OCR for scanned pages, quarantine storage): see
docs/SIH26101_FEASIBILITY_AND_ROADMAP.md section 11 for what production
still needs on top of this.
"""
from __future__ import annotations

import io
import zipfile

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB, enforced again by the caller before read()
MAX_EXTRACTED_CHARS = 120_000
MAX_PDF_PAGES = 100
MAX_DOCX_UNCOMPRESSED_BYTES = 40 * 1024 * 1024  # guards against a DOCX zip bomb
MIN_EXTRACTED_CHARS = 200

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


class ContentExtractionError(Exception):
    """Raised when a file can't be safely turned into text for quiz generation."""


def _extension(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _extract_txt_or_md(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContentExtractionError("The file is not valid UTF-8 text.") from exc


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ContentExtractionError(
            "PDF support requires the 'pypdf' package. Run: pip install pypdf"
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        raise ContentExtractionError("Could not parse this PDF -- it may be corrupted or encrypted.") from exc

    if reader.is_encrypted:
        raise ContentExtractionError("This PDF is password-protected; remove the password and try again.")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ContentExtractionError(f"This PDF has more than {MAX_PDF_PAGES} pages; split it first.")

    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            total_uncompressed = sum(entry.file_size for entry in archive.infolist())
            if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ContentExtractionError(
                    "This DOCX file expands far larger than expected; refusing to parse it."
                )
    except zipfile.BadZipFile as exc:
        raise ContentExtractionError("This DOCX file is not a valid Office document.") from exc

    try:
        import docx  # python-docx
    except ImportError as exc:
        raise ContentExtractionError(
            "DOCX support requires the 'python-docx' package. Run: pip install python-docx"
        ) from exc

    try:
        document = docx.Document(io.BytesIO(content))
    except Exception as exc:
        raise ContentExtractionError("Could not parse this DOCX file.") from exc

    return "\n".join(paragraph.text for paragraph in document.paragraphs)


_EXTRACTORS = {
    ".txt": _extract_txt_or_md,
    ".md": _extract_txt_or_md,
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
}


def extract_text(filename: str, content: bytes) -> str:
    """Extract bounded plain text from an uploaded TXT/MD/PDF/DOCX file.

    Raises ContentExtractionError for anything unsafe or unparseable, and
    ValueError if the extracted text is too short to build a quiz from.
    """
    if len(content) > MAX_UPLOAD_BYTES:
        raise ContentExtractionError(
            f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."
        )

    extension = _extension(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise ContentExtractionError(
            f"Unsupported file type '{extension or filename}'. Use .txt, .md, .pdf, or .docx."
        )

    text = _EXTRACTORS[extension](content).strip()
    if len(text) < MIN_EXTRACTED_CHARS:
        raise ValueError("The extracted text is too short to generate a reliable quiz from.")
    return text[:MAX_EXTRACTED_CHARS]
