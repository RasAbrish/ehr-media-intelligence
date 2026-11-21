"""Validation report as JSON and Markdown (FR-2.5). Ids only, never names or MRNs."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from ehr_mip.fhir.models import NormalizedBundle

MAX_LISTED_ISSUES = 100
_SEVERITIES = ("error", "warning", "info")


def build_report(results: Sequence[NormalizedBundle], *, generated_at: datetime) -> dict[str, Any]:
    issues = [i for r in results for i in r.validation.issues]
    by_code: dict[str, dict[str, Any]] = {}
    for issue in issues:
        entry = by_code.setdefault(issue.code, {"severity": issue.severity, "count": 0})
        entry["count"] += 1
    resources = Counter(row.resource_type for r in results for row in r.built.rows)
    severity_counts: Counter[str] = Counter(i.severity for i in issues)
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "bundles": len(results),
        "valid_bundles": sum(r.validation.is_valid for r in results),
        "resources_by_type": dict(sorted(resources.items())),
        "issues_by_severity": {s: severity_counts.get(s, 0) for s in _SEVERITIES},
        "issues_by_code": dict(sorted(by_code.items())),
        "bundle_results": [
            {
                "patient_key": r.built.patient_key,
                "bundle_hash": r.built.bundle_hash,
                "is_valid": r.validation.is_valid,
                "errors": r.validation.error_count,
                "warnings": r.validation.warning_count,
                "infos": r.validation.info_count,
            }
            for r in results
        ],
        "issues": [i.model_dump() for i in issues],
    }


def _cell(value: object) -> str:
    """One table cell: no pipes or line breaks, which would break the Markdown table."""
    return " ".join(str(value).replace("|", "/").split())


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    severity = report["issues_by_severity"]
    lines = [
        "# FHIR validation report",
        "",
        f"Generated {report['generated_at']}. One FHIR R4 (R4B package) Bundle per patient, "
        "validated with `fhir.resources` and the business rules in `docs/05-ALGORITHMS.md` "
        "section 2.2. Patients are identified by key only.",
        "",
        "## Summary",
        "",
        *_table(
            ["Measure", "Value"],
            [
                ["Bundles", report["bundles"]],
                ["Valid bundles (no errors)", report["valid_bundles"]],
                ["Errors", severity["error"]],
                ["Warnings", severity["warning"]],
                ["Info", severity["info"]],
            ],
        ),
        "",
        "## Resources",
        "",
        *_table(["Resource type", "Count"], list(report["resources_by_type"].items())),
        "",
        "## Issues by rule",
        "",
    ]
    if report["issues_by_code"]:
        lines += _table(
            ["Rule", "Severity", "Count"],
            [
                [f"`{code}`", v["severity"], v["count"]]
                for code, v in report["issues_by_code"].items()
            ],
        )
    else:
        lines.append("No issues.")
    invalid = [b for b in report["bundle_results"] if not b["is_valid"]]
    lines += ["", "## Invalid bundles", ""]
    if invalid:
        lines += _table(
            ["Patient key", "Errors", "Warnings"],
            [[f"`{b['patient_key']}`", b["errors"], b["warnings"]] for b in invalid],
        )
    else:
        lines.append("None. Every bundle passed schema and reference checks.")
    notable = [i for i in report["issues"] if i["severity"] != "info"]
    lines += ["", "## Errors and warnings", ""]
    if notable:
        shown = notable[:MAX_LISTED_ISSUES]
        lines += _table(
            ["Severity", "Rule", "Resource", "Path", "Message"],
            [
                [
                    i["severity"],
                    f"`{i['code']}`",
                    f"{i['resource_type']}/{(i['resource_id'] or '')[:8]}",
                    f"`{i['path']}`" if i["path"] else "",
                    i["message"],
                ]
                for i in shown
            ],
        )
        if len(notable) > len(shown):
            lines += ["", f"{len(notable) - len(shown)} more in `validation_report.json`."]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any], reports_dir: Path) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "validation_report.json"
    md_path = reports_dir / "validation_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
