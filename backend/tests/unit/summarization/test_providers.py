"""Extractive and Anthropic providers. The Anthropic tests use a mock HTTP transport."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient
from tests.support.clean_models import make_document, make_encounter
from tests.support.summaries import good_output, make_request

from ehr_mip.summarization.dictionary import find_concepts
from ehr_mip.summarization.providers.anthropic import AnthropicProvider
from ehr_mip.summarization.providers.base import ProviderError, ProviderRefusalError
from ehr_mip.summarization.providers.extractive import ExtractiveProvider, _section
from ehr_mip.summarization.schemas import NOT_DOCUMENTED

# ---------------------------------------------------------------- extractive


async def test_extractive_output_valid() -> None:
    request = make_request()
    result = await ExtractiveProvider().summarize(request)
    out = result.output
    assert out.chief_concern == "Acute on chronic systolic heart failure."
    assert [d.name for d in out.key_diagnoses][:1] == ["Systolic heart failure"]
    assert all(d.evidence for d in out.key_diagnoses)
    assert [m.kind for m in out.recent_media] == ["imaging", "lab"]
    assert out.flagged_anomalies[0].severity == "high"
    assert out.overview.startswith("56-year-old female with systolic heart failure")
    assert "latest encounter 2025-02-01 (inpatient)" in out.overview
    assert out.self_reported_confidence == "low"
    assert result.input_tokens == result.output_tokens == 0


async def test_overview_never_states_a_suspected_diagnosis_as_fact() -> None:
    note = make_document(
        text="ASSESSMENT: Acute ischemic stroke.\n"
        "PLAN: Telemetry to evaluate for atrial fibrillation."
    )
    out = (await ExtractiveProvider().summarize(make_request(documents=[note]))).output
    assert ("Atrial fibrillation", "suspected") in {(d.name, d.status) for d in out.key_diagnoses}
    assert "suspected atrial fibrillation" in out.overview
    assert "suspected acute ischemic stroke" not in out.overview


async def test_extractive_without_documents() -> None:
    result = await ExtractiveProvider().summarize(make_request(documents=[]))
    assert result.output.chief_concern == NOT_DOCUMENTED
    assert result.output.key_diagnoses == []
    assert "no documented diagnoses" in result.output.overview


async def test_extractive_never_copies_patient_identifiers() -> None:
    result = await ExtractiveProvider().summarize(make_request())
    text = result.output.model_dump_json()
    for identifier in ("Doe", "Jane", "00012345", "03/14/1968"):
        assert identifier not in text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("No evidence of pneumonia.", {}),
        ("Negative for pulmonary embolism; no pleural effusion.", {}),
        ("Pneumonia was ruled out.", {}),
        ("Suspected pulmonary embolism.", {"Pulmonary embolism": "uncertain"}),
        ("Admitted to rule out sepsis.", {"Sepsis": "uncertain"}),
        ("No significant change in heart failure.", {"Congestive heart failure": "affirmed"}),
        (
            "No fever but right lower lobe pneumonia on CXR.",
            {"Community-acquired pneumonia": "affirmed"},
        ),
        (
            "Possible pneumonia. Pneumonia confirmed on CT.",
            {"Community-acquired pneumonia": "affirmed"},
        ),
    ],
)
def test_concepts_respect_negation_and_uncertainty(text: str, expected: dict[str, str]) -> None:
    assert {k: m.certainty for k, m in find_concepts(text).items()} == expected


async def test_extractive_skips_negated_and_marks_uncertain_diagnoses() -> None:
    text = "ASSESSMENT: No evidence of pneumonia. Suspected pulmonary embolism.\nPLAN: CT."
    request = make_request(documents=[make_document(text, encounter=make_encounter())])
    diagnoses = {d.name: d.status for d in (await ExtractiveProvider().summarize(request))
                 .output.key_diagnoses}  # fmt: skip
    assert "Community-acquired pneumonia" not in diagnoses
    assert "Pneumonia" not in diagnoses
    assert diagnoses["Pulmonary embolism"] == "suspected"


def test_section_ends_only_at_upper_case_headers() -> None:
    text = "IMPRESSION: Spiculated mass.\nnote: correlate clinically.\nPLAN: Biopsy."
    assert _section(text, "IMPRESSION") == "Spiculated mass. note: correlate clinically."
    assert _section("impression: Clear lungs.\nPLAN: none.", "IMPRESSION") == "Clear lungs."


# ---------------------------------------------------------------- anthropic (mocked HTTP)


def _message(body: dict[str, Any], stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "content": [{"type": "text", "text": json.dumps(body)}] if body else [],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1200, "output_tokens": 300,
                  "cache_creation_input_tokens": 0, "cache_read_input_tokens": 100},
    }  # fmt: skip


def provider_with(handler: Callable[[httpx2.Request], httpx2.Response]) -> AnthropicProvider:
    client = AsyncAnthropic(
        api_key="test-key-not-real",
        max_retries=0,
        http_client=DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return AnthropicProvider(client=client, model="claude-haiku-5-5", backoff_seconds=0)


async def test_anthropic_parses_structured_output_and_sends_safe_request() -> None:
    request = make_request()
    expected = good_output(request)
    seen: list[dict[str, Any]] = []

    def handler(http_request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(http_request.content))
        return httpx2.Response(200, json=_message(expected.model_dump(mode="json")))

    result = await provider_with(handler).summarize(request)
    assert result.output == expected
    assert (result.input_tokens, result.output_tokens, result.attempts) == (1300, 300, 1)
    body = seen[0]
    assert body["model"] == "claude-haiku-5-5"
    assert body["max_tokens"] == 4000
    assert "temperature" not in body
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    # The request that leaves the host carries no patient identifiers.
    sent = json.dumps(body)
    for identifier in ("Doe", "Jane", "00012345", "1968-03-14", "03/14/1968"):
        assert identifier not in sent


async def test_anthropic_retries_429_then_succeeds() -> None:
    request = make_request()
    responses = [
        httpx2.Response(
            429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}
        ),
        httpx2.Response(
            529, json={"type": "error", "error": {"type": "overloaded_error", "message": "busy"}}
        ),
        httpx2.Response(200, json=_message(good_output(request).model_dump(mode="json"))),
    ]
    result = await provider_with(lambda _: responses.pop(0)).summarize(request)
    assert result.attempts == 3


async def test_anthropic_gives_up_after_four_attempts() -> None:
    calls: list[int] = []

    def handler(_: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(
            500, json={"type": "error", "error": {"type": "api_error", "message": "x"}}
        )

    with pytest.raises(ProviderError, match="after 4 attempts"):
        await provider_with(handler).summarize(make_request())
    assert len(calls) == 4


async def test_anthropic_refusal_raises_refusal() -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        body = _message({}, stop_reason="refusal")
        body["stop_details"] = {"type": "refusal", "category": None, "explanation": "declined"}
        return httpx2.Response(200, json=body)

    with pytest.raises(ProviderRefusalError):
        await provider_with(handler).summarize(make_request())


async def test_anthropic_bad_request_is_not_retried() -> None:
    calls: list[int] = []

    def handler(_: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(
            400,
            json={"type": "error", "error": {"type": "invalid_request_error", "message": "bad"}},
        )

    with pytest.raises(ProviderError, match="BadRequestError"):
        await provider_with(handler).summarize(make_request())
    assert len(calls) == 1


async def test_anthropic_schema_mismatch_is_a_provider_error() -> None:
    request = make_request()
    body = good_output(request).model_dump(mode="json")
    body["key_diagnoses"][0]["status"] = "probably"

    def handler(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=_message(body))

    with pytest.raises(ProviderError, match="schema"):
        await provider_with(handler).summarize(request)


async def test_anthropic_truncated_output_is_an_error() -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=_message({}, stop_reason="max_tokens"))

    with pytest.raises(ProviderError, match="no complete structured output"):
        await provider_with(handler).summarize(make_request())


async def test_anthropic_shorten_sends_previous_answer_and_instruction() -> None:
    request = make_request()
    previous = good_output(request)
    seen: list[dict[str, Any]] = []

    def handler(http_request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(http_request.content))
        return httpx2.Response(200, json=_message(previous.model_dump(mode="json")))

    await provider_with(handler).shorten(request, previous, 240)
    roles = [m["role"] for m in seen[0]["messages"]]
    assert roles == ["user", "assistant", "user"]
    assert "had 240 words" in seen[0]["messages"][2]["content"]
