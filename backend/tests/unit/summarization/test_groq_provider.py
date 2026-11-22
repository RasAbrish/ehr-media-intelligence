"""GroqProvider against a local fake of the OpenAI-compatible endpoint (ADR-014). No network."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from tests.support.summaries import good_output, make_request

from ehr_mip.summarization.providers.base import ProviderError
from ehr_mip.summarization.providers.groq import GroqProvider
from ehr_mip.summarization.schemas import ClinicalSummaryLLM

KEY = "gsk-test-not-real"


class FakeGroq:
    def __init__(self) -> None:
        self.replies: list[tuple[int, dict[str, str], Any]] = []
        self.requests: list[tuple[dict[str, str], dict[str, Any]]] = []


@pytest.fixture
def groq() -> Iterator[tuple[FakeGroq, str]]:
    state = FakeGroq()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            return

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            state.requests.append((dict(self.headers), body))
            status, headers, reply = state.replies.pop(0)
            data = json.dumps(reply).encode()
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield state, f"http://127.0.0.1:{server.server_address[1]}/openai/v1"
    server.shutdown()


@pytest.fixture
def summary_request() -> Any:
    return make_request()


def completion(content: str, finish: str = "stop") -> dict[str, Any]:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": finish}
        ],
        "usage": {"prompt_tokens": 1800, "completion_tokens": 420},
    }


def provider(base_url: str) -> GroqProvider:
    return GroqProvider(
        api_key=KEY, model="openai/gpt-oss-120b", base_url=base_url, backoff_seconds=0
    )


def test_structured_request_and_parsed_summary(
    groq: tuple[FakeGroq, str], summary_request: Any
) -> None:
    state, base = groq
    expected = good_output(summary_request)
    state.replies.append((200, {}, completion(expected.model_dump_json())))
    result = asyncio.run(provider(base).summarize(summary_request))
    assert result.output == expected
    assert (result.input_tokens, result.output_tokens, result.attempts) == (1800, 420, 1)
    headers, body = state.requests[0]
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["reasoning_effort"] == "low"
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    schema = body["response_format"]["json_schema"]["schema"]
    assert "$defs" not in json.dumps(schema)  # references inlined
    assert set(schema["required"]) == set(ClinicalSummaryLLM.model_fields)


def test_rate_limit_waits_and_retries(groq: tuple[FakeGroq, str], summary_request: Any) -> None:
    state, base = groq
    state.replies += [
        (429, {"retry-after": "0"}, {"error": {"message": "slow down"}}),
        (200, {}, completion(good_output(summary_request).model_dump_json())),
    ]
    assert asyncio.run(provider(base).summarize(summary_request)).attempts == 2


@pytest.mark.parametrize(
    "reply",
    [
        (400, {}, {"error": {"message": "bad request"}}),
        (200, {}, completion('{"chief_concern": 1}')),
        (200, {}, completion("not json")),
        (200, {}, completion("{}", finish="length")),
    ],
)
def test_failures_raise_provider_errors(
    groq: tuple[FakeGroq, str], summary_request: Any, reply: tuple[int, dict[str, str], Any]
) -> None:
    state, base = groq
    state.replies.append(reply)
    with pytest.raises(ProviderError):
        asyncio.run(provider(base).summarize(summary_request))


def test_the_key_never_appears_in_errors(groq: tuple[FakeGroq, str], summary_request: Any) -> None:
    state, base = groq
    state.replies.append((401, {}, {"error": {"message": "invalid api key"}}))
    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider(base).summarize(summary_request))
    assert KEY not in str(caught.value)
