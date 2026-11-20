"""Domain exceptions. The API layer maps them to RFC 9457 problem+json in one place."""

from __future__ import annotations


class EhrMipError(Exception):
    """Base class for every domain error raised by the platform."""

    code: str = "internal"


class NotImplementedYetError(EhrMipError):
    """Raised by pipeline stages that a later delivery phase implements."""

    code = "not_implemented"

    def __init__(self, stage: str, phase: int) -> None:
        super().__init__(f"'{stage}' is implemented in Phase {phase}.")
        self.stage = stage
        self.phase = phase


class PathOutsideRawDirError(EhrMipError):
    """A reader was asked to open a path that escapes DATA_RAW_DIR."""

    code = "path_outside_raw_dir"


class EmptyIngestionError(EhrMipError):
    """An ingestion produced no patients; saving it would wipe the existing store."""

    code = "empty_ingestion"
