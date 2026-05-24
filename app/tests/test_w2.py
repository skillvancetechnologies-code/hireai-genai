"""W2 additions: parser eval scoring, format reconciliation, slack
no-op, regression detection, budget guard, module-required."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import eval as eval_mod
from app.core import llm, slack
from app.core.eval import detect_regression, field_accuracy, run_eval


# ---- format reconciliation --------------------------------------------

def test_parser_json_canonical_shape():
    cases = json.loads(Path("data/eval_sets/parser.json").read_text())
    assert len(cases) == 10
    for c in cases:
        assert set(c.keys()) >= {"id", "input", "expected"}
        # `input` is now a filename string, not a {resume_text:...} dict
        assert isinstance(c["input"], str)
        assert c["input"].endswith(".pdf")
        # divergent W1 shape must be gone
        assert "resume_text" not in c.get("input", "") if isinstance(c["input"], str) else True
        assert "expected_output" not in c


# ---- parser scoring with a mock runner --------------------------------

def test_parser_eval_with_mocked_runner(monkeypatch, tmp_path):
    """Wire a fake runner returning a known parsed dict; the scorer
    should grade only the keys in `expected` (subset list match)."""
    expected = {
        "name": "Test",
        "email": "t@example.com",
        "skills": ["Python", "SQL"],
        "experience_years": 4,
    }
    # extras must NOT be penalized
    actual = {**expected, "skills": ["python", "sql", "extra"],
              "projects": ["ignored"], "summary": "ignored"}
    assert field_accuracy(expected, actual) == 1.0

    # one wrong scalar => 3/4
    actual_partial = {**actual, "experience_years": 7}
    assert field_accuracy(expected, actual_partial) == pytest.approx(0.75)


def test_parser_runner_invokes_registered_fn(monkeypatch, tmp_path):
    """run_eval should call RUNNERS["parser"] and produce an accuracy."""
    cases = [{"id": "p1", "input": "x.pdf",
              "expected": {"name": "A", "skills": ["py"]}}]
    eval_file = tmp_path / "parser.json"
    eval_file.write_text(json.dumps(cases))
    results_dir = tmp_path / "results"

    monkeypatch.setattr(eval_mod, "EVAL_SETS_DIR", tmp_path)
    monkeypatch.setattr(eval_mod, "EVAL_RESULTS_DIR", results_dir)

    eval_mod.RUNNERS["parser"] = lambda fname: {"name": "A", "skills": ["PY"]}
    eval_mod.SKIPPED_RUNNERS.pop("parser", None)
    try:
        summary = run_eval("parser")
    finally:
        eval_mod.RUNNERS.pop("parser", None)

    assert summary["accuracy"] == 1.0
    assert summary["count"] == 1


def test_parser_runner_skips_cleanly_when_unregistered(monkeypatch, tmp_path):
    cases = [{"id": "p1", "input": "missing.pdf", "expected": {"name": "A"}}]
    eval_file = tmp_path / "parser.json"
    eval_file.write_text(json.dumps(cases))
    monkeypatch.setattr(eval_mod, "EVAL_SETS_DIR", tmp_path)
    monkeypatch.setattr(eval_mod, "EVAL_RESULTS_DIR", tmp_path / "results")

    eval_mod.RUNNERS.pop("parser", None)
    eval_mod.SKIPPED_RUNNERS["parser"] = "test reason"
    try:
        summary = run_eval("parser")
    finally:
        eval_mod.SKIPPED_RUNNERS.pop("parser", None)

    assert summary["accuracy"] is None
    assert summary["results"][0]["note"] == "test reason"


# ---- slack no-op ------------------------------------------------------

def test_slack_noop_when_webhook_unset(monkeypatch, caplog):
    monkeypatch.setattr(slack.get_settings().__class__, "slack_webhook_url", "",
                        raising=False)
    # ensure the live setting reads empty
    s = slack.get_settings()
    object.__setattr__(s, "slack_webhook_url", "")
    with caplog.at_level("INFO"):
        ok = slack.post_to_slack("hello world")
    assert ok is False
    assert any("hello world" in r.message for r in caplog.records)


# ---- regression detection --------------------------------------------

def test_regression_detected_when_drop_exceeds_threshold(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_mod, "EVAL_RESULTS_DIR", tmp_path)
    # 7 days of ~90%
    for d in range(1, 8):
        (tmp_path / f"parser_2025-01-0{d}.json").write_text(
            json.dumps({"module": "parser", "accuracy": 0.90})
        )
    # latest dropped to 0.80 (10pt drop)
    (tmp_path / "parser_latest.json").write_text(
        json.dumps({"module": "parser", "accuracy": 0.80})
    )
    r = detect_regression("parser")
    assert r["regression"] is True
    assert r["delta_pts"] < -3


def test_no_regression_when_stable(monkeypatch, tmp_path):
    monkeypatch.setattr(eval_mod, "EVAL_RESULTS_DIR", tmp_path)
    for d in range(1, 8):
        (tmp_path / f"parser_2025-01-0{d}.json").write_text(
            json.dumps({"module": "parser", "accuracy": 0.90})
        )
    (tmp_path / "parser_latest.json").write_text(
        json.dumps({"module": "parser", "accuracy": 0.89})
    )
    r = detect_regression("parser")
    assert r["regression"] is False


# ---- budget guard ----------------------------------------------------

def test_budget_exceeded_blocks_openai_call(monkeypatch):
    monkeypatch.setattr(llm, "project_total", lambda: 999.0)
    monkeypatch.setattr(llm._settings, "project_spend_cap_usd", 200.0)
    # If we reach _call_ollama, the test fails.
    monkeypatch.setattr(llm, "_call_ollama",
                        lambda *a, **k: pytest.fail("should not be called"))
    with pytest.raises(llm.BudgetExceeded):
        llm.llm_call("anything", model="gemma3:4b",
                     module="test", cache=False)


def test_budget_guard_allows_cache_hits(monkeypatch):
    from app.core import cache
    cache.cache_set("budget:test:key", "cached-value", ttl=60)
    monkeypatch.setattr(llm, "project_total", lambda: 999.0)
    monkeypatch.setattr(llm._settings, "project_spend_cap_usd", 200.0)
    monkeypatch.setattr(llm, "_call_ollama",
                        lambda *a, **k: pytest.fail("should not hit API"))
    out = llm.llm_call("ignored", model="gemma3:4b", module="test",
                       cache=True, cache_key="budget:test:key")
    assert out == "cached-value"


# ---- module is required ----------------------------------------------

def test_llm_call_requires_module():
    with pytest.raises(TypeError):
        llm.llm_call("hi", model="gpt-4o-mini")  # type: ignore[call-arg]


def test_llm_call_json_requires_module():
    with pytest.raises(TypeError):
        llm.llm_call_json("hi", model="gpt-4o-mini")  # type: ignore[call-arg]
