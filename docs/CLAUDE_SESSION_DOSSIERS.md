# Claude Code session dossiers

Two artifacts were produced in the Claude Code session that assembled this repository, ahead of and alongside the ChatGPT-authored documents also in this `docs/` folder. They are not duplicated here in full (each renders as a designed report, not plain markdown); this file records what each one covers and why it's a separate source from the other two documents.

## Volume 1 — SIH26101 Dossier

The initial ten-factor viability assessment of problem statement SIH26101, before any code existed for it: pain points, feasibility, impact, competitive/academic landscape (with citations), problem-statement clarity, the evaluator's likely lens, team-fit strategy, an AI-buildability (20/80) split, data-availability audit, and a judge Q&A stress test, closing with a Green-light verdict. It also contains a from-scratch engineering audit of the *original* SkillQuest-AI-Dungeon repository (file/line counts, a real `pytest` run, and an explicit list of what would block reusing it for this problem statement) that the pivot below responds to directly.

## Volume 2 — SIH26101 War Room

A ground-truth reconciliation pass, written after a separate ChatGPT session had produced the `SIH26101_FEASIBILITY_AND_ROADMAP.md` and (later) `SIH26101_ORCHESTRATION_PLAN.md` documents also in this folder, plus outputs from Perplexity and Gemini. It establishes precisely which of the ~16 files that ChatGPT branch touched were actually recoverable (7, at that point), cross-checks factual claims across all four AI passes (flagging, among other things, that Perplexity's claim of a PostgreSQL backend was wrong — this project runs SQLite — and that Gemini's expansion of TPAC conflicted with primary-source NSSTA material), and lays out the phased plan this repository is the first concrete step of.

## What changed between Volume 2 and this repository

Volume 2 found 7 of ~16 files recoverable from the ChatGPT session and none of it landed in any git history. This repository closes that gap: the 5 real backend/frontend files from that session (`services/curricula.py`, `services/learning_engine.py`, `services/quiz_generator.py`, `routes/learning.py`, `components/AcademyHub.jsx`) are included verbatim, and the ~9 missing pieces they depended on (`models/learning.py`, `schemas/learning.py`, `services/content_ingestion.py`, `services/learning_catalog.py`, the `/academy` and `/admin` frontend routes, the `learning` API-client export, the cross-domain seeding and room-unlock logic, and a new test file) were written fresh against the exact interface contracts those 5 files already implied, then verified by actually running the test suite in this environment rather than re-quoting an unverifiable claim from elsewhere. See the root `README.md` for the current, honest state of what that verification found.
