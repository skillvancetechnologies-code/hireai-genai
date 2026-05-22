"""Nightly automation: run all evals, post a cost summary, and alert
on regressions. Designed to run from cron — see README W2 section.

    0 6 * * * cd /path/to/hireai-genai && .venv/bin/python scripts/nightly.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.core.cost import project_total, summarize_day  # noqa: E402
from app.core.eval import detect_regression, run_eval  # noqa: E402
from app.core.slack import post_to_slack  # noqa: E402
from scripts.cost_summary import format_slack as format_cost_slack  # noqa: E402

MODULES = ["parser", "copilot", "explain"]


def _format_eval_summary(eval_results: dict) -> str:
    lines = ["*GenAI nightly eval results*"]
    for mod, result in eval_results.items():
        acc = result.get("accuracy")
        acc_str = f"{acc:.1%}" if acc is not None else "skipped"
        lines.append(f"- {mod}: {acc_str} ({result['count']} cases)")
    return "\n".join(lines)


def _format_regression_alert(mod: str, reg: dict, owner: str) -> str:
    return (
        f":rotating_light: *Regression in {mod}* (owner: {owner})\n"
        f"Current: {reg['current']:.1%}, 7d avg: {reg['baseline_7d_avg']:.1%}, "
        f"delta: {reg['delta_pts']:+.2f}pts"
    )


def main() -> int:
    settings = get_settings()
    owners = settings.module_owners

    # 1. Evals
    eval_results = {}
    regressions = []
    for mod in MODULES:
        result = run_eval(mod)
        eval_results[mod] = result
        reg = detect_regression(mod)
        if reg.get("regression"):
            regressions.append((mod, reg))

    post_to_slack(_format_eval_summary(eval_results))

    # 2. Cost summary (yesterday UTC)
    summary = summarize_day()
    cost_text = format_cost_slack(summary, project_total(), settings.project_spend_cap_usd)
    post_to_slack(cost_text)

    # 3. Regression alerts (separate message per regressed module)
    for mod, reg in regressions:
        owner = owners.get(mod, "unknown")
        post_to_slack(_format_regression_alert(mod, reg, owner))

    print(f"Nightly done. Evals: {len(eval_results)}, regressions: {len(regressions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
