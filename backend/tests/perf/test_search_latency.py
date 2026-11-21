"""NFR-01: search latency with the real all-MiniLM-L6-v2 model on the synthetic set.

Hard limit: every one of 20 queries under 2 s. Target: p95 under 300 ms. The first
run downloads the model (about 90 MB) into HF_HOME (default data/generated/hf-cache).
"""

from __future__ import annotations

import os
import statistics
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.support.api import build_store, client_for

from ehr_mip.config import Settings
from ehr_mip.search.embedder import Embedder, SentenceTransformerEmbedder

pytestmark = pytest.mark.perf

# Read before the autouse fixture clears the environment, so CI's model cache is used.
HF_HOME = Path(os.environ.get("HF_HOME") or Settings(_env_file=None).hf_home)  # type: ignore[call-arg]
MODEL = "sentence-transformers/all-MiniLM-L6-v2"
QUERIES = [
    "worsening kidney function with high potassium",
    "shortness of breath and leg swelling",
    "pulmonary embolism on CT angiography",
    "elevated troponin chest pain",
    "low sodium",
    "pneumonia right lower lobe",
    "breast biopsy carcinoma",
    "urinary tract infection with sepsis",
    "high blood sugar and A1c",
    "thyroid hormone low",
    "stroke weakness on one side",
    "COPD exacerbation wheezing",
    "anemia low hemoglobin",
    "heart failure reduced ejection fraction",
    "lactate elevated",
    "diabetic eye exam",
    "discharge plan anticoagulation",
    "MRI brain findings",
    "fever and cough",
    "ICU admission",
]


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    return SentenceTransformerEmbedder(MODEL, HF_HOME)


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory, embedder: Embedder) -> Iterator[TestClient]:
    store = build_store(tmp_path_factory.mktemp("perf") / "store", embedder)
    with client_for(store, embedder_factory=lambda _: embedder) as test_client:
        yield test_client


@pytest.mark.parametrize("mode", ["semantic", "hybrid"])
def test_search_latency_under_2s(client: TestClient, mode: str) -> None:
    timings = []
    for query in QUERIES:
        started = time.perf_counter()
        response = client.post("/search", params={"mode": mode}, json={"query": query})
        timings.append((time.perf_counter() - started) * 1000)
        assert response.status_code == 200
        assert response.headers["x-cache"] == "MISS"
        assert response.json()["results"]
    p50 = statistics.median(timings)
    p95 = statistics.quantiles(timings, n=20)[-1]
    print(
        f"\nsearch latency ({mode}, n={len(timings)}): p50 {p50:.1f} ms, "
        f"p95 {p95:.1f} ms, max {max(timings):.1f} ms"
    )
    assert max(timings) < 2000
