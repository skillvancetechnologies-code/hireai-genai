"""Skill name canonicalization using skill_map.yaml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_SKILL_MAP_PATH = Path(__file__).parent / "skill_map.yaml"


@lru_cache(maxsize=1)
def _load_alias_map() -> dict[str, str]:
    """Return {lowercase_alias: canonical_name}. Cached after first load."""
    with _SKILL_MAP_PATH.open(encoding="utf-8") as f:
        raw: dict = yaml.safe_load(f) or {}
    alias_map: dict[str, str] = {}
    for canonical, aliases in raw.items():
        alias_map[canonical.lower()] = canonical
        for alias in (aliases or []):
            alias_map[str(alias).lower()] = canonical
    return alias_map


def normalize_skills(skills: list[str]) -> list[str]:
    """Canonicalize skill names and deduplicate (order-preserving)."""
    alias_map = _load_alias_map()
    seen: set[str] = set()
    result: list[str] = []
    for skill in skills:
        canonical = alias_map.get(skill.strip().lower(), skill.strip())
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            result.append(canonical)
    return result


def reload_skill_map() -> None:
    """Force re-read of skill_map.yaml (for tests/dev)."""
    _load_alias_map.cache_clear()
