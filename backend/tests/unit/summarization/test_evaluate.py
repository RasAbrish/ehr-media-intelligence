"""Evaluator helpers: fixture loading, fact checks and the report."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.support.summaries import make_request

from ehr_mip.config import PROJECT_ROOT
from ehr_mip.fhir.validator import validate_bundle
from ehr_mip.summarization.evaluate import (
    _case_result,
    compute_gates,
    diagnosis_matches,
    load_cases,
    render_markdown,
    write_manual_review_template,
)
from ehr_mip.summarization.providers.extractive import ExtractiveProvider
from ehr_mip.summarization.schemas import (
    DISCLAIMER,
    ClinicalSummary,
    ClinicalSummaryLLM,
    Confidence,
    count_words,
)
from ehr_mip.summarization.service import SummaryOutcome

FIXTURES = PROJECT_ROOT / "backend" / "tests" / "fixtures"
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("folder", ["golden", "adversarial"])
def test_fixture_cases_build_valid_bundles(folder: str) -> None:
    cases = load_cases(FIXTURES / folder, timestamp=NOW)
    assert len(cases) == 5
    for case in cases:
        result = validate_bundle(case.bundle, patient_key=case.patient_key, today=NOW.date())
        assert result.is_valid, (case.case_id, result.issues)


@pytest.mark.parametrize(
    ("expected", "names", "matched"),
    [
        ("chronic kidney disease", ["Chronic kidney disease stage 3b"], True),
        ("urinary tract infection", ["Urosepsis"], True),
        ("congestive heart failure", ["Systolic heart failure"], True),
        ("hyponatremia", ["Systolic heart failure"], False),
        ("breast mass", ["Mass in the left breast"], True),
    ],
)
def test_diagnosis_matches(expected: str, names: list[str], matched: bool) -> None:
    assert diagnosis_matches(expected, names) is matched


def _summary(**overrides: object) -> ClinicalSummary:
    request = make_request()
    output = ExtractiveProvider().build(request)
    data = {
        **output.model_dump(),
        "patient_key": request.patient_key,
        "word_count": 0,
        "confidence": Confidence(level="low", score=0.4, rationale="Offline."),
        "disclaimer": DISCLAIMER,
        "provider": "extractive",
        "model": None,
        "prompt_version": "v1",
        "bundle_hash": "h",
        "generated_at": NOW,
        "cache_key": "k",
    }
    data.update(overrides)
    data["word_count"] = count_words(ClinicalSummaryLLM.model_validate(
        {k: data[k] for k in ClinicalSummaryLLM.model_fields}
    ))  # fmt: skip
    return ClinicalSummary.model_validate(data)


def test_case_result_flags_forbidden_and_missing_facts() -> None:
    case = load_cases(FIXTURES / "golden", timestamp=NOW)[1]  # golden-ckd
    summary = _summary(overview="The patient is healthy.")
    result = _case_result(case, SummaryOutcome(summary=summary, trace=None, provider_calls=0))
    assert not result["passed"]
    assert "healthy" in result["forbidden"]
    assert any(m.startswith("diagnosis") for m in result["missing"])


def test_manual_review_sheet_never_overwrites(tmp_path: Path) -> None:
    sheet = tmp_path / "review.md"
    summaries = [_summary(patient_key=f"key-{i:02d}") for i in range(12)]
    assert write_manual_review_template(None, sheet, summaries)  # type: ignore[arg-type]
    content = sheet.read_text(encoding="utf-8")
    assert content.count("| `key-") == 10
    sheet.write_text("scored by a person", encoding="utf-8")
    assert not write_manual_review_template(None, sheet, summaries)  # type: ignore[arg-type]
    assert sheet.read_text(encoding="utf-8") == "scored by a person"


def test_report_markdown_lists_gates_and_misses() -> None:
    report = {
        "generated_at": "2026-11-21T12:00:00+00:00",
        "providers": ["extractive"],
        "models": ["extractive"],
        "prompt_version": "v1",
        "full_set": {"patients": 2, "schema_validity": 1.0, "length_compliance": 1.0,
                     "disclaimer_present": 1.0, "grounding_pre_guardrail": 1.0,
                     "grounding_final": 1.0, "diagnosis_support": 0.5,
                     "high_anomaly_recall": 1.0, "guardrail_intervention_rate": 0.0,
                     "failures": ["abc: unsupported diagnosis 'x'"]},
        "ground_truth": {"recall": 0.5, "found": 1, "total": 2, "misses": ["S-001: x"]},
        "golden": [], "adversarial": [],
        "llm": {"model_calls": 0, "input_tokens": 0, "output_tokens": 0,
                "cost_usd_estimate": 0.0, "p95_latency_ms": None, "fallbacks": 0},
        "gates": {"diagnosis_support": False}, "passed": False,
    }  # fmt: skip
    markdown = render_markdown(report)
    assert "| diagnosis support | FAIL |" in markdown
    assert "Overall: **FAIL**" in markdown
    assert "- S-001: x" in markdown
    assert "| Diagnosis support | 50.0% | ≥ 95% |" in markdown


def test_grounding_gate_fails_when_nothing_is_cited() -> None:
    rates = {
        "schema_validity": 1.0,
        "length_compliance": 1.0,
        "disclaimer_present": 1.0,
        "grounding_final": None,
        "diagnosis_support": 1.0,
        "high_anomaly_recall": 1.0,
    }
    cases = {"golden": [{"passed": True}], "adversarial": [{"passed": True}]}
    gates = compute_gates(rates, rates, cases, None, failed_patients=0)
    assert not gates["grounding_final"]
    cited = {**rates, "grounding_final": 1.0}
    assert all(compute_gates(cited, cited, cases, None, failed_patients=0).values())
    assert not compute_gates(cited, cited, cases, None, failed_patients=1)[
        "schema_disclaimer_length"
    ]  # a patient that failed to summarize fails the schema gate
