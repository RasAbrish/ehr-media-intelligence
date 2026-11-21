"""LLM call telemetry (FR-7.4, docs/10 section 7) and the daily token budget (FR-7.6).

Rows hold ids and numbers only: never prompt text, record text or model output.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

CallStatus = Literal["ok", "retried", "fallback", "failed"]

# USD per million tokens (input, output). Used for cost estimates only.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def estimate_cost(model: str | None, input_tokens: int, output_tokens: int) -> float | None:
    prices = PRICES_PER_MTOK.get(model or "")
    if prices is None:
        return None
    return round((input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000, 6)


@dataclass(frozen=True)
class LlmCall:
    patient_key: str
    cache_key: str
    provider: str
    model: str | None
    prompt_version: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    attempts: int
    status: CallStatus
    guardrail_notes_count: int
    word_count: int


class LlmCallRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def record(self, call: LlmCall, *, at: datetime | None = None) -> None:
        when = (at or datetime.now(UTC)).isoformat(timespec="seconds")
        with self._conn:
            self._conn.execute(
                """INSERT INTO llm_calls (patient_key, cache_key, provider, model, prompt_version,
                       input_tokens, output_tokens, cost_usd_estimate, latency_ms, attempts,
                       status, guardrail_notes_count, word_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    call.patient_key,
                    call.cache_key,
                    call.provider,
                    call.model,
                    call.prompt_version,
                    call.input_tokens,
                    call.output_tokens,
                    estimate_cost(call.model, call.input_tokens, call.output_tokens),
                    call.latency_ms,
                    call.attempts,
                    call.status,
                    call.guardrail_notes_count,
                    call.word_count,
                    when,
                ),
            )

    def tokens_on(self, day: str) -> int:
        """Total tokens spent on model calls on a UTC day (``YYYY-MM-DD``)."""
        row = self._conn.execute(
            "SELECT COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0) "
            "FROM llm_calls WHERE substr(created_at, 1, 10) = ?",
            (day,),
        ).fetchone()
        return int(row[0])


@dataclass
class TokenBudget:
    """Daily token cap for model calls. A limit of 0 or less disables the guard."""

    calls: LlmCallRepository
    daily_limit: int

    def exceeded(self, now: datetime | None = None) -> bool:
        if self.daily_limit <= 0:
            return False
        day = (now or datetime.now(UTC)).astimezone(UTC).date().isoformat()
        return self.calls.tokens_on(day) >= self.daily_limit
