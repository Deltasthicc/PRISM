"""Lane 4 Tests — Safe Bounded Content Ingestion & Provenance Retention."""
import io
import wave
import zipfile
import pytest

from ai.ingestion import (
    ALLOWED_EXTENSIONS,
    AUDIO_VIDEO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MAX_AUDIO_VIDEO_SECONDS,
    MAX_AUDIO_VIDEO_UPLOAD_BYTES,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_UPLOAD_BYTES,
    ContentExtractionError,
    ingest_document,
)
from services.content_ingestion import extract_text


def _make_wav_bytes(duration_seconds: float, sample_rate: int = 16000) -> bytes:
    """A real, valid WAV file of silence -- enough to exercise the actual
    PyAV decode + faster-whisper inference path end to end without needing
    a real speech sample or network access. Silence transcribing to empty
    text (see test below) is itself the meaningful assertion: it proves the
    real pipeline ran, not a mock -- the same "live smoke test on silence"
    approach tests/test_content_ai_voice.py's
    test_live_faster_whisper_tiny_en_smoke already uses for the streaming
    STT path."""
    num_samples = int(duration_seconds * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


def _create_dummy_pptx_bytes() -> bytes:
    """Create a minimal, valid PPTX zip structure containing two slides."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '  <Default Extension="xml" ContentType="application/xml"/>\n'
            "</Types>",
        )
        # Slide 1 XML
        slide1 = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
            "  <p:cSld><p:spTree>\n"
            "    <p:sp><p:txBody>\n"
            "      <a:p><a:r><a:t>Official Statistics: Sampling Theory and Frame Construction</a:t></a:r></a:p>\n"
            "      <a:p><a:r><a:t>Primary sampling units are selected via probability proportional to size.</a:t></a:r></a:p>\n"
            "    </p:txBody></p:sp>\n"
            "  </p:spTree></p:cSld>\n"
            "</p:sld>"
        )
        # Slide 2 XML
        slide2 = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
            "  <p:cSld><p:spTree>\n"
            "    <p:sp><p:txBody>\n"
            "      <a:p><a:r><a:t>Non-Response Adjustment in National Surveys</a:t></a:r></a:p>\n"
            "      <a:p><a:r><a:t>Weighting classes rescale base design weights to eliminate unit non-response bias.</a:t></a:r></a:p>\n"
            "    </p:txBody></p:sp>\n"
            "  </p:spTree></p:cSld>\n"
            "</p:sld>"
        )
        z.writestr("ppt/slides/slide1.xml", slide1)
        z.writestr("ppt/slides/slide2.xml", slide2)
    return buf.getvalue()


def test_txt_and_markdown_ingestion_preserves_section_locators():
    md_content = """# National Statistical Architecture

## Legal Framework
The Collection of Statistics Act empowers national statistical authorities to mandate data reporting from commercial establishments.

## Field Operations
Field enumerators conduct face-to-face interviews using computer-assisted personal interviewing (CAPI) tablets.
Quality assurance inspectors perform concurrent re-interviews on a five percent subsample.
"""
    source_ver, chunks, extracted_text = ingest_document(
        filename="statistical_architecture.md",
        content=md_content.encode("utf-8"),
        source_id="src-md-001",
    )

    assert source_ver.source_id == "src-md-001"
    assert source_ver.content_type == "md"
    assert source_ver.character_count == len(extracted_text)
    assert len(source_ver.sha256) == 64
    assert len(chunks) >= 2

    # Verify section locators exist on chunks
    loc_labels = [loc.label for c in chunks for loc in c.locators]
    assert any("Legal Framework" in lbl for lbl in loc_labels)
    assert any("Field Operations" in lbl for lbl in loc_labels)


def test_pptx_slide_ingestion_and_slide_locators():
    pptx_bytes = _create_dummy_pptx_bytes()
    source_ver, chunks, extracted_text = ingest_document(
        filename="sampling_theory.pptx",
        content=pptx_bytes,
        source_id="src-pptx-001",
    )

    assert source_ver.content_type == "pptx"
    assert "probability proportional to size" in extracted_text
    assert "Non-Response Adjustment" in extracted_text

    # Verify slide locators
    slide_locators = [loc for c in chunks for loc in c.locators if loc.locator_type == "slide"]
    assert len(slide_locators) >= 2
    labels = [loc.label for loc in slide_locators]
    assert "Slide 1" in labels
    assert "Slide 2" in labels


def test_vtt_transcript_ingestion_with_timecode_locators():
    vtt_content = """WEBVTT

00:00:10.000 --> 00:00:25.000
Welcome to the National Accounts statistics lecture on Gross Domestic Product estimation.

00:00:26.000 --> 00:00:45.000
Gross Value Added is measured at basic prices, and GDP equals GVA plus product taxes minus product subsidies.

00:00:46.000 --> 00:01:05.000
Double deflation is the internationally recommended method for compiling constant price value added in manufacturing.
"""
    source_ver, chunks, extracted_text = ingest_document(
        filename="gdp_lecture.vtt",
        content=vtt_content.encode("utf-8"),
        source_id="src-vtt-001",
    )

    assert source_ver.content_type == "vtt"
    assert "Gross Value Added" in extracted_text
    assert "Double deflation" in extracted_text

    timecode_locators = [loc for c in chunks for loc in c.locators if loc.locator_type == "timecode"]
    assert len(timecode_locators) >= 2
    assert any("00:00:26" in loc.label for loc in timecode_locators)


def test_oversized_upload_rejection():
    oversized = b"a" * (MAX_UPLOAD_BYTES + 1024)
    with pytest.raises(ContentExtractionError) as exc_info:
        ingest_document("oversized.txt", oversized)
    assert "upload limit" in str(exc_info.value)


def test_unsupported_file_extension_rejection():
    with pytest.raises(ContentExtractionError) as exc_info:
        ingest_document("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00")
    assert "Unsupported file type" in str(exc_info.value)


def test_too_short_extracted_text_rejection():
    with pytest.raises(ValueError) as exc_info:
        ingest_document("tiny.txt", b"Too short text.")
    assert "too short" in str(exc_info.value)


def test_audio_video_extensions_are_registered():
    assert AUDIO_VIDEO_EXTENSIONS <= ALLOWED_EXTENSIONS
    assert {".mp4", ".mov", ".webm", ".mp3", ".wav", ".m4a"} == AUDIO_VIDEO_EXTENSIONS


def test_wav_ingestion_runs_the_real_stt_pipeline_and_rejects_silence():
    """A real .wav file goes through the actual PyAV decode + faster-whisper
    inference (no mocking) -- silence correctly produces no transcribable
    speech, which is itself proof the real pipeline ran rather than a stub.
    This is a slow test (loads the real tiny.en model on first use)."""
    wav_bytes = _make_wav_bytes(duration_seconds=1.0)
    with pytest.raises(ContentExtractionError) as exc_info:
        ingest_document("meeting.wav", wav_bytes)
    assert "No speech could be transcribed" in str(exc_info.value)


def test_audio_video_gets_a_much_larger_upload_cap_than_documents():
    # Between the two limits: too big for a document, fine for audio/video.
    oversized_for_docs = b"\x00" * (MAX_UPLOAD_BYTES + 1024)
    assert len(oversized_for_docs) < MAX_AUDIO_VIDEO_UPLOAD_BYTES

    with pytest.raises(ContentExtractionError) as doc_exc:
        ingest_document("notes.txt", oversized_for_docs)
    assert "upload limit" in str(doc_exc.value)

    # The same byte count, but as a .wav, is rejected for a DIFFERENT
    # reason (unparseable as a real WAV container) -- never the upload-size
    # check, proving the larger cap is actually being applied for this
    # extension rather than merely documented.
    with pytest.raises(ContentExtractionError) as audio_exc:
        ingest_document("clip.wav", oversized_for_docs)
    assert "upload limit" not in str(audio_exc.value)


def test_oversized_audio_video_upload_is_still_rejected():
    too_big = b"\x00" * (MAX_AUDIO_VIDEO_UPLOAD_BYTES + 1024)
    with pytest.raises(ContentExtractionError) as exc_info:
        ingest_document("huge_video.mp4", too_big)
    assert "upload limit" in str(exc_info.value)


def test_audio_video_over_the_duration_limit_is_rejected_before_transcription(monkeypatch):
    """Caps the duration limit down to something a fast test can actually
    exceed, rather than generating 10 real minutes of audio -- the
    assertion (rejected for being too long, not for any other reason) is
    exactly the same real check as production's MAX_AUDIO_VIDEO_SECONDS."""
    monkeypatch.setattr("ai.ingestion.MAX_AUDIO_VIDEO_SECONDS", 1)
    wav_bytes = _make_wav_bytes(duration_seconds=3.0)

    with pytest.raises(ContentExtractionError) as exc_info:
        ingest_document("long_clip.wav", wav_bytes)
    assert "exceeding" in str(exc_info.value) and "limit" in str(exc_info.value)


def test_backward_compatible_extract_text_service():
    text = (
        "Consumer Price Index calculation requires Laspeyres price index formula. "
        "Base year expenditure weights are derived from the Household Consumer Expenditure Survey."
    )
    result = extract_text("cpi.txt", text.encode("utf-8"))
    assert "Consumer Price Index" in result
    assert "Household Consumer Expenditure" in result


# ---------------------------------------------------------------------------
# OCR fallback (scanned PDFs / legacy statistical tables / direct image
# uploads -- the "document scanner" case). These use the real Tesseract OCR
# pipeline end-to-end wherever possible, not mocks: pytesseract is only a
# thin wrapper around the actual `tesseract` binary, and OCR accuracy is
# inherently fuzzy, so assertions check for recognizable substrings rather
# than exact text equality.
# ---------------------------------------------------------------------------

_OCR_SAMPLE_LINES = [
    "PRISM STATISTICS TRAINING",
    "Household Consumer Expenditure Survey",
    "Sampling frame construction procedures",
    "for official government use only",
]


def _make_ocr_test_image_bytes(lines: list[str] = _OCR_SAMPLE_LINES, font_size: int = 40, width: int = 1000) -> bytes:
    """A real rendered PNG containing actual text, built entirely with
    Pillow's own bundled scalable default font (`ImageFont.load_default`,
    size-aware since Pillow 10.1) -- no system font dependency, so this
    renders identically on any CI runner. Used to exercise the real
    Tesseract OCR pipeline, not a mock."""
    from PIL import Image, ImageDraw, ImageFont

    line_height = font_size + 20
    height = line_height * len(lines) + 40
    image = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=font_size)
    y = 20
    for line in lines:
        draw.text((20, y), line, fill="black", font=font)
        y += line_height

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _make_scanned_pdf_bytes(image_png_bytes: bytes, page_width: int = 1000, page_height: int = 300) -> bytes:
    """A single-page PDF containing only a rendered image -- no text layer at
    all, built directly with PyMuPDF so pypdf's `extract_text()` on it
    returns empty, exactly like a real scanned document, and _parse_pdf must
    fall back to rendering + OCR-ing the page itself."""
    import fitz

    doc = fitz.open()
    try:
        page = doc.new_page(width=page_width, height=page_height)
        page.insert_image(fitz.Rect(0, 0, page_width, page_height), stream=image_png_bytes)
        return doc.tobytes()
    finally:
        doc.close()


def _make_mixed_pdf_bytes(real_text: str, image_png_bytes: bytes) -> bytes:
    """A two-page PDF: page 1 has a genuine embedded text layer (extractable
    by pypdf directly), page 2 is image-only (no text layer, needs OCR)."""
    import fitz

    doc = fitz.open()
    try:
        text_page = doc.new_page(width=600, height=200)
        text_page.insert_text((50, 100), real_text, fontsize=12)
        image_page = doc.new_page(width=1000, height=300)
        image_page.insert_image(fitz.Rect(0, 0, 1000, 300), stream=image_png_bytes)
        return doc.tobytes()
    finally:
        doc.close()


def test_png_jpg_jpeg_extensions_are_registered():
    assert IMAGE_EXTENSIONS <= ALLOWED_EXTENSIONS
    assert {".png", ".jpg", ".jpeg"} == IMAGE_EXTENSIONS


def test_direct_image_upload_ocr_extracts_recognizable_text():
    """Real Pillow-rendered PNG, real Tesseract OCR -- no mocking. This is
    the "document scanner" case: a trainer photographs a page and uploads
    the image directly rather than a PDF."""
    png_bytes = _make_ocr_test_image_bytes()

    source_ver, chunks, extracted_text = ingest_document(
        filename="scanned_notes.png",
        content=png_bytes,
        source_id="src-img-ocr-001",
    )

    assert source_ver.content_type == "png"
    upper = extracted_text.upper()
    assert "STATISTIC" in upper
    assert "SURVEY" in upper

    ocr_locators = [loc for c in chunks for loc in c.locators if "OCR" in loc.label]
    assert ocr_locators


def test_scanned_pdf_page_is_extracted_via_ocr_fallback():
    """A synthetic single-page 'scanned' PDF (image only, no text layer) --
    _parse_pdf must render the page and OCR it rather than treating it as
    empty."""
    png_bytes = _make_ocr_test_image_bytes()
    pdf_bytes = _make_scanned_pdf_bytes(png_bytes)

    source_ver, chunks, extracted_text = ingest_document(
        filename="scanned_report.pdf",
        content=pdf_bytes,
        source_id="src-scanned-pdf-001",
    )

    assert source_ver.content_type == "pdf"
    upper = extracted_text.upper()
    assert "STATISTIC" in upper
    assert "SURVEY" in upper

    ocr_page_locators = [
        loc for c in chunks for loc in c.locators
        if loc.locator_type == "page" and "OCR" in loc.label
    ]
    assert ocr_page_locators
    assert ocr_page_locators[0].label == "Page 1 (OCR)"


def test_mixed_pdf_with_real_text_page_and_scanned_page_extracts_both():
    """One page with a genuine text layer, one scanned/image-only page --
    both must contribute text; the real-text page must NOT be routed through
    OCR, and the scanned page must be."""
    real_text = (
        "The Ministry of Statistics conducts periodic labour force surveys "
        "nationwide across sampled households for employment estimation."
    )
    png_bytes = _make_ocr_test_image_bytes()
    pdf_bytes = _make_mixed_pdf_bytes(real_text, png_bytes)

    source_ver, chunks, extracted_text = ingest_document(
        filename="mixed_report.pdf",
        content=pdf_bytes,
        source_id="src-mixed-pdf-001",
    )

    assert "Ministry of Statistics" in extracted_text
    assert "STATISTIC" in extracted_text.upper()

    labels = [loc.label for c in chunks for loc in c.locators]
    assert "Page 1" in labels  # real text layer -- no OCR involved
    assert "Page 2 (OCR)" in labels  # image-only page -- OCR fallback used


def test_tesseract_not_installed_raises_honest_content_extraction_error(monkeypatch):
    """The one case that's fine to mock: pytesseract.image_to_string raising
    TesseractNotFoundError simulates the tesseract binary genuinely missing
    from the environment (can't reliably force this any other way). The
    fallback must degrade honestly -- a clear ContentExtractionError, never a
    silent empty result pretending the page had nothing on it."""
    import pytesseract

    def _raise_not_found(*args, **kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", _raise_not_found)

    png_bytes = _make_ocr_test_image_bytes()
    with pytest.raises(ContentExtractionError) as exc_info:
        ingest_document("scanned_photo.png", png_bytes, source_id="src-no-tess-001")

    message = str(exc_info.value)
    assert "tesseract binary is not installed" in message
    assert "OCR is not available" in message


def test_mixed_pdf_degrades_gracefully_when_tesseract_is_missing(monkeypatch):
    """A document with SOME real-text pages must not hard-fail just because
    tesseract is unavailable for its scanned pages -- the real text should
    still come through, with an honest note about what could not be read,
    rather than either crashing or silently dropping the scanned page."""
    import pytesseract

    def _raise_not_found(*args, **kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", _raise_not_found)

    real_text = (
        "The Ministry of Statistics conducts periodic labour force surveys "
        "nationwide across sampled households for employment estimation."
    )
    png_bytes = _make_ocr_test_image_bytes()
    pdf_bytes = _make_mixed_pdf_bytes(real_text, png_bytes)

    source_ver, chunks, extracted_text = ingest_document(
        filename="mixed_report_no_tesseract.pdf",
        content=pdf_bytes,
        source_id="src-mixed-no-tess-001",
    )

    assert "Ministry of Statistics" in extracted_text
    assert "OCR unavailable" in extracted_text
    assert "tesseract binary is not installed" in extracted_text


def test_fully_scanned_pdf_raises_honest_error_when_tesseract_is_missing(monkeypatch):
    """When literally every page needs OCR and none can be read, this must
    surface as "OCR genuinely could not run here", not the generic
    too-short-text failure."""
    import pytesseract

    def _raise_not_found(*args, **kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", _raise_not_found)

    png_bytes = _make_ocr_test_image_bytes()
    pdf_bytes = _make_scanned_pdf_bytes(png_bytes)

    with pytest.raises(ContentExtractionError) as exc_info:
        ingest_document("fully_scanned_no_tesseract.pdf", pdf_bytes, source_id="src-scanned-no-tess-001")

    assert "OCR is not available" in str(exc_info.value)


def test_oversized_image_pixel_count_is_rejected(monkeypatch):
    """Guards against a decompression-bomb-sized image -- checked against
    header-reported dimensions before any pixel data is decoded. The real
    limit (40 megapixels) is impractical to build a real fixture for in a
    fast test, so it's lowered here to something a small real image can
    exceed, the same technique this file already uses for
    MAX_AUDIO_VIDEO_SECONDS above."""
    monkeypatch.setattr("ai.ingestion.MAX_IMAGE_PIXELS", 100)

    png_bytes = _make_ocr_test_image_bytes(lines=["small"], font_size=20, width=200)
    with pytest.raises(ContentExtractionError) as exc_info:
        ingest_document("huge.png", png_bytes, source_id="src-bomb-001")
    assert "megapixel limit" in str(exc_info.value)
