"""Nightly eval runner.

Usage:
    python scripts/run_evals.py --module parser
    python scripts/run_evals.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `app` importable when run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.eval import detect_regression, run_eval  # noqa: E402

MODULES = ["parser", "copilot", "explain"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", choices=MODULES, help="Run one module's eval.")
    parser.add_argument("--all", action="store_true", help="Run all modules.")
    args = parser.parse_args()

    targets = MODULES if args.all else ([args.module] if args.module else [])
    if not targets:
        parser.error("Pass --module <name> or --all")

    summary = {}
    for mod in targets:
        result = run_eval(mod)
        regression = detect_regression(mod)
        summary[mod] = {**result, "regression": regression}
        acc = result.get("accuracy")
        acc_str = f"{acc:.1%}" if acc is not None else "n/a (no runner registered)"
        flag = " ⚠️ REGRESSION" if regression.get("regression") else ""
        print(f"{mod:>8}: {acc_str} ({result['count']} cases){flag}")

    print("\n--- JSON ---")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
