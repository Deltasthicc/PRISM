"""Lane 4 Tests — Safe Bounded Content Ingestion & Provenance Retention."""
import io
import zipfile
import pytest

from ai.ingestion import (
    ALLOWED_EXTENSIONS,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_UPLOAD_BYTES,
    ContentExtractionError,
    ingest_document,
)
from services.content_ingestion import extract_text


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


def test_backward_compatible_extract_text_service():
    text = (
        "Consumer Price Index calculation requires Laspeyres price index formula. "
        "Base year expenditure weights are derived from the Household Consumer Expenditure Survey."
    )
    result = extract_text("cpi.txt", text.encode("utf-8"))
    assert "Consumer Price Index" in result
    assert "Household Consumer Expenditure" in result
