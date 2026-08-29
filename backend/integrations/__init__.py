"""Lane 5 (Product API, Integrations & Analytics) — reserved for the `LearningProviderAdapter`
interface and the simulated/live iGOT and NSSTA adapters described in
SIH26101_TEAM_ORCHESTRATION.md section 5 (Lane 5) and docs/SIH26101_PROBLEM_STATEMENT.md
PS-05/PS-17. Contract: docs/contracts/provider-adapter.md.

Empty scaffold. `backend/services/learning_catalog.py` remains the current, honest
catalog-fallback implementation until a real adapter lands here. An environment variable alone is
never proof that an integration works (CODEX.md "Architecture invariants") — a live adapter needs
the authorized endpoint/credentials/sandbox tracked as BLOCKED-EXTERNAL in
SIH26101_MASTER_CHECKLIST.md section 4.3.
"""
