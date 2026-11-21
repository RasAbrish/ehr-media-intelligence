"""Structured JSON logging.

Logs carry ids only, never names, MRNs, dates of birth or note text. Callers pass
the PHI redaction processor (``observability/log_redaction.py``) as an extra
processor, because this module sits below ``observability`` in the layer contract.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

import structlog


class _CurrentStderr:
    """Writes to whatever ``sys.stderr`` is at call time (test runners swap it)."""

    def write(self, text: str) -> int:
        return sys.stderr.write(text)

    def flush(self) -> None:
        sys.stderr.flush()


def configure_logging(
    level: str = "INFO",
    *,
    json: bool = True,
    extra_processors: Sequence[structlog.typing.Processor] = (),
) -> None:
    """Configure structlog and the stdlib root logger once per process."""
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            structlog.processors.EventRenamer("event"),
            *extra_processors,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(file=_CurrentStderr()),  # type: ignore[arg-type]
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=level, stream=sys.stderr, format="%(message)s")
