"""``ehr-mip`` command line interface.

Each pipeline stage becomes real in the phase listed in ``docs/08-DELIVERY.md``.
Until then the command exits with ``EXIT_NOT_IMPLEMENTED`` and says which phase delivers it.
"""

from __future__ import annotations

import typer

from ehr_mip import __version__
from ehr_mip.config import get_settings
from ehr_mip.errors import NotImplementedYetError

# Distinct from 1 (failure) and 2 (usage error) so automation can tell "not built yet" apart.
EXIT_NOT_IMPLEMENTED = 3

app = typer.Typer(
    name="ehr-mip",
    help="EHR Media Intelligence Platform pipeline and server.",
    no_args_is_help=True,
    add_completion=False,
)

_STAGES: dict[str, tuple[int, str]] = {
    "ingest": (1, "Read, clean, resolve identities and dedupe raw EHR exports."),
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
