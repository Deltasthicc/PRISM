"""Step 1 of the voice-model domain-adaptation pipeline.

Extracts real, already-committed domain text from this repo -- competency
labels/descriptions (services/curricula.py) and every hand-authored quiz
question + its source excerpt (data/hand_authored_questions.json) -- into a
flat list of training sentences for TTS-based STT fine-tuning.

Why this text and not something invented: it is the exact vocabulary a real
learner's voice queries will contain (government-body acronyms like DARPG,
NITI Aayog, MoSPI, PLFS; domain terms like Sevottam, sufficient statistic,
hazard rate). The stock faster-whisper tiny.en model measurably mis-
transcribes this vocabulary today (confirmed by hand before writing this
pipeline: "DARPG Sevottam" -> "dark, sevetam" on a clean, artifact-free
TTS-synthesized sample) -- this is the concrete problem this fine-tune fixes.

Run from backend/: python scripts/voice_finetuning/1_prepare_domain_corpus.py
Writes scripts/voice_finetuning/corpus.txt (one sentence per line, deduped).
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.curricula import CURRICULA  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_PATH = os.path.join(HERE, "..", "..", "data", "hand_authored_questions.json")
OUT_PATH = os.path.join(HERE, "corpus.txt")

# Whisper fine-tuning wants reasonably short utterances (a few seconds of
# speech each) -- long multi-sentence excerpts are split on sentence
# boundaries rather than fed in as one huge, unnaturally long "utterance".
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
MIN_CHARS = 8
MAX_CHARS = 220


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def collect_curricula_sentences() -> list[str]:
    sentences = []
    for curriculum in CURRICULA.values():
        for field in ("name", "domain", "description", "audience", "level_band"):
            value = curriculum.get(field)
            if value:
                sentences.extend(_split_sentences(_clean(value)))
        for competency in curriculum.get("competencies", []):
            for field in ("label", "description"):
                value = competency.get(field)
                if value:
                    sentences.extend(_split_sentences(_clean(value)))
    return sentences


def collect_question_sentences() -> list[str]:
    with open(QUESTIONS_PATH, encoding="utf-8") as handle:
        data = json.load(handle)

    sentences = []
    for item in data.get("questions", []):
        question = item.get("question", "")
        # Fill-in-blank markers ("_____") read oddly as speech -- fine for
        # training text-to-speech input, but strip the marker itself so the
        # synthesized utterance is natural spoken English.
        question = question.replace("_____", "")
        if question:
            sentences.extend(_split_sentences(_clean(question)))

        excerpt = item.get("source_excerpt", "")
        if excerpt:
            sentences.extend(_split_sentences(_clean(excerpt)))

        for option in item.get("options") or []:
            if option:
                sentences.append(_clean(option))
    return sentences


def main() -> None:
    all_sentences = collect_curricula_sentences() + collect_question_sentences()

    seen = set()
    deduped = []
    for s in all_sentences:
        if MIN_CHARS <= len(s) <= MAX_CHARS and s not in seen:
            seen.add(s)
            deduped.append(s)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(deduped) + "\n")

    print(f"Wrote {len(deduped)} unique training sentences to {OUT_PATH}")


if __name__ == "__main__":
    main()
