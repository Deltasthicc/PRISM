"""Lane 4 (Content AI, RAG & Evaluation) — Bounded Ingestion Engine.

Parses TXT, Markdown, PDF, DOCX, PPTX, and timestamped transcripts into
immutable SourceVersion records and Chunk objects with exact source locators.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Any

from ai.provenance import Chunk, SourceLocator, SourceVersion, generate_uuid
from ai.security import sanitize_untrusted_text

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_EXTRACTED_CHARS = 120_000
MAX_PDF_PAGES = 100
MAX_PPTX_SLIDES = 100
MAX_DOCX_UNCOMPRESSED_BYTES = 40 * 1024 * 1024  # 40 MB zip-bomb guard
MAX_PPTX_UNCOMPRESSED_BYTES = 40 * 1024 * 1024  # 40 MB zip-bomb guard
MIN_EXTRACTED_CHARS = 100

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx", ".vtt", ".srt", ".transcript"}


class ContentExtractionError(Exception):
    """Raised when a file cannot be safely or validly extracted."""


def _extension(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _parse_txt_or_md(content: bytes) -> list[tuple[str, SourceLocator]]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        try:
            text = content.decode("latin-1")
        except Exception as inner_exc:
            raise ContentExtractionError("File content is not valid encoded text.") from inner_exc

    sections: list[tuple[str, SourceLocator]] = []
    lines = text.splitlines()
    current_section = "Introduction"
    current_lines: list[str] = []
    section_index = 1

    for line in lines:
        if line.startswith("#"):
            if current_lines:
                sec_text = "\n".join(current_lines).strip()
                if sec_text:
                    sections.append((
                        sec_text,
                        SourceLocator(
                            locator_type="section",
                            index=section_index,
                            label=f"Section: {current_section}",
                        ),
                    ))
                    section_index += 1
                current_lines = []
            current_section = line.lstrip("#").strip() or f"Section {section_index}"
        else:
            current_lines.append(line)

    if current_lines:
        sec_text = "\n".join(current_lines).strip()
        if sec_text:
            sections.append((
                sec_text,
                SourceLocator(
                    locator_type="section",
                    index=section_index,
                    label=f"Section: {current_section}",
                ),
            ))

    if not sections:
        sections.append((
            text.strip(),
            SourceLocator(locator_type="section", index=1, label="Document Body"),
        ))
    return sections


def _parse_pdf(content: bytes) -> list[tuple[str, SourceLocator]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ContentExtractionError("PDF parsing requires the 'pypdf' package.") from exc

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        raise ContentExtractionError("Could not parse PDF — corrupted or invalid format.") from exc

    if reader.is_encrypted:
        raise ContentExtractionError("PDF is password protected; remove password before upload.")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ContentExtractionError(f"PDF exceeds {MAX_PDF_PAGES} page limit ({len(reader.pages)} pages).")

    pages: list[tuple[str, SourceLocator]] = []
    for i, page in enumerate(reader.pages, start=1):
        extracted = (page.extract_text() or "").strip()
        if extracted:
            pages.append((
                extracted,
                SourceLocator(locator_type="page", index=i, label=f"Page {i}"),
            ))
    return pages


def _parse_docx(content: bytes) -> list[tuple[str, SourceLocator]]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            total_uncompressed = sum(entry.file_size for entry in archive.infolist())
            if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ContentExtractionError("DOCX expands beyond safe limits (potential zip bomb).")
    except zipfile.BadZipFile as exc:
        raise ContentExtractionError("Invalid DOCX format.") from exc

    try:
        import docx
        document = docx.Document(io.BytesIO(content))
        elements: list[tuple[str, SourceLocator]] = []
        current_heading = "Main"
        current_paras: list[str] = []
        para_idx = 1

        for p in document.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            if p.style and p.style.name.startswith("Heading"):
                if current_paras:
                    elements.append((
                        "\n".join(current_paras),
                        SourceLocator(locator_type="section", index=para_idx, label=f"Section: {current_heading}"),
                    ))
                    para_idx += 1
                    current_paras = []
                current_heading = text
            else:
                current_paras.append(text)

        if current_paras:
            elements.append((
                "\n".join(current_paras),
                SourceLocator(locator_type="section", index=para_idx, label=f"Section: {current_heading}"),
            ))
        return elements
    except Exception:
        # Fallback XML parsing if python-docx fails
        return [(_extract_docx_xml(content), SourceLocator(locator_type="section", index=1, label="Document Body"))]


def _extract_docx_xml(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        xml_content = archive.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        texts = [node.text for node in tree.iter() if node.text]
        return "\n".join(texts)


def _parse_pptx(content: bytes) -> list[tuple[str, SourceLocator]]:
    """Safe, bounded standard-library PPTX slide extraction."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            total_uncompressed = sum(entry.file_size for entry in archive.infolist())
            if total_uncompressed > MAX_PPTX_UNCOMPRESSED_BYTES:
                raise ContentExtractionError("PPTX expands beyond safe limits (potential zip bomb).")

            # Discover slide XML files
            slide_entries = sorted(
                [f for f in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml", f)],
                key=lambda x: int(re.search(r"slide(\d+)\.xml", x).group(1)),
            )

            if len(slide_entries) > MAX_PPTX_SLIDES:
                raise ContentExtractionError(f"PPTX exceeds {MAX_PPTX_SLIDES} slide limit ({len(slide_entries)} slides).")

            slides: list[tuple[str, SourceLocator]] = []
            for i, entry_name in enumerate(slide_entries, start=1):
                slide_xml = archive.read(entry_name)
                tree = ET.fromstring(slide_xml)
                # In PresentationML, text nodes are in namespace http://schemas.openxmlformats.org/drawingml/2006/main with tag 't'
                slide_texts: list[str] = []
                for node in tree.iter():
                    if node.tag.endswith("}t") and node.text:
                        slide_texts.append(node.text.strip())
                slide_text = " ".join(slide_texts).strip()
                if slide_text:
                    slides.append((
                        slide_text,
                        SourceLocator(locator_type="slide", index=i, label=f"Slide {i}"),
                    ))
            return slides
    except ContentExtractionError:
        raise
    except Exception as exc:
        raise ContentExtractionError("Could not parse PPTX presentation — invalid or corrupted file.") from exc


def _parse_transcript(content: bytes) -> list[tuple[str, SourceLocator]]:
    """Parse VTT/SRT or timestamped transcripts preserving timecodes."""
    text = content.decode("utf-8", errors="replace")
    blocks: list[tuple[str, SourceLocator]] = []

    # Match common VTT/SRT timestamp lines like 00:01:20.000 --> 00:01:35.000 or 00:01:20 --> 00:01:35
    timestamp_pattern = re.compile(
        r"(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{3})?)\s*-->\s*(\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{3})?)"
    )

    lines = text.splitlines()
    current_start: str | None = None
    current_end: str | None = None
    current_text: list[str] = []
    chunk_index = 1

    for line in lines:
        line_clean = line.strip()
        if not line_clean or line_clean.isdigit() or line_clean == "WEBVTT":
            continue
        ts_match = timestamp_pattern.search(line_clean)
        if ts_match:
            if current_text and current_start:
                cue_text = " ".join(current_text).strip()
                if cue_text:
                    blocks.append((
                        cue_text,
                        SourceLocator(
                            locator_type="timecode",
                            index=chunk_index,
                            label=f"Timecode {current_start} - {current_end}",
                            start_timecode=current_start,
                            end_timecode=current_end,
                        ),
                    ))
                    chunk_index += 1
                current_text = []
            current_start = ts_match.group(1)
            current_end = ts_match.group(2)
        else:
            current_text.append(line_clean)

    if current_text and current_start:
        cue_text = " ".join(current_text).strip()
        if cue_text:
            blocks.append((
                cue_text,
                SourceLocator(
                    locator_type="timecode",
                    index=chunk_index,
                    label=f"Timecode {current_start} - {current_end}",
                    start_timecode=current_start,
                    end_timecode=current_end,
                ),
            ))

    if not blocks:
        # Fallback to plain paragraphs if not formatted as cues
        return _parse_txt_or_md(content)
    return blocks


_PARSERS = {
    ".txt": _parse_txt_or_md,
    ".md": _parse_txt_or_md,
    ".pdf": _parse_pdf,
    ".docx": _parse_docx,
    ".pptx": _parse_pptx,
    ".vtt": _parse_transcript,
    ".srt": _parse_transcript,
    ".transcript": _parse_transcript,
}


def _split_into_chunks(
    text_blocks: list[tuple[str, SourceLocator]],
    source_id: str,
    source_version: int,
    tenant_id: str = "default",
    allowed_roles: list[str] | None = None,
    target_chunk_chars: int = 600,
    overlap_chars: int = 100,
) -> list[Chunk]:
    """Chunk extracted blocks while maintaining precise locators."""
    chunks: list[Chunk] = []
    roles = allowed_roles or ["learner", "trainer", "admin"]

    for block_text, locator in text_blocks:
        sanitized = sanitize_untrusted_text(block_text)
        if not sanitized:
            continue

        if len(sanitized) <= target_chunk_chars:
            chunks.append(
                Chunk(
                    chunk_id=generate_uuid(),
                    source_id=source_id,
                    source_version=source_version,
                    text=sanitized,
                    locators=[locator],
                    tenant_id=tenant_id,
                    allowed_roles=roles,
                    token_count=len(sanitized.split()),
                )
            )
        else:
            # Sub-chunk larger blocks with overlap
            sentences = re.split(r"(?<=[.!?])\s+", sanitized)
            curr_chunk = ""
            for sentence in sentences:
                if len(curr_chunk) + len(sentence) + 1 > target_chunk_chars and curr_chunk:
                    chunks.append(
                        Chunk(
                            chunk_id=generate_uuid(),
                            source_id=source_id,
                            source_version=source_version,
                            text=curr_chunk.strip(),
                            locators=[locator],
                            tenant_id=tenant_id,
                            allowed_roles=roles,
                            token_count=len(curr_chunk.split()),
                        )
                    )
                    # Retain last few characters for context overlap
                    curr_chunk = curr_chunk[-overlap_chars:] + " " + sentence
                else:
                    curr_chunk = f"{curr_chunk} {sentence}".strip()

            if curr_chunk.strip():
                chunks.append(
                    Chunk(
                        chunk_id=generate_uuid(),
                        source_id=source_id,
                        source_version=source_version,
                        text=curr_chunk.strip(),
                        locators=[locator],
                        tenant_id=tenant_id,
                        allowed_roles=roles,
                        token_count=len(curr_chunk.split()),
                    )
                )

    return chunks


def ingest_document(
    filename: str,
    content: bytes,
    source_id: str | None = None,
    version: int = 1,
    tenant_id: str = "default",
    allowed_roles: list[str] | None = None,
) -> tuple[SourceVersion, list[Chunk], str]:
    """Ingest, validate, hash, and chunk a document with provenance locators.

    Returns:
        (source_version, chunks, full_extracted_text)
    """
    if len(content) > MAX_UPLOAD_BYTES:
        raise ContentExtractionError(
            f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."
        )

    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ContentExtractionError(
            f"Unsupported file type '{ext or filename}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

    parser = _PARSERS[ext]
    text_blocks = parser(content)

    full_text = "\n\n".join(text for text, _ in text_blocks).strip()
    sanitized_full = sanitize_untrusted_text(full_text, MAX_EXTRACTED_CHARS)

    if len(sanitized_full) < MIN_EXTRACTED_CHARS:
        raise ValueError("The extracted text is too short to generate a reliable learning artifact from.")

    doc_source_id = source_id or generate_uuid()
    sha256_hash = hashlib.sha256(content).hexdigest()

    source_ver = SourceVersion(
        source_id=doc_source_id,
        version=version,
        sha256=sha256_hash,
        filename=filename,
        content_type=ext.lstrip("."),
        character_count=len(sanitized_full),
        metadata={"block_count": len(text_blocks), "extension": ext},
    )

    chunks = _split_into_chunks(
        text_blocks=text_blocks,
        source_id=doc_source_id,
        source_version=version,
        tenant_id=tenant_id,
        allowed_roles=allowed_roles,
    )

    return source_ver, chunks, sanitized_full
