"""Print yesterday's (or a given date's) LLM spend.

Usage:
    python scripts/cost_summary.py              # yesterday UTC
    python scripts/cost_summary.py --date 2025-05-18
    python scripts/cost_summary.py --slack      # print Slack-ready message
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.cost import project_total, summarize_day  # noqa: E402


def format_slack(summary: dict, total: float, cap: float) -> str:
    lines = [
        f"*GenAI cost summary - {summary['date']}*",
        f"Total: ${summary['total_usd']:.4f} ({summary['calls']} calls, "
        f"{summary['cache_hits']} cache hits)",
    ]
    if summary["by_module"]:
        by_mod = ", ".join(f"{k} ${v:.4f}" for k, v in summary["by_module"].items())
        lines.append(f"By module: {by_mod}")
    if summary["by_model"]:
        by_mdl = ", ".join(f"{k} ${v:.4f}" for k, v in summary["by_model"].items())
        lines.append(f"By model: {by_mdl}")
    lines.append(f"Project total: ${total:.4f} / ${cap:.0f} cap")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="ISO date (UTC). Default: yesterday.")
    p.add_argument("--slack", action="store_true", help="Print Slack-formatted message.")
    args = p.parse_args()

    summary = summarize_day(args.date)
    total = project_total()
    from app.core.config import get_settings
    cap = get_settings().project_spend_cap_usd

    if args.slack:
        print(format_slack(summary, total, cap))
    else:
        import json
        print(json.dumps({**summary, "project_total_usd": total, "project_cap_usd": cap}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
