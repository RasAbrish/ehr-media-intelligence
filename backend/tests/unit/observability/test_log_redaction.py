"""PHI redaction processor (FR-6.4, docs/09 section 6)."""

from __future__ import annotations

from ehr_mip.observability.log_redaction import REDACTED, redact_phi


def test_drops_phi_keys_and_masks_mrns() -> None:
    event = {
        "event": "patient 00012345 viewed",
        "patient_key": "patient-key-1",
        "name": "Jane Doe",
        "mrn": "00012345",
        "birth_date": "1968-03-14",
        "text": "Ms. Doe has CHF",
        "query": "Jane Doe chest pain",
        "nested": {"phone": "212-555-0142", "note": "MRN 00098765", "count": 3},
        "items": ["00012345", 7],
    }
    out = redact_phi(None, "info", dict(event))
    for key in ("name", "mrn", "birth_date", "text", "query"):
        assert out[key] == REDACTED
    assert out["event"] == "patient [mrn] viewed"
    assert out["patient_key"] == event["patient_key"]  # ids are kept
    assert out["nested"] == {"phone": REDACTED, "note": REDACTED, "count": 3}
    assert out["items"] == ["[mrn]", 7]
