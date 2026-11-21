"""Provider interface shared by the Fake, Extractive and Anthropic providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ehr_mip.summarization.context import Context
from ehr_mip.summarization.prompts.registry import Prompt
from ehr_mip.summarization.records import BundleView
from ehr_mip.summarization.schemas import Anomaly, ClinicalSummaryLLM, SummaryProvider


@dataclass(frozen=True)
class SummaryRequest:
    patient_key: str
    view: BundleView
    anomalies: list[Anomaly]
    context: Context
    prompt: Prompt


@dataclass(frozen=True)
class ProviderResult:
    output: ClinicalSummaryLLM
    input_tokens: int = 0
    output_tokens: int = 0
    attempts: int = 1


class ProviderError(Exception):
    """The provider could not produce a summary; the service falls back to extractive."""

    reason = "provider_error"


class ProviderRefusalError(ProviderError):
    """The model declined the request (``stop_reason == "refusal"``)."""

    reason = "refusal"


class Provider(Protocol):
    """Read-only attributes (properties) so implementations may narrow their types."""

    @property
    def name(self) -> str: ...  # telemetry label: "anthropic", "extractive" or "fake"

    @property
    def kind(self) -> SummaryProvider: ...  # what the summary reports to clients

    @property
    def model(self) -> str | None: ...

    @property
    def can_shorten(self) -> bool: ...

    async def summarize(self, request: SummaryRequest) -> ProviderResult: ...

    async def shorten(
        self, request: SummaryRequest, previous: ClinicalSummaryLLM, words: int
    ) -> ProviderResult: ...
