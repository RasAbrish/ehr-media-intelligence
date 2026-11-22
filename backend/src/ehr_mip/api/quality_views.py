"""Assembly for the directory, data quality and stats endpoints (docs/04 sections 4.3, 6.1,
6.8 and 8). Routers validate input and call these; SQL lives in `db.listings`."""

from __future__ import annotations

import math
import sqlite3
from collections import Counter
from datetime import date
from typing import Any

from ehr_mip.api.mappers import patient_ref
from ehr_mip.api.masking import mask_value, quarantine_preview
from ehr_mip.api.schemas.common import PatientRef
from ehr_mip.api.schemas.patients import AnomalyCounts, PatientListItem
from ehr_mip.api.schemas.quality import (
    AuditEntryItem,
    AuditEntryWithPatient,
    BySeverity,
    CodeCount,
    FeedbackOverview,
    IngestionOverview,
    LastRunOut,
    LlmOverview,
    PromptFeedback,
    QualityOverview,
    QuarantineItem,
    RuleCount,
    SummaryOverview,
    ValidationIssueItem,
    ValidationOverview,
)
from ehr_mip.api.schemas.system import ResourcesByType, StatsResponse
from ehr_mip.db.listings import DirectorySort, Listings
from ehr_mip.db.listings import Page as RowPage
from ehr_mip.db.read_models import PatientReader, ResourceReader, StatusReader
from ehr_mip.fhir.store import BundleStore
from ehr_mip.summarization.feedback import FeedbackRepository
from ehr_mip.summarization.guardrails import content_interventions

P95 = 0.95


def total_pages(total: int, page_size: int) -> int:
    return max(math.ceil(total / page_size), 1) if page_size else 1


def page_out(rows: list[Any], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": rows,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages(total, page_size),
    }


def directory(
    conn: sqlite3.Connection,
    *,
    q: str | None,
    sort: DirectorySort,
    descending: bool,
    conflict_only: bool,
    page: int,
    page_size: int,
    today: date,
) -> dict[str, Any]:
    listings = Listings(conn)
    result: RowPage = listings.directory(
        q=q,
        sort=sort,
        descending=descending,
        conflict_only=conflict_only,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    summaries = listings.current_summaries([r.patient.patient_key for r in result.rows])
    items = []
    for row in result.rows:
        summary = summaries.get(row.patient.patient_key)
        severities = Counter(a["severity"] for a in (summary or {}).get("flagged_anomalies", []))
        items.append(
            PatientListItem(
                **patient_ref(row.patient, today).model_dump(),
                last_activity=row.last_activity,
                resource_count=row.resource_count,
                has_summary=summary is not None,
                chief_concern=summary["chief_concern"] if summary else None,
                anomaly_counts=AnomalyCounts(
                    high=severities["high"], moderate=severities["moderate"], low=severities["low"]
                ),
            )
        )
    return page_out(items, result.total, page, page_size)


def _audit_item(row: sqlite3.Row) -> dict[str, Any]:
    field = row["field"]
    return {
        "id": int(row["id"]),
        "run_id": str(row["run_id"] or ""),
        "record_id": str(row["record_id"]),
        "stage": row["stage"],
        "field": field,
        "rule": row["rule"],
        "before": mask_value(field, row["before"]),
        "after": mask_value(field, row["after"]),
        "severity": row["severity"],
        "message": row["message"],
    }


def patient_audit(
    conn: sqlite3.Connection, key: str, *, severities: list[str], page: int, page_size: int
) -> dict[str, Any]:
    result = Listings(conn).audit(
        patient_key=key, severities=severities, limit=page_size, offset=(page - 1) * page_size
    )
    items = [AuditEntryItem(**_audit_item(r)) for r in result.rows]
    return page_out(items, result.total, page, page_size)


def _refs(conn: sqlite3.Connection, keys: list[str | None], today: date) -> dict[str, PatientRef]:
    patients = PatientReader(conn).many(k for k in keys if k)
    return {k: patient_ref(p, today) for k, p in patients.items()}


def quality_audit(
    conn: sqlite3.Connection,
    *,
    rule: str | None,
    stages: list[str],
    severities: list[str],
    patient_key: str | None,
    page: int,
    page_size: int,
    today: date,
) -> dict[str, Any]:
    result = Listings(conn).audit(
        patient_key=patient_key,
        severities=severities,
        stages=stages,
        rule_prefix=rule,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    refs = _refs(conn, [r["patient_key"] for r in result.rows], today)
    items = [
        AuditEntryWithPatient(**_audit_item(r), patient=refs.get(r["patient_key"] or ""))
        for r in result.rows
    ]
    return page_out(items, result.total, page, page_size)


def validation_issues(
    conn: sqlite3.Connection,
    *,
    severities: list[str],
    resource_types: list[str],
    code: str | None,
    page: int,
    page_size: int,
    today: date,
) -> dict[str, Any]:
    result = Listings(conn).validation(
        severities=severities,
        resource_types=resource_types,
        code=code,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    refs = _refs(conn, [r["patient_key"] for r in result.rows], today)
    items = [
        ValidationIssueItem(
            id=int(r["id"]),
            patient=refs[r["patient_key"]],
            resource_type=r["resource_type"] or "Bundle",
            resource_id=r["resource_id"],
            path=r["path"] or "",
            severity=r["severity"],
            code=r["code"],
            message=r["message"],
        )
        for r in result.rows
        if r["patient_key"] in refs
    ]
    return page_out(items, result.total, page, page_size)


def quarantine(conn: sqlite3.Connection, *, page: int, page_size: int) -> dict[str, Any]:
    result = Listings(conn).quarantine(limit=page_size, offset=(page - 1) * page_size)
    items = [
        QuarantineItem(
            id=int(r["id"]),
            run_id=str(r["run_id"] or ""),
            source_locator=r["source_locator"],
            reason=r["reason"],
            payload_preview=quarantine_preview(r["payload_json"]),
        )
        for r in result.rows
    ]
    return page_out(items, result.total, page, page_size)


def _severity(counts: dict[str, int]) -> BySeverity:
    return BySeverity(
        info=counts.get("info", 0), warning=counts.get("warning", 0), error=counts.get("error", 0)
    )


def _rate(helpful: int, total: int) -> float | None:
    return round(helpful / total, 4) if total else None


def overview(conn: sqlite3.Connection) -> QualityOverview:
    listings = Listings(conn)
    ingest = listings.latest_run_stats("ingest")
    records = {k: int(v) for k, v in (ingest.get("records_read") or {}).items()}
    ingestion = IngestionOverview(
        records_read=sum(records.values()),
        by_format={
            "json": records.get("json", 0),
            "csv": records.get("csv", 0),
            "txt": records.get("txt", 0),
        },
        patients=int(ingest.get("patients", 0)),
        documents=int(ingest.get("documents", 0)),
        lab_results=int(ingest.get("lab_results", 0)),
        exact_duplicates_removed=int(ingest.get("duplicates_exact", 0)),
        near_duplicates_removed=int(ingest.get("duplicates_near", 0)),
        identities_merged=int(ingest.get("identities_merged", 0)),
        identity_conflicts=int(ingest.get("identity_conflicts", 0)),
        quarantined=int(ingest.get("quarantined", 0)),
        audit_by_severity=_severity(listings.counts_by("audit_log", "severity")),
        top_rules=[RuleCount(rule=r, count=n) for r, n in listings.top_rules()],
    )
    bundles, valid = listings.bundle_counts()
    validation = ValidationOverview(
        bundles=bundles,
        valid_bundles=valid,
        issues_by_severity=_severity(listings.counts_by("validation_issues", "severity")),
        top_codes=[CodeCount(code=c, count=n) for c, n in listings.top_codes()],
    )

    patient_keys = BundleStore(conn).patient_keys()
    summaries = list(listings.current_summaries(patient_keys).values())
    words = [int(s["word_count"]) for s in summaries]
    providers = Counter(s["provider"] for s in summaries)
    levels = Counter(s["confidence"]["level"] for s in summaries)
    calls = listings.llm_rows()
    latencies = sorted(int(r["latency_ms"]) for r in calls)
    p95 = latencies[min(len(latencies) - 1, int(P95 * len(latencies)))] if latencies else 0
    feedback = FeedbackRepository(conn).by_prompt_version()
    helpful = sum(h for _, h, _ in feedback)
    not_helpful = sum(n for _, _, n in feedback)
    summary = SummaryOverview(
        total=len(summaries),
        by_provider={
            "anthropic": providers.get("anthropic", 0),
            "extractive": providers.get("extractive", 0),
        },
        avg_word_count=round(sum(words) / len(words), 1) if words else 0.0,
        max_word_count=max(words, default=0),
        confidence={
            "low": levels.get("low", 0),
            "medium": levels.get("medium", 0),
            "high": levels.get("high", 0),
        },
        guardrail_interventions=sum(
            content_interventions(s.get("guardrail_notes", [])) for s in summaries
        ),
        llm=LlmOverview(
            calls=len(calls),
            fallback_calls=sum(r["status"] == "fallback" for r in calls),
            failed_calls=sum(r["status"] == "failed" for r in calls),
            input_tokens=sum(int(r["input_tokens"] or 0) for r in calls),
            output_tokens=sum(int(r["output_tokens"] or 0) for r in calls),
            cost_usd_estimate=round(sum(float(r["cost_usd_estimate"] or 0) for r in calls), 4),
            p95_latency_ms=p95,
        ),
        feedback=FeedbackOverview(
            helpful=helpful,
            not_helpful=not_helpful,
            helpful_rate=_rate(helpful, helpful + not_helpful),
            by_prompt_version=[
                PromptFeedback(prompt_version=v, helpful_rate=_rate(h, h + n), votes=h + n)
                for v, h, n in feedback
            ],
        ),
    )
    last = StatusReader(conn).last_run()
    return QualityOverview(
        ingestion=ingestion,
        validation=validation,
        summaries=summary,
        last_run=LastRunOut(
            run_id=last["run_id"],
            finished_at=last["finished_at"],
            status="succeeded" if last["finished_at"] else "running",
        )
        if last
        else None,
    )


def stats(conn: sqlite3.Connection) -> StatsResponse:
    counts = StatusReader(conn).counts()
    index = Listings(conn).latest_run_stats("index")
    return StatsResponse(
        patients=counts["patients"],
        resources_by_type=ResourcesByType(**ResourceReader(conn).counts_by_type()),
        searchable_records=int(index.get("resources", 0)) + int(index.get("summaries", 0)),
        summaries=counts["summaries"],
        last_pipeline_run_at=Listings(conn).last_finished_at(),
    )
