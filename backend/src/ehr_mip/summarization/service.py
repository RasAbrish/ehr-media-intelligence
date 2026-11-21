"""SummaryService: cache → provider → guardrails → cache (docs/02 section 6.3)."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import structlog

from ehr_mip.errors import PatientNotFoundError
from ehr_mip.fhir.store import BundleStore
from ehr_mip.observability.metrics import (
    GUARDRAIL_INTERVENTIONS,
    LLM_CALLS,
    LLM_LATENCY,
    LLM_TOKENS,
)
from ehr_mip.summarization.anomalies import detect_anomalies
from ehr_mip.summarization.cache import SummaryCache, cache_key
from ehr_mip.summarization.context import build_context
from ehr_mip.summarization.guardrails import (
    apply_guardrails,
    content_interventions,
    score_confidence,
    trim_to_word_limit,
)
from ehr_mip.summarization.prompts.registry import load_prompt
from ehr_mip.summarization.providers.base import (
    Provider,
    ProviderError,
    ProviderResult,
    SummaryRequest,
)
from ehr_mip.summarization.providers.extractive import ExtractiveProvider
from ehr_mip.summarization.records import read_bundle
from ehr_mip.summarization.schemas import (
    MAX_WORDS,
    ClinicalSummary,
    ClinicalSummaryLLM,
    SummaryTrace,
    count_words,
)
from ehr_mip.summarization.telemetry import (
    CallStatus,
    LlmCall,
    LlmCallRepository,
    TokenBudget,
)

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SummaryOutcome:
    summary: ClinicalSummary
    trace: SummaryTrace | None
    provider_calls: int


@dataclass(frozen=True)
class SummaryBatch:
    """Outcomes of a run plus the patients that failed; iterates over the outcomes."""

    outcomes: list[SummaryOutcome]
    failed: list[str] = field(default_factory=list)

    def __iter__(self) -> Iterator[SummaryOutcome]:
        return iter(self.outcomes)

    def __len__(self) -> int:
        return len(self.outcomes)


@dataclass
class _Generation:
    """Everything produced while generating one summary, before it is stored."""

    used: Provider
    fallback_reason: str | None
    output: ClinicalSummaryLLM | None = None
    notes: list[str] = field(default_factory=list)
    cited: int = 0
    grounded: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    attempts: int = 0
    calls: int = 0
    shortened: bool = False
    latency_ms: int = 0

    def add_usage(self, result: ProviderResult) -> None:
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self.attempts += result.attempts


def _now() -> datetime:
    return datetime.now(UTC)


class SummaryService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        provider: Provider,
        prompt_version: str,
        max_concurrency: int = 4,
        daily_token_budget: int = 0,
        today: date | None = None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._conn = conn
        self._provider = provider
        self._extractive = ExtractiveProvider()
        self._prompt = load_prompt(prompt_version)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._cache = SummaryCache(conn)
        self._calls = LlmCallRepository(conn)
        self._budget = TokenBudget(self._calls, daily_token_budget)
        self._today = today
        self._clock = clock

    def _model_for(self, provider: Provider) -> str | None:
        return provider.model if provider.kind == "anthropic" else None

    def _cached(
        self, patient_key: str, bundle_hash: str, provider: Provider
    ) -> SummaryOutcome | None:
        key = cache_key(patient_key, bundle_hash, self._prompt.version, self._model_for(provider))
        hit = self._cache.get(key)
        return (
            None if hit is None else SummaryOutcome(summary=hit[0], trace=hit[1], provider_calls=0)
        )

    async def summarize_patient(self, patient_key: str, *, force: bool = False) -> SummaryOutcome:
        loaded = BundleStore(self._conn).load_with_meta(patient_key)
        if loaded is None:
            msg = "No FHIR bundle for this patient. Run `make normalize` first."
            raise PatientNotFoundError(msg)
        bundle, bundle_hash, is_valid = loaded
        return await self.summarize_bundle(
            patient_key, bundle, bundle_hash, bundle_has_errors=not is_valid, force=force
        )

    async def summarize_all(self, *, force: bool = False) -> SummaryBatch:
        """Every patient; one patient's failure is logged and never aborts the run (NFR-07)."""
        keys = BundleStore(self._conn).patient_keys()
        results = await asyncio.gather(
            *(self.summarize_patient(k, force=force) for k in keys), return_exceptions=True
        )
        batch = SummaryBatch(outcomes=[])
        for key, result in zip(keys, results, strict=True):
            if isinstance(result, SummaryOutcome):
                batch.outcomes.append(result)
            elif isinstance(result, Exception):
                batch.failed.append(key)
                log.error("summary_failed", patient_key=key, error_type=type(result).__name__)
            else:  # KeyboardInterrupt, CancelledError and other BaseExceptions
                raise result
        return batch

    async def summarize_bundle(
        self,
        patient_key: str,
        bundle: dict[str, Any],
        bundle_hash: str,
        *,
        bundle_has_errors: bool = False,
        force: bool = False,
        persist: bool = True,
    ) -> SummaryOutcome:
        """Summarize one bundle. ``persist=False`` (eval fixtures) skips the cache and telemetry."""
        if persist and not force:
            hit = self._cached(patient_key, bundle_hash, self._provider)
            if hit is not None:
                return hit

        primary = self._provider
        fallback_reason: str | None = None
        if primary.kind == "anthropic" and self._budget.exceeded(self._clock()):
            primary, fallback_reason = self._extractive, "budget_exceeded"
            # A fallback summary for this exact bundle may already exist.
            hit = self._cached(patient_key, bundle_hash, primary) if persist and not force else None
            if hit is not None:
                return hit

        view = read_bundle(bundle)
        today = self._today or self._clock().date()
        anomalies = detect_anomalies(view, today=today)
        request = SummaryRequest(
            patient_key=patient_key,
            view=view,
            anomalies=anomalies,
            context=build_context(view, anomalies),
            prompt=self._prompt,
        )
        generation = await self._generate(request, primary, fallback_reason)
        return self._finalize(
            request,
            bundle_hash,
            generation,
            bundle_has_errors=bundle_has_errors,
            persist=persist,
        )

    async def _generate(
        self, request: SummaryRequest, primary: Provider, fallback_reason: str | None
    ) -> _Generation:
        """Provider call, extractive fallback, guardrails, one shorten retry, then trim."""
        async with self._semaphore:
            started = time.perf_counter()
            gen = _Generation(used=primary, fallback_reason=fallback_reason)
            try:
                gen.calls += primary.kind == "anthropic"
                result = await primary.summarize(request)
            except ProviderError as error:
                gen.fallback_reason, gen.used = error.reason, self._extractive
                result = await self._extractive.summarize(request)
                log.warning(
                    "summary_provider_fallback",
                    patient_key=request.patient_key,
                    reason=error.reason,
                )
            gen.add_usage(result)
            guard = apply_guardrails(result.output, request.view, request.anomalies)
            if guard.word_count > MAX_WORDS and gen.used.can_shorten:
                try:
                    gen.calls += 1
                    shorter = await gen.used.shorten(request, result.output, guard.word_count)
                    gen.add_usage(shorter)
                    # Only the kept answer's notes count; the first answer is discarded.
                    guard = apply_guardrails(shorter.output, request.view, request.anomalies)
                    guard.notes.append("shortened_by_retry")
                    gen.shortened = True
                except ProviderError:
                    log.warning("summary_shorten_failed", patient_key=request.patient_key)
            gen.output, gen.notes = guard.output, list(guard.notes)
            gen.cited, gen.grounded = guard.cited, guard.grounded
            if count_words(gen.output) > MAX_WORDS:
                gen.output = trim_to_word_limit(gen.output)
                gen.notes.append("trimmed")
            if gen.fallback_reason is not None:
                gen.notes.insert(0, f"fallback_extractive ({gen.fallback_reason})")
            gen.latency_ms = int((time.perf_counter() - started) * 1000)
        return gen

    def _finalize(
        self,
        request: SummaryRequest,
        bundle_hash: str,
        gen: _Generation,
        *,
        bundle_has_errors: bool,
        persist: bool,
    ) -> SummaryOutcome:
        """Confidence, the stored summary, its trace, the cache entry and telemetry."""
        assert gen.output is not None  # noqa: S101 (set by _generate)
        view = request.view
        extractive = gen.used.kind == "extractive"
        model = self._model_for(gen.used)
        summary = ClinicalSummary(
            **gen.output.model_dump(),
            patient_key=request.patient_key,
            word_count=count_words(gen.output),
            confidence=score_confidence(
                gen.output.self_reported_confidence,
                content_interventions(gen.notes),
                records=len(view.records),
                identity_conflict=view.patient.conflict,
                extractive=extractive,
                bundle_has_errors=bundle_has_errors,
            ),
            provider="extractive" if extractive else "anthropic",
            model=model,
            prompt_version=self._prompt.version,
            bundle_hash=bundle_hash,
            generated_at=self._clock(),
            cached=False,
            cache_key=cache_key(request.patient_key, bundle_hash, self._prompt.version, model),
            guardrail_notes=gen.notes,
        )
        trace = SummaryTrace(
            cited_ids=gen.cited,
            grounded_ids=gen.grounded,
            interventions=gen.notes,
            attempts=gen.attempts,
            shortened=gen.shortened,
            fallback_reason=gen.fallback_reason,
        )
        if not persist:
            return SummaryOutcome(summary=summary, trace=trace, provider_calls=gen.calls)
        self._cache.put(summary, trace)
        fell_back = gen.fallback_reason is not None and self._provider.kind == "anthropic"
        status: CallStatus = "fallback" if fell_back else "retried" if gen.attempts > 1 else "ok"
        self._calls.record(
            LlmCall(
                patient_key=request.patient_key,
                cache_key=summary.cache_key,
                provider=self._provider.name if fell_back else gen.used.name,
                model=self._provider.model if fell_back else model,
                prompt_version=self._prompt.version,
                input_tokens=gen.input_tokens,
                output_tokens=gen.output_tokens,
                latency_ms=gen.latency_ms,
                attempts=gen.attempts,
                status=status,
                guardrail_notes_count=len(gen.notes),
                word_count=summary.word_count,
            ),
            at=self._clock(),
        )
        _observe(self._provider.name if fell_back else gen.used.name, status, gen)
        return SummaryOutcome(summary=summary, trace=trace, provider_calls=gen.calls)


def _observe(provider: str, status: str, gen: _Generation) -> None:
    LLM_CALLS.labels(provider=provider, status=status).inc()
    LLM_TOKENS.labels(direction="input").inc(gen.input_tokens)
    LLM_TOKENS.labels(direction="output").inc(gen.output_tokens)
    LLM_LATENCY.labels(provider=provider).observe(gen.latency_ms / 1000)
    for note in gen.notes:
        GUARDRAIL_INTERVENTIONS.labels(type=note.split(" ", 1)[0]).inc()
