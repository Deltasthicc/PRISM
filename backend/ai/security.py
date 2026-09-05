"""Lane 4 (Content AI, RAG & Evaluation) — Security & Defense Controls.

Defends against prompt injection within user queries and uploaded documents,
sanitizes untrusted inputs, wraps retrieved content in data frames, and
prevents instruction leakage.

NOTE ON LIMITATIONS:
Regex-based heuristic pattern matching is one layer of defense in depth. It
does not mathematically guarantee 100% detection of all possible adversarial
jailbreaks or zero-day obfuscations. It is paired with XML CDATA data-framing,
strict system prompt constraints, and pre-retrieval access boundary enforcement.
"""
from __future__ import annotations

import re
from typing import Any

# Known prompt injection / instruction override patterns (case-insensitive)
_INJECTION_PATTERNS = [
    # Direct instruction overrides
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier|past)\s+(instructions?|directions?|rules?|prompts?)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above|earlier|past)\s+(instructions?|directions?|rules?|guidance|policies)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|above|earlier|past|your)\s+(instructions?|directions?|rules?|guidance|training|prompts?)", re.IGNORECASE),
    re.compile(r"set\s+aside\s+(all\s+)?(previous|prior|earlier|existing)\s+(instructions?|guidance|rules?|policies)", re.IGNORECASE),
    re.compile(r"drop\s+(all\s+)?(previous|prior|earlier)\s+(instructions?|rules?|constraints?)", re.IGNORECASE),
    re.compile(r"discard\s+(all\s+)?(previous|prior|earlier)\s+(instructions?|rules?|guidelines?)", re.IGNORECASE),
    
    # System override and mode hijacking
    re.compile(r"system\s+override", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|in)\b", re.IGNORECASE),
    re.compile(r"bypass\s+all\s+(guardrails|filters|rules|checks)", re.IGNORECASE),
    re.compile(r"developer\s+mode\s+(enabled|on)", re.IGNORECASE),
    re.compile(r"disable\s+(all\s+)?(safety|security|content)\s+(filters|checks|guardrails|restrictions?)", re.IGNORECASE),
    re.compile(r"override\s+(all\s+)?(system|security|safety)\s+(rules|controls|policies|guardrails)", re.IGNORECASE),
    
    # Exfiltration of confidential prompt / credentials
    re.compile(r"(output|print|reveal|show|display|leak)\s+(the\s+|your\s+|all\s+)?(system\s+prompt|hidden\s+prompt|secret\s+key|api\s+key|credentials?|internal\s+instructions?|secret\s+instructions?)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
    re.compile(r"act\s+as\s+an?\s+(unrestricted|unfiltered|jailbroken|evil)", re.IGNORECASE),
    re.compile(r"pretend\s+(to\s+be|that\s+you\s+are)\s+an?\s+(unrestricted|unfiltered)", re.IGNORECASE),
    re.compile(r"from\s+now\s+on\s*,\s*(you\s+are|act\s+as|behave\s+as)", re.IGNORECASE),
]

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def detect_prompt_injection(text: str) -> tuple[bool, str | None]:
    """Scan text for adversarial prompt injection and override patterns.

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
        return '<retrieved_evidence count="0" />'

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
