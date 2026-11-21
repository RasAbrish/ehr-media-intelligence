"""Claude provider: structured output through ``messages.parse`` (docs/05 section 3.3).

Retries 429, 5xx, timeouts and connection errors up to ``attempts`` times with
exponential backoff (the SDK's own retries are disabled so attempts are counted
here). Refusals, truncated answers and other API errors raise ``ProviderError`` and
the service falls back to the extractive provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import OutputConfigParam
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ehr_mip.summarization.providers.base import (
    ProviderError,
    ProviderRefusalError,
    ProviderResult,
    SummaryRequest,
)
from ehr_mip.summarization.schemas import ClinicalSummaryLLM, SummaryProvider

RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
)
SHORTEN_TARGET_WORDS = 170


@dataclass
class AnthropicProvider:
    client: AsyncAnthropic
    model: str
    max_tokens: int = 4000
    effort: str = "low"
    attempts: int = 4
    backoff_seconds: float = 1.0
    name: str = "anthropic"
    kind: SummaryProvider = "anthropic"
    can_shorten: bool = True

    async def summarize(self, request: SummaryRequest) -> ProviderResult:
        messages = [{"role": "user", "content": request.prompt.render_user(request.context.text)}]
        return await self._call(request.prompt.system, messages)

    async def shorten(
        self, request: SummaryRequest, previous: ClinicalSummaryLLM, words: int
    ) -> ProviderResult:
        messages = [
            {"role": "user", "content": request.prompt.render_user(request.context.text)},
            {"role": "assistant", "content": previous.model_dump_json()},
            {
                "role": "user",
                "content": (
                    f"Your previous answer had {words} words. Shorten it to under "
                    f"{SHORTEN_TARGET_WORDS} words. Keep every citation and every high "
                    "severity anomaly."
                ),
            },
        ]
        return await self._call(request.prompt.system, messages)

    async def _call(self, system: str, messages: list[dict[str, Any]]) -> ProviderResult:
        attempts = 0
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.attempts),
                wait=wait_exponential(multiplier=self.backoff_seconds, max=16),
                retry=retry_if_exception_type(RETRYABLE),
                reraise=True,
            ):
                with attempt:
                    attempts = attempt.retry_state.attempt_number
                    response = await self.client.messages.parse(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        # The static system prompt is marked cacheable; it only caches once
                        # the prefix passes the model's minimum cacheable length.
                        system=[
                            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
                        ],
                        messages=messages,  # type: ignore[arg-type]
                        output_format=ClinicalSummaryLLM,
                        output_config=cast("OutputConfigParam", {"effort": self.effort}),
                    )
        except RETRYABLE as error:
            raise ProviderError(f"Claude unavailable after {attempts} attempts") from error
        except anthropic.APIError as error:
            raise ProviderError(f"Claude request failed: {type(error).__name__}") from error
        except ValueError as error:  # pydantic ValidationError or bad JSON from the parser
            raise ProviderError("Claude output did not match the summary schema") from error

        if response.stop_reason == "refusal":
            raise ProviderRefusalError("Claude declined to summarize this record")
        try:
            parsed = response.parsed_output
        except ValueError as error:
            raise ProviderError("Claude output did not match the summary schema") from error
        if response.stop_reason == "max_tokens" or parsed is None:
            raise ProviderError("Claude returned no complete structured output")
        usage = response.usage
        input_tokens = (
            usage.input_tokens
            + (usage.cache_creation_input_tokens or 0)
            + (usage.cache_read_input_tokens or 0)
        )
        return ProviderResult(
            output=parsed,
            input_tokens=input_tokens,
            output_tokens=usage.output_tokens,
            attempts=attempts,
        )
