# Content/AI service interface and evaluation fixtures contract

Owner: Lane 4 (Content AI, RAG & Evaluation)
Consumers: Lanes 1, 5, 6
Change approval: Lane 3, Lane 5 and a named domain reviewer

Status: **NOT YET DEFINED** — this is a scaffold. `backend/services/quiz_generator.py` and
`content_ingestion.py` are the current, tested implementation (context-stuffing generation with
source-span validation, not retrieval RAG — see `README.md` and `CODEX.md`).

## What this contract must define once implemented

- Source, source-version and chunk record shapes, including page/section locators and hashes.
- The retrieval interface Lane 1/5 can call without knowing about embeddings or the vector store.
- The evaluation/gold-set fixture format used to report citation correctness, groundedness,
  answer validity and Recall@K (`SIH26101_TEAM_ORCHESTRATION.md` section 5, Lane 4 acceptance
  evidence).
- The item lifecycle states (`draft -> auto_checked -> expert_review -> approved -> pilot ->
  published -> retired`) and who may move an item between them.
- The bounded learner-assistant's request/response shape and its abstention/escalation contract
  (`docs/SIH26101_PROBLEM_STATEMENT.md` PS-06).

## Change process

See `SIH26101_TEAM_ORCHESTRATION.md` section 8, "Cross-lane handoff".
