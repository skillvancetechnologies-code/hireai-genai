"""Load and render prompts from app/prompts/library.yaml.

Module owners call `load_prompt("parser_main").format(resume_text=...)`.
They never define prompts inline. All prompts are versioned in the
YAML file and changes require a PR + changelog bump.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

LIBRARY_PATH = Path(__file__).parent.parent / "prompts" / "library.yaml"


class PromptNotFound(KeyError):
    pass


class Prompt:
    """A versioned, renderable prompt with metadata attached."""

    def __init__(self, prompt_id: str, spec: dict[str, Any]):
        self.id = prompt_id
        self.version: int = spec["version"]
        self.model: str = spec["model"]
        self.temperature: float = spec["temperature"]
        self.template: str = spec["template"]
        self.description: str = spec.get("description", "")
        self.json_mode: bool = spec.get("json_mode", False)
        self.changelog: list[str] = spec.get("changelog", [])

    def format(self, **kwargs) -> str:
        return self.template.format(**kwargs)

    def __repr__(self) -> str:
        return f"Prompt(id={self.id}, v{self.version}, model={self.model})"


@lru_cache(maxsize=1)
def _load_library() -> dict[str, dict[str, Any]]:
    if not LIBRARY_PATH.exists():
        raise FileNotFoundError(f"Prompt library not found at {LIBRARY_PATH}")
    with LIBRARY_PATH.open() as f:
        return yaml.safe_load(f) or {}


def load_prompt(prompt_id: str) -> Prompt:
    library = _load_library()
    if prompt_id not in library:
        raise PromptNotFound(f"Prompt '{prompt_id}' not in library.yaml")
    return Prompt(prompt_id, library[prompt_id])


def list_prompts() -> list[str]:
    return list(_load_library().keys())


def reload_library() -> None:
    """Force re-read of library.yaml (for tests/dev)."""
    _load_library.cache_clear()
