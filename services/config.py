"""
Central config loader for the standalone AI/ML services layer.

Loads services/.env via python-dotenv and exposes everything as module-level
constants. No database settings live here -- the main backend owns
DATABASE_URL and all other game-server config.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- LLM provider -----------------------------------------------------------
# Gemini-only -- there is no provider-branching logic anywhere in this
# codebase (unlike the README's original anthropic/openai-swappable design).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-flash-lite-latest")

# --- Game config -------------------------------------------------------------
DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "Data Structures & Algorithms")

# --- NLP judge thresholds -----------------------------------------------------
JUDGE_CORRECT_THRESHOLD = float(os.getenv("JUDGE_CORRECT_THRESHOLD", "0.65"))
JUDGE_PARTIAL_THRESHOLD = float(os.getenv("JUDGE_PARTIAL_THRESHOLD", "0.30"))
JUDGE_LOCAL_CORRECT_THRESHOLD = float(
    os.getenv("JUDGE_LOCAL_CORRECT_THRESHOLD", "0.50")
)
# Widened from the README's literal 0.55-0.70 -- see .env.example for the
# measured-score rationale (all-MiniLM-L6-v2 paraphrase scores ranged 0.52-0.83
# on real DSA test pairs, wider than the originally specified band).
JUDGE_FALLBACK_RANGE_LOW = float(os.getenv("JUDGE_FALLBACK_RANGE_LOW", "0.45"))
JUDGE_FALLBACK_RANGE_HIGH = float(os.getenv("JUDGE_FALLBACK_RANGE_HIGH", "0.85"))

# --- RL tuner ------------------------------------------------------------------
RL_HARD_THRESHOLD = float(os.getenv("RL_HARD_THRESHOLD", "0.80"))
RL_MEDIUM_THRESHOLD = float(os.getenv("RL_MEDIUM_THRESHOLD", "0.50"))
RL_EPSILON = float(os.getenv("RL_EPSILON", "0.1"))
