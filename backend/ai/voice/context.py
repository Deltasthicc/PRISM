"""
Lane 4 (Content AI & Voice) — Bounded Conversation Context.

Manages bounded, in-memory conversational turns with FIFO eviction and
character/turn caps. No database persistence, no disk storage, no raw audio.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass
from datetime import datetime, timezone

DEFAULT_MAX_TURNS = 5
DEFAULT_MAX_TOTAL_CHARS = 4000


@dataclass(frozen=True)
class ConversationTurn:
    """An immutable record of a single conversational turn."""
    turn_index: int
    user_transcript: str
    assistant_answer: str
    created_at: str
    char_count: int


class ConversationContextManager:
    """In-memory sliding window of recent conversational turns.

    Enforces both maximum turn count and maximum total character size.
    Evicts oldest turns first (FIFO) when bounds are reached.
    """

    def __init__(
        self,
        max_turns: int = DEFAULT_MAX_TURNS,
        max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
    ) -> None:
        self.max_turns = max(1, max_turns)
        self.max_total_chars = max(100, max_total_chars)
        self._turns: collections.deque[ConversationTurn] = collections.deque()
        self._total_chars: int = 0
        self._turn_counter: int = 0

    @property
    def turn_count(self) -> int:
        """Current number of retained turns in memory."""
        return len(self._turns)

    @property
    def total_chars(self) -> int:
        """Total characters across all currently retained turns."""
        return self._total_chars

    def add_turn(self, user_transcript: str, assistant_answer: str) -> ConversationTurn:
        """Add a turn to the context, evicting older turns if bounds are exceeded."""
        clean_user = user_transcript.strip()
        clean_answer = assistant_answer.strip()
        turn_chars = len(clean_user) + len(clean_answer)

        self._turn_counter += 1
        turn = ConversationTurn(
            turn_index=self._turn_counter,
            user_transcript=clean_user,
            assistant_answer=clean_answer,
            created_at=datetime.now(timezone.utc).isoformat(),
            char_count=turn_chars,
        )

        self._turns.append(turn)
        self._total_chars += turn_chars

        self._enforce_limits()
        return turn

    def _enforce_limits(self) -> None:
        # 1. Enforce turn count limit (FIFO)
        while len(self._turns) > self.max_turns:
            evicted = self._turns.popleft()
            self._total_chars -= evicted.char_count

        # 2. Enforce character budget limit (FIFO)
        while self._total_chars > self.max_total_chars and len(self._turns) > 1:
            evicted = self._turns.popleft()
            self._total_chars -= evicted.char_count

    def get_turns(self) -> list[ConversationTurn]:
        """Return the current list of retained turns in chronological order."""
        return list(self._turns)

    def clear(self) -> None:
        """Reset the conversation context completely."""
        self._turns.clear()
        self._total_chars = 0
