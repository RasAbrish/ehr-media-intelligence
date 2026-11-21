"""FakeProvider: deterministic stand-in for the LLM in tests (never calls the network)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ehr_mip.summarization.providers.base import (
    ProviderError,
    ProviderResult,
    SummaryRequest,
)
from ehr_mip.summarization.schemas import ClinicalSummaryLLM, SummaryProvider

Script = Callable[[SummaryRequest], ClinicalSummaryLLM]


@dataclass
class FakeProvider:
    """Returns scripted outputs and records every call.

    ``script`` builds the first answer; ``shorter`` (optional) builds the answer to a
    shorten request. ``fail_with`` makes every call raise, to test the fallback path.
    """

    script: Script
    shorter: Script | None = None
    fail_with: ProviderError | None = None
    model: str | None = "fake-model"
    name: str = "fake"
    kind: SummaryProvider = "anthropic"
    can_shorten: bool = True
    calls: list[str] = field(default_factory=list)

    async def summarize(self, request: SummaryRequest) -> ProviderResult:
        self.calls.append(f"summarize:{request.patient_key}")
        if self.fail_with is not None:
            raise self.fail_with
        return ProviderResult(self.script(request), input_tokens=len(request.context.text) // 4,
                              output_tokens=150)  # fmt: skip

    async def shorten(
        self, request: SummaryRequest, previous: ClinicalSummaryLLM, words: int
    ) -> ProviderResult:
        self.calls.append(f"shorten:{request.patient_key}:{words}")
        if self.fail_with is not None:
            raise self.fail_with
        if self.shorter is None:
            return ProviderResult(previous, output_tokens=150)
        return ProviderResult(self.shorter(request), output_tokens=100)
