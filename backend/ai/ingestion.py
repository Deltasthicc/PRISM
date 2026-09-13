"""Lane 4 (Content AI, RAG & Evaluation) — Bounded Ingestion Engine.

Parses TXT, Markdown, PDF, DOCX, PPTX, timestamped transcripts, images, and
audio/video files into immutable SourceVersion records and Chunk objects
with exact source locators.

OCR fallback (closes the gap vs. rival teams' pipelines that already handle
scanned PDFs/legacy statistical tables): when a PDF page has no extractable
text layer, or a standalone image is uploaded directly (the "document
scanner" case), the page/image is rendered/opened and run through Tesseract
via pytesseract. pytesseract is only a thin Python wrapper -- it shells out
to the real `tesseract` binary, which is NOT bundled with the pip package.
If that binary isn't installed in this environment, OCR degrades honestly
(see `_ocr_image`) instead of silently returning empty text as if the page
had nothing on it.
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

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB -- documents (txt/md/pdf/docx/pptx/transcripts)
# Real audio/video needs far more headroom than a text document -- a few
# minutes of compressed speech easily exceeds 5 MB. MAX_AUDIO_VIDEO_SECONDS
# is the actual cost control (bounds Whisper's CPU transcription time);
# this byte cap just keeps a clearly-oversized upload from being read into
# memory at all before that duration check ever runs.
MAX_AUDIO_VIDEO_UPLOAD_BYTES = 60 * 1024 * 1024  # 60 MB
MAX_AUDIO_VIDEO_SECONDS = 600  # 10 minutes
MAX_EXTRACTED_CHARS = 120_000
MAX_PDF_PAGES = 100
MAX_PPTX_SLIDES = 100
MAX_DOCX_UNCOMPRESSED_BYTES = 40 * 1024 * 1024  # 40 MB zip-bomb guard
MAX_PPTX_UNCOMPRESSED_BYTES = 40 * 1024 * 1024  # 40 MB zip-bomb guard
MIN_EXTRACTED_CHARS = 100
# Scanned PDF pages are rendered to a bitmap at this resolution before OCR --
# 150-200 DPI is the standard tradeoff for Tesseract (materially better
# accuracy than screen resolution, without the multi-second-per-page cost of
# print-quality 300+ DPI). No separate "max pages to OCR" constant is needed:
# MAX_PDF_PAGES above already bounds the whole document (and therefore how
# many pages could ever need OCR) before this is reached.
OCR_RENDER_DPI = 175
# Guards a directly-uploaded image against a decompression-bomb-sized file
# (a small file that decodes to an enormous pixel buffer) -- checked against
# the image's header-reported dimensions *before* the pixel data is decoded,
# the same "validate before doing the expensive part" shape as the DOCX/PPTX
# zip-bomb guards below.
MAX_IMAGE_PIXELS = 40_000_000  # ~40 megapixels

AUDIO_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mp3", ".wav", ".m4a"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx", ".pptx", ".vtt", ".srt", ".transcript",
} | AUDIO_VIDEO_EXTENSIONS | IMAGE_EXTENSIONS


class ContentExtractionError(Exception):
    """Raised when a file cannot be safely or validly extracted."""


def _ocr_image(image: Any) -> str:
    """Run Tesseract OCR on a Pillow image and return the recognized text.

    pytesseract is only a thin Python wrapper -- it shells out to the real
    `tesseract` binary, which is NOT bundled with the pip package. If that
    binary isn't installed in this environment, pytesseract raises
    TesseractNotFoundError; that is turned into a clear, honest
    ContentExtractionError here rather than being allowed to crash the
    request or silently swallowed as if the page had no content.
    """
    import pytesseract

    try:
        return (pytesseract.image_to_string(image) or "").strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise ContentExtractionError(
            "OCR is not available in this environment (the tesseract binary is "
            "not installed) -- scanned pages could not be read; only pages "
            "with a text layer were extracted."
        ) from exc


def _render_pdf_page_to_image(fitz_doc: Any, page_index: int, dpi: int = OCR_RENDER_DPI) -> Any:
    """Render one PDF page to a Pillow RGB image via PyMuPDF.

    Pure Python/C-extension rendering -- no external poppler binary needed,
    unlike pdf2image.
    """
    import fitz  # PyMuPDF
    from PIL import Image

    page = fitz_doc[page_index]
    zoom = dpi / 72.0  # PyMuPDF's native page units are 72 DPI
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    mode = "RGB" if pixmap.n < 4 else "RGBA"
    return Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples).convert("RGB")


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
    ocr_unavailable_pages: list[int] = []
    fitz_doc = None  # opened lazily -- only if some page actually needs OCR

    try:
        for i, page in enumerate(reader.pages, start=1):
            extracted = (page.extract_text() or "").strip()
            if extracted:
                pages.append((
                    extracted,
                    SourceLocator(locator_type="page", index=i, label=f"Page {i}"),
                ))
                continue

            # No text layer on this page -- likely a scanned image or a
            # legacy statistical table rendered as a picture (the exact gap
            # this OCR fallback closes). Render just this page and OCR it
            # rather than silently contributing nothing for it.
            if fitz_doc is None:
                import fitz  # PyMuPDF -- renders pages without an external poppler binary
                fitz_doc = fitz.open(stream=content, filetype="pdf")

            try:
                image = _render_pdf_page_to_image(fitz_doc, i - 1)
                ocr_text = _ocr_image(image)
            except ContentExtractionError:
                # The tesseract binary itself is missing -- note it and keep
                # going rather than failing the whole document if other
                # pages already have a real text layer.
                ocr_unavailable_pages.append(i)
                continue

            if ocr_text:
                pages.append((
                    ocr_text,
                    SourceLocator(locator_type="page", index=i, label=f"Page {i} (OCR)"),
                ))
    finally:
        if fitz_doc is not None:
            fitz_doc.close()

    if ocr_unavailable_pages:
        if not pages:
            # Every page in this PDF needed OCR and none of them could be
            # read -- this is "OCR genuinely could not run here", not "the
            # document has no content". Say so honestly instead of falling
            # through to the generic too-short-text error downstream.
            raise ContentExtractionError(
                "OCR is not available in this environment (the tesseract binary is "
                "not installed) -- scanned pages could not be read; only pages "
                "with a text layer were extracted."
            )
        # Partial degradation: some pages had a real text layer, so don't
        # hard-fail the whole ingest -- just leave an honest note alongside
        # the real content instead of pretending the scanned pages were blank.
        page_list = ", ".join(str(n) for n in ocr_unavailable_pages)
        pages.append((
            f"[OCR unavailable in this environment: the tesseract binary is not "
            f"installed. Page(s) {page_list} appear to be scanned/image-only and "
            f"could not be read.]",
            SourceLocator(
                locator_type="page",
                index=ocr_unavailable_pages[0],
                label="OCR unavailable",
            ),
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


def _parse_audio_video(content: bytes) -> list[tuple[str, SourceLocator]]:
    """Real speech-to-text extraction for an uploaded audio/video file --
    reuses the exact faster-whisper tiny.en model that already powers the
    voice pipeline (ai/voice/stt.py), lazy-loaded on first use so this adds
    no extra startup cost when nobody uploads audio/video. PyAV (already a
    faster-whisper dependency) decodes the container and resamples
    in-process; no ffmpeg binary or subprocess is needed.

    A single chunk covering the whole transcript, not per-timestamp
    segments -- a real, honest scope given the same "bounded ingestion, not
    a full transcription-editing product" posture every other parser here
    holds. MAX_AUDIO_VIDEO_SECONDS bounds the actual transcription cost,
    checked before the (expensive) segment generator is ever consumed.
    """
    from ai.voice.stt import get_stt_engine

    try:
        result = get_stt_engine().transcribe_file(
            io.BytesIO(content), max_duration_seconds=MAX_AUDIO_VIDEO_SECONDS
        )
    except ValueError as exc:
        raise ContentExtractionError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive: an unparseable/corrupt media file
        raise ContentExtractionError(
            f"Could not decode this audio/video file: {exc}"
        ) from exc

    if not result.text:
        raise ContentExtractionError("No speech could be transcribed from this audio/video file.")

    return [(
        result.text,
        SourceLocator(locator_type="section", index=1, label="Full audio/video transcript"),
    )]


def _parse_image(content: bytes) -> list[tuple[str, SourceLocator]]:
    """OCR a directly uploaded image (.png/.jpg/.jpeg) -- the "document
    scanner" case: a trainer photographs a page rather than uploading a PDF.
    Distinct from `_parse_pdf`'s per-page OCR fallback, but shares the same
    `_ocr_image` path (and therefore the same honest missing-tesseract
    handling).
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise ContentExtractionError("Image parsing requires the 'Pillow' package.") from exc

    try:
        image = Image.open(io.BytesIO(content))
        # .size reads only the header -- no pixel decoding yet, so this
        # dimension check runs *before* the expensive/exploitable part,
        # mirroring the DOCX/PPTX zip-bomb guards' "validate before doing
        # the expensive work" shape.
        width, height = image.size
    except Exception as exc:
        raise ContentExtractionError("Could not parse image -- corrupted or invalid format.") from exc

    if width * height > MAX_IMAGE_PIXELS:
        raise ContentExtractionError(
            f"Image exceeds the {MAX_IMAGE_PIXELS // 1_000_000} megapixel limit "
            f"({width}x{height}) -- possible decompression bomb."
        )

    try:
        image = image.convert("RGB")
    except Exception as exc:
        raise ContentExtractionError("Could not parse image -- corrupted or invalid format.") from exc

    text = _ocr_image(image)
    if not text:
        return []
    return [(text, SourceLocator(locator_type="page", index=1, label="Page 1 (OCR)"))]


_PARSERS = {
    ".txt": _parse_txt_or_md,
    ".md": _parse_txt_or_md,
    ".pdf": _parse_pdf,
    ".docx": _parse_docx,
    ".pptx": _parse_pptx,
    ".vtt": _parse_transcript,
    ".srt": _parse_transcript,
    ".transcript": _parse_transcript,
    ".mp4": _parse_audio_video,
    ".mov": _parse_audio_video,
    ".webm": _parse_audio_video,
    ".mp3": _parse_audio_video,
    ".wav": _parse_audio_video,
    ".m4a": _parse_audio_video,
    ".png": _parse_image,
    ".jpg": _parse_image,
    ".jpeg": _parse_image,
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
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ContentExtractionError(
            f"Unsupported file type '{ext or filename}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

    # Audio/video gets a much larger byte cap -- MAX_AUDIO_VIDEO_SECONDS
    # (enforced inside _parse_audio_video, before transcription runs) is the
    # real cost control, not this upload size.
    upload_limit = MAX_AUDIO_VIDEO_UPLOAD_BYTES if ext in AUDIO_VIDEO_EXTENSIONS else MAX_UPLOAD_BYTES
    if len(content) > upload_limit:
        raise ContentExtractionError(
            f"File exceeds {upload_limit // (1024 * 1024)} MB upload limit."
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
