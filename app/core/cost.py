"""Per-call token + cost tracking.

Every LLM call writes one JSONL line to data/cost_log.jsonl.
Use `summarize_day()` to print yesterday's spend (called by
scripts/cost_summary.py).
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.core.config import get_settings

log = logging.getLogger(__name__)
_settings = get_settings()

# Pricing in USD per 1M tokens (input, output). Update as needed.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.150, 0.600),
    "gpt-4o": (2.500, 10.000),
    "gpt-4-turbo": (10.000, 30.000),
    "gemini-1.5-flash": (0.075, 0.300),
}


@dataclass
class CallRecord:
    timestamp: str
    model: str
    module: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    cache_hit: bool


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_price, out_price = PRICING.get(model, (0.0, 0.0))
    return (prompt_tokens * in_price + completion_tokens * out_price) / 1_000_000


def log_call(
    model: str,
    module: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cache_hit: bool = False,
) -> CallRecord:
    cost = 0.0 if cache_hit else estimate_cost(model, prompt_tokens, completion_tokens)
    record = CallRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        model=model,
        module=module,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=round(cost, 6),
        cache_hit=cache_hit,
    )
    path = Path(_settings.cost_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(asdict(record)) + "\n")
    return record


def summarize_day(date_iso: Optional[str] = None) -> dict:
    """Return cost rollup for a given UTC date (defaults to yesterday)."""
    if date_iso is None:
        target = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    else:
        target = date_iso
    path = Path(_settings.cost_log_path)
    if not path.exists():
        return {"date": target, "total_usd": 0.0, "by_module": {}, "by_model": {}, "calls": 0, "cache_hits": 0}

    total = 0.0
    by_module: dict[str, float] = {}
    by_model: dict[str, float] = {}
    calls = 0
    hits = 0
    with path.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not r.get("timestamp", "").startswith(target):
                continue
            calls += 1
            if r.get("cache_hit"):
                hits += 1
            total += r.get("cost_usd", 0.0)
            by_module[r["module"]] = by_module.get(r["module"], 0.0) + r["cost_usd"]
            by_model[r["model"]] = by_model.get(r["model"], 0.0) + r["cost_usd"]

    return {
        "date": target,
        "total_usd": round(total, 4),
        "by_module": {k: round(v, 4) for k, v in by_module.items()},
        "by_model": {k: round(v, 4) for k, v in by_model.items()},
        "calls": calls,
        "cache_hits": hits,
    }


def project_total() -> float:
    """Cumulative spend across the whole cost log."""
    path = Path(_settings.cost_log_path)
    if not path.exists():
        return 0.0
    total = 0.0
    with path.open() as f:
        for line in f:
            try:
                total += json.loads(line).get("cost_usd", 0.0)
            except json.JSONDecodeError:
                continue
    return round(total, 4)
