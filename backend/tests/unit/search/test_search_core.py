"""Search building blocks: where clause, chunker, scores, fusion, highlights, lexical."""

from __future__ import annotations

from datetime import date
from itertools import pairwise

import pytest

from ehr_mip.search.chunker import ResourceText, chunk_resource, windows
from ehr_mip.search.filters import SearchFilters, build_where
from ehr_mip.search.highlights import highlight_ranges, mrn_digits, query_terms, snippet
from ehr_mip.search.lexical import IndexedChunk, LexicalIndex
from ehr_mip.search.ranking import (
    Candidate,
    best_per_resource,
    distance_to_score,
    rank,
    reciprocal_rank_fusion,
)
from ehr_mip.summarization.context import identifier_scrubber
from ehr_mip.summarization.records import PatientInfo

D1, D2 = date(2024, 6, 1), date(2025, 2, 2)


# ---------------------------------------------------------------- where clause


def test_build_where_0_1_n_clauses() -> None:
    assert build_where(SearchFilters()) is None
    assert build_where(SearchFilters(resource_types=("DiagnosticReport",))) == {
        "resource_type": {"$in": ["DiagnosticReport"]}
    }
    where = build_where(SearchFilters(resource_types=("DocumentReference",), date_from=D1,
                                      date_to=D2, patient_key="p"))  # fmt: skip
    assert where == {
        "$and": [
            {"resource_type": {"$in": ["DocumentReference"]}},
            {"patient_key": "p"},
            {"date_ord": {"$gte": D1.toordinal()}},
            {"date_ord": {"$lte": D2.toordinal()}},
            {"date_ord": {"$gt": 0}},
        ]
    }
    # A single date bound still excludes undated records.
    assert build_where(SearchFilters(date_from=D1)) == {
        "$and": [{"date_ord": {"$gte": D1.toordinal()}}, {"date_ord": {"$gt": 0}}]
    }


@pytest.mark.parametrize(
    ("filters", "meta", "expected"),
    [
        (SearchFilters(), {"resource_type": "Observation", "patient_key": "p", "date_ord": 0},
         True),
        (SearchFilters(date_from=D1), {"resource_type": "X", "patient_key": "p", "date_ord": 0},
         False),
        (SearchFilters(date_from=D1, date_to=D1),
         {"resource_type": "X", "patient_key": "p", "date_ord": D1.toordinal()}, True),
        (SearchFilters(date_to=D1),
         {"resource_type": "X", "patient_key": "p", "date_ord": D2.toordinal()}, False),
        (SearchFilters(resource_types=("DiagnosticReport",)),
         {"resource_type": "DocumentReference", "patient_key": "p", "date_ord": 5}, False),
        (SearchFilters(patient_key="q"),
         {"resource_type": "X", "patient_key": "p", "date_ord": 5}, False),
    ],
)  # fmt: skip
def test_python_filter_matches_where_rules(
    filters: SearchFilters, meta: dict[str, object], expected: bool
) -> None:
    assert filters.matches(meta) is expected


# ---------------------------------------------------------------- chunker


def test_chunker_windows_and_overlap() -> None:
    sentences = [f"Sentence {i} " + "word " * 18 + "end." for i in range(30)]  # 21 words each
    parts = windows(" ".join(sentences), size=180, overlap=30)
    assert len(parts) > 1
    assert all(len(p.split()) <= 180 + 21 for p in parts)
    for previous, current in pairwise(parts):
        assert current.split()[:30] == previous.split()[-30:]
    assert windows("") == []
    assert windows("Short note.") == ["Short note."]


def test_long_sentence_is_split_by_words() -> None:
    parts = windows("word " * 500, size=180, overlap=30)
    assert all(len(p.split()) <= 180 for p in parts)
    assert sum(len(p.split()) for p in parts) >= 500


def test_chunks_never_contain_names_or_mrns() -> None:
    patient = PatientInfo(patient_key="p", family="Doe", given=("Jane",),
                          birth_date=date(1968, 3, 14), gender="female", mrns=("00012345",),
                          merged=False, conflict=False)  # fmt: skip
    row = ResourceText(
        patient_key="p", resource_id="r", resource_type="DocumentReference",
        subtype="discharge_summary", title="Discharge Summary", date=D2,
        text="Ms. Jane Doe (MRN 00012345, DOB 03/14/1968) admitted with CHF. Call 212-555-0142.",
    )  # fmt: skip
    (chunk,) = chunk_resource(row, identifier_scrubber(patient))
    assert chunk.text.startswith("Discharge summary: Discharge Summary. 2025-02-02. Ms. [patient]")
    for identifier in ("Jane", "Doe", "00012345", "12345", "03/14/1968", "555-0142"):
        assert identifier not in chunk.text
    assert chunk.id == "r:0"
    assert chunk.metadata["date_ord"] == D2.toordinal()
    assert chunk.metadata["date"] == "2025-02-02"


def test_chunker_templates_and_undated() -> None:
    lab = ResourceText(patient_key="p", resource_id="l", resource_type="DiagnosticReport",
                       subtype="LAB", title="Basic metabolic panel", date=None,
                       text="1 abnormal: Potassium H.")  # fmt: skip
    (chunk,) = chunk_resource(lab, [])
    assert chunk.text == "Lab report: Basic metabolic panel. Undated. 1 abnormal: Potassium H."
    assert chunk.metadata["date_ord"] == 0
    encounter = ResourceText(patient_key="p", resource_id="e", resource_type="Encounter",
                             subtype="inpatient", title=None, date=D1, text=None)  # fmt: skip
    assert chunk_resource(encounter, []) == []


# ---------------------------------------------------------------- scores and fusion


@pytest.mark.parametrize(("distance", "score"), [(0.0, 1.0), (0.25, 0.75), (1.0, 0.0), (1.6, 0.0)])
def test_distance_to_score(distance: float, score: float) -> None:
    assert distance_to_score(distance) == pytest.approx(score)


def _candidate(
    chunk: str, resource: str, score: float, day: int = 1, semantic: float = 0.0
) -> Candidate:
    return Candidate(chunk, resource, day, score, semantic, "semantic")


def test_best_chunk_per_resource() -> None:
    grouped = best_per_resource([_candidate("a:0", "a", 0.4, semantic=0.4),
                                 _candidate("a:1", "a", 0.7, semantic=0.2),
                                 _candidate("b:0", "b", 0.5)])  # fmt: skip
    by_resource = {c.resource_id: c for c in grouped}
    assert by_resource["a"].chunk_id == "a:1"
    assert by_resource["a"].semantic_score == 0.4  # best semantic of any chunk
    assert len(grouped) == 2


def test_rank_sorts_by_score_then_newer_date_and_cuts() -> None:
    ranked = rank([_candidate("a:0", "a", 0.5, day=10), _candidate("b:0", "b", 0.5, day=20),
                   _candidate("c:0", "c", 0.9), _candidate("d:0", "d", 0.1)], top_k=3)  # fmt: skip
    assert [c.resource_id for c in ranked] == ["c", "b", "a"]


def test_rrf_order() -> None:
    fused = reciprocal_rank_fusion([("x", 0.9), ("y", 0.8), ("z", 0.7)], ["y", "w"])
    order = sorted(fused, key=lambda i: -fused[i][0])
    assert order[0] == "y"  # second semantically, first lexically
    assert fused["y"][1] == "hybrid"
    assert fused["x"][1] == "semantic"
    assert fused["w"][1] == "lexical"
    assert all(0 < score <= 1 for score, _ in fused.values())
    assert reciprocal_rank_fusion([("a", 1.0)], ["a"])["a"][0] == 1.0


# ---------------------------------------------------------------- highlights and MRN


def test_query_terms_drop_stop_words_and_keep_abbreviations() -> None:
    assert query_terms("The CT of the chest and high K") == ["ct", "chest", "high", "k"]


def test_highlight_ranges() -> None:
    text = "Potassium 5.9 (H); potassium-sparing. High potassium noted."
    ranges = highlight_ranges(text, ["potassium", "high"])
    assert [text[s:e] for s, e in ranges] == ["Potassium", "potassium", "High", "potassium"]
    assert highlight_ranges("kidney", ["kid"]) == []  # whole words only
    assert highlight_ranges("abc abc", ["abc", "abc abc"]) == [(0, 7)]  # overlaps merge


def test_snippet_word_boundary() -> None:
    text = "Intro words. " * 30 + "The key finding is hyperkalemia here. " + "Tail words. " * 30
    cut = snippet(text, ["hyperkalemia"])
    assert len(cut) <= 320
    assert "hyperkalemia" in cut
    assert cut.startswith("…")
    assert cut.endswith("…")
    assert snippet("Short text.", []) == "Short text."
    head = snippet("word " * 200, [])
    assert len(head) <= 320
    assert head.endswith("…")
    assert not head.startswith("…")


@pytest.mark.parametrize(
    ("query", "digits"),
    [("MRN 00012345", "00012345"), ("mrn:12345", "12345"), ("00012345", "00012345"),
     ("123", None), ("kidney 12345", None), ("123456789", None)],
)  # fmt: skip
def test_mrn_pattern(query: str, digits: str | None) -> None:
    assert mrn_digits(query) == digits


# ---------------------------------------------------------------- lexical


def test_lexical_index_filters_and_name_tokens() -> None:
    chunks = [
        IndexedChunk("a:0", "Potassium high on BMP", {"patient_key": "p1", "resource_type":
                     "DiagnosticReport", "resource_id": "a", "date_ord": 10, "chunk_index": 0}),
        IndexedChunk("b:0", "Chest x-ray clear", {"patient_key": "p2", "resource_type":
                     "DiagnosticReport", "resource_id": "b", "date_ord": 0, "chunk_index": 0}),
    ]  # fmt: skip
    index = LexicalIndex(chunks, {"p2": "Marcus Hale"})
    assert index.search("potassium", SearchFilters(), 5) == ["a:0"]
    assert index.search("hale", SearchFilters(), 5) == ["b:0"]  # name, not chunk text
    assert index.search("hale", SearchFilters(date_from=date(1, 1, 1)), 5) == []
    assert LexicalIndex([]).search("anything", SearchFilters(), 5) == []
    assert [c.chunk_id for c in index.for_patient({"p1"}, SearchFilters())] == ["a:0"]


def test_summary_chunk_is_dated_by_newest_record() -> None:
    from datetime import UTC, datetime  # noqa: PLC0415

    from ehr_mip.search.chunker import chunk_summary  # noqa: PLC0415
    from ehr_mip.summarization.schemas import ClinicalSummary, Confidence  # noqa: PLC0415

    summary = ClinicalSummary(
        patient_key="p", chief_concern="Sepsis in Jane Doe.", key_diagnoses=[], recent_media=[],
        flagged_anomalies=[], overview="Not documented", self_reported_confidence="low",
        word_count=6, confidence=Confidence(level="low", score=0.4, rationale="Offline."),
        provider="extractive", model=None, prompt_version="v1", bundle_hash="h",
        generated_at=datetime(2026, 11, 21, tzinfo=UTC), cache_key="k",
    )  # fmt: skip
    patient = PatientInfo(patient_key="p", family="Doe", given=("Jane",), birth_date=None,
                          gender="female", mrns=(), merged=False, conflict=False)  # fmt: skip
    (chunk,) = chunk_summary(summary, identifier_scrubber(patient), D2)
    assert chunk.date == D2
    assert chunk.resource_id == "summary:p"
    assert chunk.resource_type == "ClinicalSummary"
    assert "Doe" not in chunk.text
    assert chunk.text.startswith("Clinical summary. Chief concern: Sepsis in [patient] [patient].")


def test_windows_never_exceed_size_with_long_sentences() -> None:
    text = "Short opener here. " + " ".join(["long"] * 170) + ". Tail sentence."
    parts = windows(text, size=180, overlap=30)
    assert all(len(p.split()) <= 180 for p in parts)
    assert sum(len(p.split()) for p in parts) >= 170


# ---------------------------------------------------------------- newest order


def _chunk(
    chunk_id: str,
    resource: str,
    text: str,
    day: date | None,
    *,
    kind: str = "DiagnosticReport",
    patient: str = "p",
) -> IndexedChunk:
    return IndexedChunk(
        chunk_id,
        text,
        {
            "resource_id": resource,
            "resource_type": kind,
            "patient_key": patient,
            "date_ord": day.toordinal() if day else 0,
            "chunk_index": int(chunk_id[-1]),
        },
    )


def _newest(index: LexicalIndex, query: str, filters: SearchFilters | None = None) -> list[str]:
    found = index.newest(query, filters or SearchFilters(), 5)
    return [str(chunk.metadata["resource_id"]) for chunk in found]


def test_newest_finds_the_newest_beyond_any_candidate_pool() -> None:
    old = [_chunk(f"o{i}-0", f"old{i}", "pulmonary embolism " * 5, D1) for i in range(60)]
    new = _chunk("new-0", "new", "long report " * 40 + "Pulmonary embolism.", D2)
    assert _newest(LexicalIndex([*old, new]), "pulmonary embolism")[0] == "new"


def test_newest_needs_every_word_as_a_whole_word() -> None:
    index = LexicalIndex(
        [
            _chunk("a-0", "a", "pulmonary nodule", D2),
            _chunk("b-0", "b", "pulmonary embolisms", D2),
            _chunk("c-0", "c", "Embolism, pulmonary.", D1),
        ]
    )
    assert _newest(index, "the pulmonary embolism") == ["c"]
    assert _newest(index, "pulmonary embolism zzqx") == []
    assert _newest(index, "the of") == []


def test_newest_matches_across_the_chunks_of_one_record_once() -> None:
    index = LexicalIndex(
        [_chunk("r-0", "r", "pulmonary", D2), _chunk("r-1", "r", "embolism embolism", D2)]
    )
    assert _newest(index, "pulmonary embolism") == ["r"]


def test_newest_puts_undated_last_and_breaks_ties_by_id() -> None:
    index = LexicalIndex(
        [
            _chunk("u-0", "undated", "sepsis", None),
            _chunk("b-0", "b", "sepsis", D2),
            _chunk("a-0", "a", "sepsis", D2),
            _chunk("o-0", "old", "sepsis", D1),
        ]
    )
    assert _newest(index, "sepsis") == ["a", "b", "old", "undated"]


def test_newest_never_returns_an_ai_summary() -> None:
    index = LexicalIndex(
        [
            _chunk("s-0", "summary", "sepsis", D2, kind="ClinicalSummary"),
            _chunk("r-0", "r", "sepsis", D1),
        ]
    )
    assert _newest(index, "sepsis") == ["r"]
    assert _newest(index, "sepsis", SearchFilters(resource_types=("ClinicalSummary",))) == []


def test_newest_applies_filters_and_knows_patient_names() -> None:
    index = LexicalIndex(
        [
            _chunk("a-0", "a", "sepsis", D2, kind="DocumentReference"),
            _chunk("b-0", "b", "sepsis", D1),
            _chunk("c-0", "c", "sepsis", D1, patient="q"),
        ],
        {"q": "Rivera"},
    )
    assert _newest(index, "sepsis", SearchFilters(resource_types=("DiagnosticReport",))) == [
        "b",
        "c",
    ]
    assert _newest(index, "sepsis", SearchFilters(date_to=D1, patient_key="p")) == ["b"]
    assert _newest(index, "rivera sepsis") == ["c"]
