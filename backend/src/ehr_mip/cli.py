"""``ehr-mip`` command line interface.

Each pipeline stage becomes real in the phase listed in ``docs/08-DELIVERY.md``.
Until then the command exits with ``EXIT_NOT_IMPLEMENTED`` and says which phase delivers it.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import UTC, datetime

import typer
from rich.console import Console
from rich.table import Table

from ehr_mip import __version__
from ehr_mip.config import PROJECT_ROOT, Settings, get_settings
from ehr_mip.db.connection import connect
from ehr_mip.db.read_models import StatusReader
from ehr_mip.db.repositories import PipelineRunRepository
from ehr_mip.errors import NotImplementedYetError
from ehr_mip.fhir.models import NormalizedBundle
from ehr_mip.fhir.pipeline import run_normalization
from ehr_mip.fhir.report import build_report, write_reports
from ehr_mip.fhir.store import BundleStore
from ehr_mip.ingestion.cleaners.dates import today_local
from ehr_mip.ingestion.models import IngestionStats
from ehr_mip.ingestion.pipeline import run_ingestion
from ehr_mip.ingestion.repository import IngestionRepository
from ehr_mip.logging import configure_logging
from ehr_mip.observability.log_redaction import redact_phi
from ehr_mip.summarization.evaluate import (
    run_eval,
    write_manual_review_template,
)
from ehr_mip.summarization.evaluate import (
    write_reports as write_eval_reports,
)
from ehr_mip.summarization.providers import make_provider
from ehr_mip.summarization.service import SummaryBatch, SummaryService

# Distinct from 1 (failure) and 2 (usage error) so automation can tell "not built yet" apart.
EXIT_NOT_IMPLEMENTED = 3

app = typer.Typer(
    name="ehr-mip",
    help="EHR Media Intelligence Platform pipeline and server.",
    no_args_is_help=True,
    add_completion=False,
)


def _pending(stage: str, phase: int) -> None:
    err = NotImplementedYetError(stage, phase)
    typer.secho(str(err), fg=typer.colors.YELLOW, err=True)
    raise typer.Exit(code=EXIT_NOT_IMPLEMENTED)


def _stats_table(stats: IngestionStats) -> Table:
    table = Table(title="Ingestion", show_header=True, header_style="bold")
    table.add_column("Measure")
    table.add_column("Count", justify="right")
    for fmt, count in stats.records_read.items():
        table.add_row(f"Records read ({fmt})", str(count))
    rows = [
        ("Patients", stats.patients),
        ("Encounters", stats.encounters),
        ("Documents", stats.documents),
        ("Lab results", stats.lab_results),
        ("Lab reports", stats.lab_reports),
        ("Exact duplicates removed", stats.duplicates_exact),
        ("Near duplicates removed", stats.duplicates_near),
        ("Duplicate lab rows removed", stats.duplicates_lab),
        ("Identities merged (two MRNs)", stats.identities_merged),
        ("Identity conflicts flagged", stats.identity_conflicts),
        ("Records quarantined", stats.quarantined),
    ]
    for label, count in rows:
        table.add_row(label, str(count))
    for severity, count in stats.audit_by_severity.items():
        table.add_row(f"Audit entries ({severity})", str(count))
    return table


@app.command()
def ingest() -> None:
    """Read, clean, resolve identities and dedupe raw EHR exports into SQLite. (Phase 1)"""
    settings = get_settings()
    _configure_logging(settings)
    result = run_ingestion(settings.data_raw_dir)
    if not result.patients:
        typer.secho(
            f"No patients found in {settings.data_raw_dir}. Run `make data` or check "
            "DATA_RAW_DIR. The database was not changed.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    with closing(connect(settings.sqlite_path)) as conn:
        runs = PipelineRunRepository(conn)
        run_id = runs.start("ingest")
        IngestionRepository(conn).save(run_id, result)
        runs.finish(run_id, result.stats.model_dump())
    console = Console()
    console.print(_stats_table(result.stats))
    console.print(f"Run {run_id} saved to {settings.sqlite_path}")


def _normalize_table(results: list[NormalizedBundle]) -> Table:
    table = Table(title="FHIR normalization", show_header=True, header_style="bold")
    table.add_column("Measure")
    table.add_column("Count", justify="right")
    resources = Counter(row.resource_type for r in results for row in r.built.rows)
    rows: list[tuple[str, int]] = [
        ("Bundles", len(results)),
        ("Valid bundles", sum(r.validation.is_valid for r in results)),
        ("Errors", sum(r.validation.error_count for r in results)),
        ("Warnings", sum(r.validation.warning_count for r in results)),
        ("Info", sum(r.validation.info_count for r in results)),
        *((f"{kind} resources", count) for kind, count in sorted(resources.items())),
    ]
    for label, count in rows:
        table.add_row(label, str(count))
    return table


@app.command()
def normalize() -> None:
    """Map clean records to FHIR R4B bundles, validate them and write the report. (Phase 2)"""
    settings = get_settings()
    _configure_logging(settings)
    now = datetime.now(UTC)
    with closing(connect(settings.sqlite_path)) as conn:
        results = run_normalization(conn, today=today_local(), timestamp=now)
        if not results:
            typer.secho(
                "No ingested patients found. Run `make ingest` first. Nothing was changed.",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=1)
        runs = PipelineRunRepository(conn)
        run_id = runs.start("normalize")
        BundleStore(conn).save(results, created_at=now, full_refresh=True)
        report = build_report(results, generated_at=now)
        json_path, md_path = write_reports(report, settings.reports_dir)
        runs.finish(
            run_id, {k: report[k] for k in ("bundles", "valid_bundles", "issues_by_severity")}
        )
    console = Console()
    console.print(_normalize_table(results))
    console.print(f"Reports: {json_path} and {md_path}")


def _service(conn: sqlite3.Connection, settings: Settings) -> SummaryService:
    return SummaryService(
        conn,
        provider=make_provider(settings),
        prompt_version=settings.prompt_version,
        max_concurrency=settings.llm_max_concurrency,
        daily_token_budget=settings.llm_daily_token_budget,
    )


def _configure_logging(settings: Settings) -> None:
    configure_logging(settings.log_level, extra_processors=[redact_phi])


def _require_bundles(conn: sqlite3.Connection) -> None:
    if not BundleStore(conn).patient_keys():
        typer.secho(
            "No FHIR bundles found. Run `make ingest` and `make normalize` first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)


def _summary_table(batch: SummaryBatch, calls: dict[str, float]) -> Table:
    table = Table(title="Summaries", show_header=True, header_style="bold")
    table.add_column("Measure")
    table.add_column("Value", justify="right")
    outcomes = batch.outcomes
    summaries = [o.summary for o in outcomes]
    providers = Counter(s.provider for s in summaries)
    levels = Counter(s.confidence.level for s in summaries)
    rows: list[tuple[str, object]] = [
        ("Patients", len(summaries)),
        ("Failed", len(batch.failed)),
        ("From cache", sum(s.cached for s in summaries)),
        ("Model calls", sum(o.provider_calls for o in outcomes)),
        *((f"Provider: {name}", count) for name, count in sorted(providers.items())),
        (
            "Fallbacks to extractive",
            sum(any(n.startswith("fallback_") for n in s.guardrail_notes) for s in summaries),
        ),
        ("With guardrail notes", sum(bool(s.guardrail_notes) for s in summaries)),
        ("Max words", max((s.word_count for s in summaries), default=0)),
        *((f"Confidence {level}", levels.get(level, 0)) for level in ("high", "medium", "low")),
        ("Tokens (in / out)", f"{int(calls['input'])} / {int(calls['output'])}"),
        ("Estimated cost (USD)", f"{calls['cost']:.4f}"),
    ]
    for label, value in rows:
        table.add_row(label, str(value))
    return table


def _calls_since(conn: sqlite3.Connection, since: datetime) -> dict[str, float]:
    row = conn.execute(
        "SELECT COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0), "
        "COALESCE(SUM(cost_usd_estimate), 0) FROM llm_calls WHERE created_at >= ?",
        (since.isoformat(timespec="seconds"),),
    ).fetchone()
    return {"input": float(row[0]), "output": float(row[1]), "cost": float(row[2])}


@app.command()
def summarize(
    force: bool = typer.Option(False, "--force", help="Regenerate even when cached."),
) -> None:
    """Generate grounded clinical summaries for every patient (cached). (Phase 3)"""
    settings = get_settings()
    _configure_logging(settings)
    started = datetime.now(UTC).replace(microsecond=0)
    with closing(connect(settings.sqlite_path)) as conn:
        _require_bundles(conn)
        runs = PipelineRunRepository(conn)
        run_id = runs.start("summarize")
        batch = asyncio.run(_service(conn, settings).summarize_all(force=force))
        calls = _calls_since(conn, started)
        runs.finish(run_id, {"summaries": len(batch), "failed": len(batch.failed), **calls})
    Console().print(_summary_table(batch, calls))
    if batch.failed:
        typer.secho(
            f"{len(batch.failed)} patients failed; see the summary_failed log events.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)


@app.command(name="eval")
def evaluate() -> None:
    """Score summaries: synthetic, golden and adversarial sets; writes reports/eval_report.*."""
    settings = get_settings()
    _configure_logging(settings)
    fixtures = PROJECT_ROOT / "backend" / "tests" / "fixtures"
    with closing(connect(settings.sqlite_path)) as conn:
        _require_bundles(conn)
        service = _service(conn, settings)
        result = asyncio.run(
            run_eval(
                conn,
                service,
                golden_dir=fixtures / "golden",
                adversarial_dir=fixtures / "adversarial",
                truth_path=settings.data_raw_dir / "_ground_truth.json",
                today=today_local(),
            )
        )
        report, summaries = result.report, result.summaries
        # One sheet per model, so a real-model run never reuses an extractive sheet.
        model = summaries[0].model or "extractive" if summaries else "extractive"
        review = PROJECT_ROOT / "docs" / "eval" / f"manual_review_{model}.md"
        created = write_manual_review_template(conn, review, summaries)
    json_path, md_path = write_eval_reports(report, settings.reports_dir)
    console = Console()
    for gate, ok in report["gates"].items():
        console.print(f"{'pass' if ok else 'FAIL'}  {gate.replace('_', ' ')}")
    console.print(f"Reports: {json_path} and {md_path}")
    if created:
        console.print(f"Manual review sheet created: {review}")
    if not report["passed"]:
        raise typer.Exit(code=1)


@app.command()
def info() -> None:
    """Show the version and the non-secret effective configuration."""
    settings = get_settings()
    rows = {
        "version": __version__,
        "env": settings.env,
        "llm_provider": settings.effective_llm_provider,
        "llm_model": settings.llm_model,
        "prompt_version": settings.prompt_version,
        "search_mode": settings.search_mode,
        "cache_backend": settings.cache_backend,
        "data_raw_dir": str(settings.data_raw_dir),
        "sqlite_path": str(settings.sqlite_path),
    }
    width = max(len(key) for key in rows)
    for key, value in rows.items():
        typer.echo(f"{key.ljust(width)}  {value}")


@app.command()
def index() -> None:
    """Chunk, embed and index records and summaries into Chroma. (Phase 4)"""
    from ehr_mip.search.embedder import SentenceTransformerEmbedder  # noqa: PLC0415 (slow import)
    from ehr_mip.search.indexer import run_index  # noqa: PLC0415
    from ehr_mip.search.vector_store import VectorStore, open_client  # noqa: PLC0415

    settings = get_settings()
    _configure_logging(settings)
    with closing(connect(settings.sqlite_path)) as conn:
        _require_bundles(conn)
        embedder = SentenceTransformerEmbedder(settings.embedding_model, settings.hf_home)
        stats = run_index(
            conn,
            VectorStore(open_client(settings.chroma_dir)),
            embedder,
            index_observations=settings.index_observations,
        )
    table = Table(title="Index", show_header=True, header_style="bold")
    table.add_column("Measure")
    table.add_column("Count", justify="right")
    for label, value in [
        ("Chunks", stats.chunks),
        ("Resources", stats.resources),
        ("Summaries", stats.summaries),
        *((f"Type: {t}", n) for t, n in sorted(stats.by_type.items())),
    ]:
        table.add_row(label, str(value))
    Console().print(table)


@app.command(name="run-all")
def run_all() -> None:
    """Run ingest, normalize, summarize and index in order. (Phase 4)"""
    ingest()
    normalize()
    summarize(force=False)
    index()


def _bootstrap_if_empty(settings: Settings) -> None:
    """AUTO_BOOTSTRAP: fill a store that was never indexed, before the port opens."""
    if not settings.auto_bootstrap:
        return
    with closing(connect(settings.sqlite_path)) as conn:
        if StatusReader(conn).index_version():
            return
    typer.echo("No indexed data found: running the pipeline (AUTO_BOOTSTRAP=true).")
    run_all()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8000, help="Port."),
) -> None:
    """Start the FastAPI server. (Phase 4)"""
    import uvicorn  # noqa: PLC0415

    from ehr_mip.api.main import create_app  # noqa: PLC0415

    _bootstrap_if_empty(get_settings())
    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        access_log=False,  # it prints query strings (patient names); ours logs routes
        limit_concurrency=64,
        timeout_keep_alive=5,
        timeout_graceful_shutdown=10,
    )
