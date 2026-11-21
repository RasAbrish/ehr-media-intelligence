"""Helpers for summarization tests: requests and scripted model outputs."""

from __future__ import annotations

from datetime import date
from typing import Any

from tests.support.bundles import heart_failure_bundle

from ehr_mip.summarization.anomalies import detect_anomalies
from ehr_mip.summarization.context import build_context
from ehr_mip.summarization.prompts.registry import load_prompt
from ehr_mip.summarization.providers.base import SummaryRequest
from ehr_mip.summarization.records import read_bundle
from ehr_mip.summarization.schemas import ClinicalSummaryLLM

TODAY = date(2026, 11, 21)


def make_request(**bundle_kwargs: Any) -> SummaryRequest:
    built = heart_failure_bundle(**bundle_kwargs)
    view = read_bundle(built.bundle)
    anomalies = detect_anomalies(view, today=TODAY)
    return SummaryRequest(
        patient_key=built.patient_key,
        view=view,
        anomalies=anomalies,
        context=build_context(view, anomalies),
        prompt=load_prompt("v1"),
    )


def ref(request: SummaryRequest, kind: str) -> dict[str, str]:
    """The first citable record of a kind (note, imaging, lab) as an evidence dict."""
    record = next(r for r in request.view.records if r.kind == kind)
    return {"resource_type": record.ref.resource_type, "resource_id": record.ref.resource_id}


def good_output(request: SummaryRequest, **overrides: Any) -> ClinicalSummaryLLM:
    """A well-formed, grounded answer such as a careful model would give."""

    def default(name: str) -> object:
        note, echo, lab = ref(request, "note"), ref(request, "imaging"), ref(request, "lab")
        high = request.anomalies[0]
        return {
            "key_diagnoses": [
                {"name": "Acute on chronic systolic heart failure", "status": "active",
                 "evidence": [note]}
            ],
            "recent_media": [
                {"resource": echo, "kind": "imaging", "date": None, "finding": "Echo: EF 30%"},
                {"resource": lab, "kind": "lab", "date": None, "finding": "K 6.3 HH, Na 131 L"},
            ],
            "flagged_anomalies": [{"description": high.description, "severity": "high",
                                   "source": "rule",
                                   "evidence": [e.model_dump() for e in high.evidence]}],
        }[name]  # fmt: skip

    data: dict[str, Any] = {
        "chief_concern": "Admitted with dyspnea from acute on chronic systolic heart failure.",
        "overview": "56-year-old female with systolic heart failure, EF 30%, diuresed.",
        "self_reported_confidence": "high",
    }
    for name in ("key_diagnoses", "recent_media", "flagged_anomalies"):
        if name not in overrides:
            data[name] = default(name)
    data.update(overrides)
    return ClinicalSummaryLLM.model_validate(data)
