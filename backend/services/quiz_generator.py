"""Source-grounded MCQ generation with strict validation and local fallback."""

import asyncio
import json
import os
import random
import re

import google.generativeai as genai


VALID_BLOOM_LEVELS = {"remember", "understand", "apply", "analyse", "evaluate"}
WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z-]{4,}\b")


def _sentences(text: str) -> list[str]:
    candidates = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [sentence.strip() for sentence in candidates if 45 <= len(sentence.strip()) <= 360]


def _extract_json(raw: str):
    match = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    return json.loads((match.group(1) if match else raw).strip())


def _validate_questions(raw_questions, source_text: str, requested_count: int) -> list[dict]:
    if not isinstance(raw_questions, list):
        raise ValueError("Quiz output must be a list")
    validated = []
    compact_source = " ".join(source_text.split()).lower()
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        options = item.get("options")
        excerpt = " ".join(str(item.get("source_excerpt", "")).split())
        try:
            answer_index = int(item.get("answer_index"))
        except (TypeError, ValueError):
            continue
        if (
            not item.get("question")
            or not isinstance(options, list)
            or len(options) != 4
            or len({str(option).strip().lower() for option in options}) != 4
            or not 0 <= answer_index <= 3
            or len(excerpt) < 20
            or excerpt.lower() not in compact_source
        ):
            continue
        bloom_level = str(item.get("bloom_level", "understand")).lower()
        if bloom_level not in VALID_BLOOM_LEVELS:
            bloom_level = "understand"
        validated.append(
            {
                "question": str(item["question"]).strip(),
                "options": [str(option).strip() for option in options],
                "answer_index": answer_index,
                "explanation": str(item.get("explanation", excerpt)).strip(),
                "source_excerpt": excerpt,
                "competency": str(item.get("competency", "Source comprehension")).strip(),
                "bloom_level": bloom_level,
            }
        )
        if len(validated) == requested_count:
            break
    if len(validated) < requested_count:
        raise ValueError("The generated quiz did not pass source-grounding validation")
    return validated


def _fallback_questions(source_text: str, count: int) -> list[dict]:
    sentences = _sentences(source_text)
    if not sentences:
        raise ValueError("The material does not contain enough complete sentences for quiz generation")

    terms = []
    seen_terms = set()
    for sentence in sentences:
        for word in WORD_RE.findall(sentence):
            lowered = word.lower()
            if lowered not in seen_terms:
                terms.append(word)
                seen_terms.add(lowered)
    if len(terms) < 4:
        raise ValueError("The material needs at least four distinct concepts for an MCQ quiz")

    questions = []
    used_answers = set()
    for sentence in sentences:
        candidates = [word for word in WORD_RE.findall(sentence) if word.lower() not in used_answers]
        if not candidates:
            continue
        answer = max(candidates, key=len)
        distractors = [term for term in terms if term.lower() != answer.lower()]
        if len(distractors) < 3:
            continue
        seed = sum(ord(character) for character in sentence)
        local_random = random.Random(seed)
        options = [answer, *local_random.sample(distractors, 3)]
        local_random.shuffle(options)
        blanked = re.sub(rf"\b{re.escape(answer)}\b", "_____", sentence, count=1, flags=re.IGNORECASE)
        questions.append(
            {
                "question": f"Which term best completes this statement from the uploaded material? {blanked}",
                "options": options,
                "answer_index": options.index(answer),
                "explanation": f"The source uses “{answer}” in this statement.",
                "source_excerpt": sentence,
                "competency": "Source comprehension",
                "bloom_level": "understand",
            }
        )
        used_answers.add(answer.lower())
        if len(questions) == count:
            return questions
    raise ValueError("The material does not contain enough varied concepts for the requested quiz size")


async def generate_quiz(
    source_text: str,
    count: int,
    difficulty: str,
    language: str,
) -> tuple[list[dict], str]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_"):
        return _fallback_questions(source_text, count), "extractive-fallback"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(os.getenv("LLM_MODEL", "gemini-flash-lite-latest"))
    prompt = f"""Generate exactly {count} high-quality multiple-choice questions from ONLY the source below.
Difficulty: {difficulty}. Output language: {language}.

Rules:
- Return a JSON array only.
- Every question has exactly four unique options and one unambiguous answer.
- answer_index is a zero-based integer from 0 to 3.
- source_excerpt must be an exact, contiguous quote from the source and must prove the answer.
- Do not use facts that are absent from the source.
- Distractors must be plausible but contradicted or unsupported by the quoted source.
- Include a short explanation, competency, and Bloom level (remember, understand, apply, analyse, evaluate).

Schema per item:
{{"question":"...","options":["...","...","...","..."],"answer_index":0,"explanation":"...","source_excerpt":"...","competency":"...","bloom_level":"understand"}}

SOURCE:
{source_text[:80_000]}
"""
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt), timeout=30.0
        )
        parsed = _extract_json(response.text or "")
        return _validate_questions(parsed, source_text, count), "gemini-grounded"
    except Exception:
        return _fallback_questions(source_text, count), "extractive-fallback"
