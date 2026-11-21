"""Prompt registry (docs/10-AI-DESIGN.md section 3).

Prompts are files under ``prompts/<version>/``. A released version is never edited:
a change creates a new folder, and because the cache key includes the version,
every summary is regenerated with the new prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from ehr_mip.summarization.schemas import ClinicalSummaryLLM

_FILES = ("system.md", "user_template.md", "example_input.xml", "example_output.json")


@dataclass(frozen=True)
class Prompt:
    version: str
    system: str
    user_template: str
    example_input: str
    example_output: str

    def render_user(self, context: str) -> str:
        """Fill the user template. ``str.replace`` because the template contains JSON braces."""
        example = (
            "<example>\n<example_input>\n"
            f"{self.example_input.strip()}\n"
            "</example_input>\n<example_output>\n"
            f"{self.example_output.strip()}\n"
            "</example_output>\n</example>"
        )
        return (
            self.user_template.replace("{example}", example).replace("{context}", context).strip()
            + "\n"
        )


@lru_cache(maxsize=8)
def load_prompt(version: str) -> Prompt:
    """Load a prompt version, checking that its example output matches the schema."""
    folder = resources.files("ehr_mip.summarization.prompts").joinpath(version)
    if not folder.is_dir():
        msg = f"Unknown prompt version {version!r}"
        raise ValueError(msg)
    texts = {name: folder.joinpath(name).read_text(encoding="utf-8") for name in _FILES}
    ClinicalSummaryLLM.model_validate_json(texts["example_output.json"])
    return Prompt(
        version=version,
        system=texts["system.md"].strip(),
        user_template=texts["user_template.md"],
        example_input=texts["example_input.xml"],
        example_output=texts["example_output.json"],
    )


def available_versions() -> list[str]:
    root = resources.files("ehr_mip.summarization.prompts")
    return sorted(p.name for p in root.iterdir() if p.is_dir() and p.name.startswith("v"))
