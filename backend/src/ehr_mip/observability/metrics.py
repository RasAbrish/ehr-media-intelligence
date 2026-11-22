"""Prometheus series from docs/04 section 9a.2.

HTTP request counters and durations come from prometheus-fastapi-instrumentator;
the series below are defined once per process in the default registry.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

_LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0)

SEARCH_LATENCY = Histogram(
    "search_latency_seconds", "Search latency.", ["mode", "cache"], buckets=_LATENCY_BUCKETS
)
CACHE_REQUESTS = Counter("cache_requests_total", "Cache lookups.", ["cache", "result"])
CACHE_ERRORS = Counter("cache_errors_total", "Redis failures, served without it.", ["store"])
LLM_CALLS = Counter("llm_calls_total", "Summary provider calls.", ["provider", "status"])
LLM_TOKENS = Counter("llm_tokens_total", "LLM tokens.", ["direction"])
LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "Summary generation latency.",
    ["provider"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 20, 45),
)
GUARDRAIL_INTERVENTIONS = Counter(
    "summary_guardrail_interventions_total", "Guardrail notes on summaries.", ["type"]
)
RATE_LIMITED = Counter("rate_limited_total", "Requests refused by the rate limiter.", ["route"])
