"""Eval framework skeleton.

Reads gold cases from data/eval_sets/<module>.json and produces a
scored result file at data/eval_results/<module>_latest.json plus a
historical snapshot data/eval_results/<module>_<date>.json.

Each module defines its own scorer (parser = field accuracy,
copilot = top-K recall, explain = rubric pass rate). Scorers are
registered in `SCORERS` below. Module-specific runners (the actual
function that maps `input -> actual`) live in their module folders
and are wired in W2.

Run via `python scripts/run_evals.py --module parser`.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

EVAL_SETS_DIR = Path("data/eval_sets")
EVAL_RESULTS_DIR = Path("data/eval_results")

Scorer = Callable[[dict, Any], float]  # (expected, actual) -> [0,1]
Runner = Callable[[Any], Any]          # input -> actual output


# ---- default scorers ---------------------------------------------------

def field_accuracy(expected: dict, actual: dict) -> float:
    """Parser scorer. Grades ONLY the keys present in `expected`.

    Contract (locked W2): any field the runner returns but the eval case
    does not specify (e.g. projects, summary, parse_confidence) is
    ignored — it is neither rewarded nor penalized. This lets G1 evolve
    the parser schema without invalidating the gold set.

    - list fields: case-insensitive SUBSET match (expected ⊆ actual)
    - scalar fields: exact equality
    """
    if not isinstance(actual, dict):
        return 0.0
    total = len(expected)
    if total == 0:
        return 1.0
    matched = 0
    for k, v in expected.items():
        a = actual.get(k)
        if isinstance(v, list) and isinstance(a, list):
            if set(map(str.lower, map(str, v))) <= set(map(str.lower, map(str, a))):
                matched += 1
        elif a == v:
            matched += 1
    return matched / total


def recall_at_k(expected: dict, actual: Any) -> float:
    """Used by copilot: |gold ∩ predicted_top_k| / |gold|."""
    gold = set(expected.get("candidate_ids", []))
    if not gold:
        return 1.0
    if not isinstance(actual, list):
        return 0.0
    pred = set(actual[: len(gold)])
    return len(gold & pred) / len(gold)


def rubric_pass(expected: dict, actual: Any) -> float:
    """Used by explain: average of (factual, clear, unbiased) on 1-3 scale,
    pass if >= 2.5. For W1 this is a stub - replaced when G3 ships rubric."""
    if not isinstance(actual, dict):
        return 0.0
    scores = [actual.get("factual", 0), actual.get("clear", 0), actual.get("unbiased", 0)]
    avg = sum(scores) / 3
    return 1.0 if avg >= 2.5 else avg / 3


SCORERS: dict[str, Scorer] = {
    "parser": field_accuracy,
    "copilot": recall_at_k,
    "explain": rubric_pass,
}

# Runners registered by modules when their actual logic exists.
# In W1 these are placeholders; W2 wires real implementations.
RUNNERS: dict[str, Runner] = {}

# Reasons a runner was deliberately not registered (used to surface a
# clean "skipped" message in run_eval rather than crashing).
SKIPPED_RUNNERS: dict[str, str] = {}


def register_runner(module: str, fn: Runner) -> None:
    RUNNERS[module] = fn
    SKIPPED_RUNNERS.pop(module, None)


# ---- W2: parser runner registration ------------------------------------
#
# The parser eval calls G1's module the SAME way production does:
# hand it a resume FILE, let G1 extract text + run the LLM. We do not
# re-implement PDF extraction here — that would duplicate G1's code.

PARSER_RESUMES_DIR = EVAL_SETS_DIR / "parser_resumes"


def _register_parser_runner() -> None:
    """Try to wire G1's parser. If it isn't importable or PDFs aren't
    on disk yet, leave RUNNERS["parser"] unset and record why."""
    try:
        from app.modules.parser.service import parse_resume_file  # type: ignore
    except Exception as e:
        SKIPPED_RUNNERS["parser"] = f"G1 parser not importable: {e}"
        return

    if not PARSER_RESUMES_DIR.exists() or not any(PARSER_RESUMES_DIR.iterdir()):
        SKIPPED_RUNNERS["parser"] = (
            f"no resume PDFs in {PARSER_RESUMES_DIR} - G1 must drop them there"
        )
        return

    def _runner(filename: str) -> dict:
        path = PARSER_RESUMES_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"resume not found: {path}")
        return parse_resume_file(str(path))

    RUNNERS["parser"] = _runner


_register_parser_runner()


# ---- main runner -------------------------------------------------------

def run_eval(module: str) -> dict:
    if module not in SCORERS:
        raise ValueError(f"No scorer registered for module '{module}'")

    eval_file = EVAL_SETS_DIR / f"{module}.json"
    if not eval_file.exists():
        log.warning("Eval set %s not found - skipping.", eval_file)
        return {"module": module, "accuracy": None, "count": 0, "results": []}

    cases = json.loads(eval_file.read_text())
    scorer = SCORERS[module]
    runner = RUNNERS.get(module)
    skip_reason = SKIPPED_RUNNERS.get(module)

    if runner is None and skip_reason:
        log.warning("Eval runner skipped for %s: %s", module, skip_reason)

    results = []
    for case in cases:
        case_id = case.get("id", "?")
        expected = case.get("expected", {})
        if runner is None:
            note = skip_reason or "no runner registered"
            results.append({"id": case_id, "score": None, "note": note})
            continue
        try:
            actual = runner(case["input"])
            score = scorer(expected, actual)
            results.append({"id": case_id, "score": round(score, 3)})
        except Exception as e:
            log.exception("Case %s failed: %s", case_id, e)
            results.append({"id": case_id, "score": 0.0, "error": str(e)})

    scored = [r["score"] for r in results if r.get("score") is not None]
    accuracy = round(sum(scored) / len(scored), 3) if scored else None

    summary = {
        "module": module,
        "accuracy": accuracy,
        "count": len(results),
        "results": results,
    }

    EVAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (EVAL_RESULTS_DIR / f"{module}_latest.json").write_text(json.dumps(summary, indent=2))
    (EVAL_RESULTS_DIR / f"{module}_{date.today().isoformat()}.json").write_text(
        json.dumps(summary, indent=2)
    )
    return summary


def detect_regression(module: str, threshold_pts: float = 3.0) -> dict:
    """Compare today's accuracy vs the prior 7-day average. Used by
    the nightly Slack report to flag regressions."""
    history_dir = EVAL_RESULTS_DIR
    if not history_dir.exists():
        return {"module": module, "regression": False, "reason": "no history"}
    files = sorted(history_dir.glob(f"{module}_2*.json"))
    if len(files) < 2:
        return {"module": module, "regression": False, "reason": "insufficient history"}
    history_scores = []
    for f in files[-8:-1]:
        data = json.loads(f.read_text())
        if data.get("accuracy") is not None:
            history_scores.append(data["accuracy"])
    latest = json.loads((history_dir / f"{module}_latest.json").read_text())
    if latest.get("accuracy") is None or not history_scores:
        return {"module": module, "regression": False, "reason": "no scores"}
    avg = sum(history_scores) / len(history_scores)
    delta_pts = (latest["accuracy"] - avg) * 100
    return {
        "module": module,
        "regression": delta_pts < -threshold_pts,
        "delta_pts": round(delta_pts, 2),
        "current": latest["accuracy"],
        "baseline_7d_avg": round(avg, 3),
    }
