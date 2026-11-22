"""Groq provider: an OpenAI-compatible chat API with JSON schema output (ADR-014).

Standard library HTTP in a worker thread, so no new dependency. 429 and 5xx are retried,
honouring ``Retry-After`` (the free tier counts tokens per minute). Every other failure
raises ``ProviderError`` and the service falls back to the extractive provider.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ehr_mip.summarization.providers.anthropic import SHORTEN_TARGET_WORDS
from ehr_mip.summarization.providers.base import ProviderError, ProviderResult, SummaryRequest
from ehr_mip.summarization.schemas import ClinicalSummaryLLM, SummaryProvider

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_WAIT_S = 90.0


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Replace ``$ref`` with the referenced definition (no ``$defs`` in the request)."""
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].rsplit("/", 1)[-1]])
            return {k: walk(v) for k, v in node.items() if k not in ("$defs", "title")}
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    result: dict[str, Any] = walk(schema)
    return result


SUMMARY_SCHEMA = _inline_refs(ClinicalSummaryLLM.model_json_schema())


class _Retryable(Exception):  # noqa: N818 (internal signal, never escapes)
    def __init__(self, wait: float) -> None:
        super().__init__("retry")
        self.wait = wait


@dataclass
class GroqProvider:
    api_key: str
    model: str
    base_url: str = GROQ_BASE_URL
    max_tokens: int = 4000
    attempts: int = 6
    backoff_seconds: float = 2.0
    timeout_s: float = 60.0
    name: str = "groq"
    kind: SummaryProvider = "groq"
    can_shorten: bool = True

    async def summarize(self, request: SummaryRequest) -> ProviderResult:
        user = {"role": "user", "content": request.prompt.render_user(request.context.text)}
        return await self._call(request.prompt.system, [user])

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

    def _post(self, body: bytes) -> dict[str, Any]:
        http = urllib.request.Request(  # noqa: S310 (fixed https base URL from settings)
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "ehr-mip",
            },
        )
        try:
            with urllib.request.urlopen(http, timeout=self.timeout_s) as response:  # noqa: S310
                payload: dict[str, Any] = json.loads(response.read())
                return payload
        except urllib.error.HTTPError as error:
            if error.code in _RETRY_STATUS:
                header = error.headers.get("retry-after")
                try:
                    wait = float(header) if header else 0.0
                except ValueError:
                    wait = 0.0
                raise _Retryable(wait) from None
            msg = f"Groq request failed with status {error.code}"
            raise ProviderError(msg) from None
        except (urllib.error.URLError, TimeoutError):
            raise _Retryable(0.0) from None

    async def _call(self, system: str, messages: list[dict[str, str]]) -> ProviderResult:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, *messages],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "clinical_summary", "schema": SUMMARY_SCHEMA},
                },
                "reasoning_effort": "low",
                "max_completion_tokens": self.max_tokens,
            }
        ).encode()
        payload: dict[str, Any] | None = None
        attempt = 0
        for attempt in range(1, self.attempts + 1):
            try:
                payload = await asyncio.to_thread(self._post, body)
                break
            except _Retryable as retry:
                if attempt == self.attempts:
                    msg = f"Groq unavailable after {attempt} attempts"
                    raise ProviderError(msg) from None
                wait = retry.wait or self.backoff_seconds * 2 ** (attempt - 1)
                await asyncio.sleep(min(wait, _MAX_WAIT_S))
        assert payload is not None  # noqa: S101 (the loop breaks or raises)
        try:
            choice = payload["choices"][0]
            if choice.get("finish_reason") == "length":
                msg = "Groq returned no complete structured output"
                raise ProviderError(msg)
            output = ClinicalSummaryLLM.model_validate_json(choice["message"]["content"])
            usage = payload.get("usage") or {}
        except (KeyError, IndexError, TypeError, ValidationError) as error:
            msg = "Groq output did not match the summary schema"
            raise ProviderError(msg) from error
        return ProviderResult(
            output=output,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            attempts=attempt,
        )
