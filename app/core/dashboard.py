"""PM-facing cost & eval dashboard (G4, Week 4).

Read-only JSON endpoints the PM (or a thin frontend) can poll:

    GET /dashboard/costs   — today + last-N-days spend, project total vs cap
    GET /dashboard/evals   — latest accuracy per module + regression status

Data sources: data/cost_log.jsonl (written by app.core.cost on every
LLM call) and data/eval_results/ (written by the nightly eval runner).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.core.cost import project_total, summarize_day
from app.core.eval import EVAL_RESULTS_DIR, detect_regression

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

MODULES = ["parser", "copilot", "explain"]


@router.get("/costs")
def cost_dashboard(days: int = Query(default=7, ge=1, le=60)) -> dict:
    """Spend rollup for the PM: today, a daily trend, and budget status."""
    settings = get_settings()
    today = datetime.now(timezone.utc).date()

    daily = []
    for offset in range(days):
        date_iso = (today - timedelta(days=offset)).isoformat()
        s = summarize_day(date_iso)
        daily.append(
            {
                "date": date_iso,
                "total_usd": s["total_usd"],
                "calls": s["calls"],
                "cache_hits": s["cache_hits"],
                "by_module": s["by_module"],
            }
        )

    total = project_total()
    cap = settings.project_spend_cap_usd
    return {
        "today": daily[0],
        "daily": daily,
        "project_total_usd": total,
        "project_cap_usd": cap,
        "budget_used_pct": round(100 * total / cap, 2) if cap else 0.0,
        "on_track": total < cap,
        "note": "Local Ollama models cost $0; call/cache volumes are the metrics that matter.",
    }


@router.get("/evals")
def eval_dashboard() -> dict:
    """Latest nightly eval accuracy per module plus regression flags."""
    modules = {}
    for mod in MODULES:
        latest_file = EVAL_RESULTS_DIR / f"{mod}_latest.json"
        if latest_file.exists():
            latest = json.loads(latest_file.read_text())
            modules[mod] = {
                "accuracy": latest.get("accuracy"),
                "cases": latest.get("count", 0),
                "regression": detect_regression(mod),
            }
        else:
            modules[mod] = {"accuracy": None, "cases": 0, "regression": {"regression": False, "reason": "no results yet"}}
    return {"modules": modules}
