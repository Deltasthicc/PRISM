"""Lane 4 (Content AI, RAG & Evaluation) — Security & Defense Controls.

Defends against prompt injection within user queries and uploaded documents,
sanitizes untrusted inputs, wraps retrieved content in data frames, and
prevents instruction leakage.
"""
from __future__ import annotations

import re
from typing import Any

# Known prompt injection / instruction override patterns (case-insensitive)
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s+override", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|in)\b", re.IGNORECASE),
    re.compile(r"bypass\s+all\s+(guardrails|filters|rules)", re.IGNORECASE),
    re.compile(r"developer\s+mode\s+(enabled|on)", re.IGNORECASE),
    re.compile(r"output\s+the\s+(system\s+prompt|secret\s+key|api\s+key|credentials?)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
    re.compile(r"act\s+as\s+an\s+unrestricted", re.IGNORECASE),
]

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def detect_prompt_injection(text: str) -> tuple[bool, str | None]:
    """Scan text for common adversarial prompt injection patterns.

    Returns:
        (is_injection, matched_pattern_description)
    """
    if not text:
        return False, None
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, f"Detected potential prompt override attempt: '{match.group(0)}'"
    return False, None


def sanitize_untrusted_text(text: str, max_chars: int = 120_000) -> str:
    """Sanitize untrusted text from uploaded documents or user queries.

    Strips null bytes and non-printable control characters, normalizes line
    breaks, and enforces a strict character boundary.
    """
    if not text:
        return ""
    # Strip dangerous control characters while preserving standard \t, \n, \r
    cleaned = _CONTROL_CHAR_RE.sub("", text)
    # Normalize CRLF to LF
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    return cleaned[:max_chars].strip()


def format_evidence_block(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks as strictly delimited untrusted DATA.

    Wraps each chunk in XML-style tags with explicit metadata attributes so
    the LLM treats the text purely as reference facts, never as executable
    instructions.
    """
    if not chunks:
        return "<retrieved_evidence count=\"0\" />"

    formatted_blocks = ["<retrieved_evidence>"]
    for i, c in enumerate(chunks, start=1):
        chunk_id = c.get("chunk_id", f"chunk-{i}")
        source_id = c.get("source_id", "unknown")
        locators = c.get("locators", [])
        locator_str = "; ".join(loc.get("label", "") for loc in locators) if locators else "N/A"
        raw_text = c.get("text", "").strip()

        # Sanitize any embedded closing tags to prevent escape attacks
        escaped_text = raw_text.replace("</evidence_chunk>", "&lt;/evidence_chunk&gt;")

        formatted_blocks.append(
            f'  <evidence_chunk id="{chunk_id}" source="{source_id}" locators="{locator_str}">\n'
            f"    <![CDATA[\n{escaped_text}\n    ]]>\n"
            f"  </evidence_chunk>"
        )
    formatted_blocks.append("</retrieved_evidence>")
    return "\n".join(formatted_blocks)
