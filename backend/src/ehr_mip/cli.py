"""``ehr-mip`` command line interface.

Each pipeline stage becomes real in the phase listed in ``docs/08-DELIVERY.md``.
Until then the command exits with ``EXIT_NOT_IMPLEMENTED`` and says which phase delivers it.
"""

from __future__ import annotations

from contextlib import closing

import typer
from rich.console import Console
from rich.table import Table

from ehr_mip import __version__
from ehr_mip.config import get_settings
from ehr_mip.db.connection import connect
from ehr_mip.db.repositories import PipelineRunRepository
from ehr_mip.errors import NotImplementedYetError
from ehr_mip.ingestion.models import IngestionStats
from ehr_mip.ingestion.pipeline import run_ingestion
from ehr_mip.ingestion.repository import IngestionRepository
from ehr_mip.logging import configure_logging

# Distinct from 1 (failure) and 2 (usage error) so automation can tell "not built yet" apart.
EXIT_NOT_IMPLEMENTED = 3

app = typer.Typer(
    name="ehr-mip",
    help="EHR Media Intelligence Platform pipeline and server.",
    no_args_is_help=True,
    add_completion=False,
)

_STAGES: dict[str, tuple[int, str]] = {
    "normalize": (2, "Map clean records to FHIR R4B bundles and validate them."),
    "summarize": (3, "Generate grounded clinical summaries per patient."),
    "eval": (3, "Score summaries against the golden and adversarial sets."),
    "index": (4, "Chunk, embed and index records and summaries."),
    "run-all": (4, "Run ingest, normalize, summarize and index in order."),
    "serve": (4, "Start the FastAPI server."),
}


def _pending(stage: str, phase: int) -> None:
    err = NotImplementedYetError(stage, phase)
    typer.secho(str(err), fg=typer.colors.YELLOW, err=True)
    raise typer.Exit(code=EXIT_NOT_IMPLEMENTED)


def _register(stage: str, phase: int, help_text: str) -> None:
    def command() -> None:
        _pending(stage, phase)

    command.__doc__ = f"{help_text} (Phase {phase})"
    app.command(name=stage)(command)


for _name, (_phase, _help) in _STAGES.items():
    _register(_name, _phase, _help)


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
    configure_logging(settings.log_level)
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
