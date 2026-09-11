"""Source-grounded MCQ generation with strict validation and local fallback."""

import asyncio
import json
import os
import random
import re

# google.generativeai is imported lazily inside generate_quiz(), not here.
# CLAUDE.md coding conventions: "keep heavy/optional SDK imports lazy". A
# top-level import made the whole module unimportable without the SDK, which
# defeated the extractive fallback below -- the one path specifically designed
# to work with no model and no network.


VALID_BLOOM_LEVELS = {"remember", "understand", "apply", "analyse", "evaluate"}
VALID_QUESTION_DIFFICULTIES = {"easy", "medium", "hard"}
WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z-]{4,}\b")


def _estimate_difficulty(sentence: str, answer: str) -> str:
    """A deterministic, explainable easy/medium/hard estimate for one
    fill-in-the-blank question, used only by the extractive fallback (no
    model available there to judge difficulty itself -- the Gemini path
    below asks the model to self-report `difficulty` per question instead,
    validated the same way `bloom_level` already is).

    The two signals available without a language model are how long/salient
    the blanked-out term is and how long/clause-heavy its carrier sentence
    is -- both genuinely correlate with how hard the fill-in-the-blank is to
    answer, so this is a real (if simple) heuristic, not an arbitrary label.
    """
    score = 0
    word_len = len(answer)
    if word_len >= 10:
        score += 2
    elif word_len >= 7:
        score += 1
    sentence_len = len(sentence)
    if sentence_len >= 220:
        score += 2
    elif sentence_len >= 140:
        score += 1
    clause_breaks = sentence.count(",") + sentence.count(";") + sentence.count(":")
    if clause_breaks >= 2:
        score += 1
    if score >= 4:
        return "hard"
    if score >= 2:
        return "medium"
    return "easy"


def _sentences(text: str) -> list[str]:
    candidates = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [sentence.strip() for sentence in candidates if 45 <= len(sentence.strip()) <= 360]


def _extract_json(raw: str):
    match = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    return json.loads((match.group(1) if match else raw).strip())


def _derive_answer_index(item: dict) -> int | None:
    """Never trust a model-stated `answer_index` on its own -- an LLM can
    (and does) produce an explanation that argues for one option while a
    separately-stated index field points at another, with nothing to catch
    the mismatch. Instead require the model to independently judge each
    option's truth value (`option_truth`, one bool per option) and derive
    the index from that structural constraint: a normal question must have
    exactly one true option; a NOT/EXCEPT-style question (`is_negation`)
    must have exactly one false option among three true ones. Returns None
    if the option_truth array doesn't satisfy that constraint, so the
    caller can reject the item outright rather than guess.
    """
    truth = item.get("option_truth")
    if not isinstance(truth, list) or len(truth) != 4 or not all(isinstance(t, bool) for t in truth):
        return None
    is_negation = bool(item.get("is_negation", False))
    target = False if is_negation else True
    matches = [i for i, t in enumerate(truth) if t is target]
    if len(matches) != 1:
        return None
    return matches[0]


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
        answer_index = _derive_answer_index(item)
        if (
            answer_index is None
            or not item.get("question")
            or not isinstance(options, list)
            or len(options) != 4
            or len({str(option).strip().lower() for option in options}) != 4
            or len(excerpt) < 20
            or excerpt.lower() not in compact_source
        ):
            continue
        bloom_level = str(item.get("bloom_level", "understand")).lower()
        if bloom_level not in VALID_BLOOM_LEVELS:
            bloom_level = "understand"
        question_difficulty = str(item.get("difficulty", "medium")).lower()
        if question_difficulty not in VALID_QUESTION_DIFFICULTIES:
            question_difficulty = "medium"
        validated.append(
            {
                "question": str(item["question"]).strip(),
                "options": [str(option).strip() for option in options],
                "answer_index": answer_index,
                "explanation": str(item.get("explanation", excerpt)).strip(),
                "source_excerpt": excerpt,
                "competency": str(item.get("competency", "Source comprehension")).strip(),
                "bloom_level": bloom_level,
                "difficulty": question_difficulty,
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
                "difficulty": _estimate_difficulty(sentence, answer),
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

    try:
        import google.generativeai as genai
    except ImportError:
        # SDK absent (a lean deployment, or the wrong interpreter). Same
        # outcome as an unconfigured key: real questions, quoted from the
        # source, just without the model.
        return _fallback_questions(source_text, count), "extractive-fallback"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(os.getenv("LLM_MODEL", "gemini-flash-lite-latest"))
    prompt = f"""Generate exactly {count} high-quality multiple-choice questions from ONLY the source below.
Difficulty: {difficulty}. Output language: {language}.

Rules:
- Return a JSON array only.
- Every question has exactly four unique options and one unambiguous answer.
- Do NOT state which option is correct via an index. Instead, judge each of the four options
  independently and return `option_truth`, a 4-item boolean array: true if that option's
  statement is factually correct per the source, false if it is not. Exactly one option must be
  true, UNLESS the question itself is a NOT/EXCEPT-style question (asking which option is the
  odd one out) -- in that case set `is_negation` to true and make exactly three options true
  (correct statements) and one false (the actual answer to a NOT/EXCEPT question).
- source_excerpt must be an exact, contiguous quote from the source and must prove the answer.
- Do not use facts that are absent from the source.
- Distractors must be plausible but contradicted or unsupported by the quoted source.
- Include a short explanation, competency, and Bloom level (remember, understand, apply, analyse, evaluate).
- Also include a per-question `difficulty` (easy, medium, or hard) based on how much reasoning the question demands
  from the source, independent of the overall quiz difficulty setting above -- a quiz can mix difficulties.

Schema per item:
{{"question":"...","options":["...","...","...","..."],"option_truth":[true,false,false,false],"is_negation":false,"explanation":"...","source_excerpt":"...","competency":"...","bloom_level":"understand","difficulty":"medium"}}

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
