"""W3 integration tests: copilot and explain endpoints + eval wiring.

All tests are offline — LLM calls are monkeypatched so no Ollama needed.
Run with:  pytest app/tests/test_w3.py -v
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core import eval as eval_mod
from app.core.eval import copilot_intent_accuracy, explain_response_valid, run_eval

client = TestClient(app)


# ---- app startup -------------------------------------------------------

def test_all_routers_registered():
    routes = {r.path for r in app.routes}
    assert "/parse" in routes
    assert "/copilot" in routes
    assert "/explain/" in routes


# ---- copilot endpoint --------------------------------------------------

def test_copilot_empty_query_returns_400():
    resp = client.post("/copilot", json={"query": ""})
    assert resp.status_code == 400


def test_copilot_returns_valid_shape(monkeypatch):
    """Copilot with a rule-based fallback (no Ollama needed)."""
    monkeypatch.setattr(
        "app.modules.copilot.intent_parser.parse_intent_with_llm",
        lambda q: {"type": "filter", "job_id": None, "skills_required": ["Python"],
                   "min_experience": None, "label_filter": None,
                   "status_filter": None, "top_k": 5, "free_text": ""},
    )
    resp = client.post("/copilot", json={"query": "top 5 Python developers"})
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        body = resp.json()
        assert "query_interpreted" in body
        assert "candidates" in body
        assert "summary" in body
        assert isinstance(body["candidates"], list)


def test_copilot_no_match_returns_404(monkeypatch):
    """Intent with impossible filters should return 404, not crash."""
    monkeypatch.setattr(
        "app.modules.copilot.intent_parser.parse_intent_with_llm",
        lambda q: {"type": "filter", "job_id": 99999, "skills_required": [],
                   "min_experience": None, "label_filter": None,
                   "status_filter": None, "top_k": 10, "free_text": ""},
    )
    resp = client.post("/copilot", json={"query": "job 99999"})
    assert resp.status_code == 404


# ---- explain endpoint --------------------------------------------------

def test_explain_known_candidate(monkeypatch):
    """Known mock candidate returns a structured response."""
    monkeypatch.setattr(
        "app.modules.explain.generator.llm_call",
        lambda prompt, **kwargs: (
            "Arjun Sharma scores 74/100 for Backend Engineer. "
            "Matched skills include Python, FastAPI, and Docker. "
            "Kafka and Airflow are not present in the candidate profile."
        ),
    )
    resp = client.post("/explain/", json={"candidate_id": "C1", "job_id": "J1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["candidate_id"] == "C1"
    assert body["job_id"] == "J1"
    assert len(body["explanation_text"]) > 0
    assert isinstance(body["top_strengths"], list)
    assert isinstance(body["top_gaps"], list)


def test_explain_unknown_candidate_returns_not_found():
    resp = client.post("/explain/", json={"candidate_id": "DOESNOTEXIST", "job_id": "J1"})
    assert resp.status_code == 200
    body = resp.json()
    assert "not found" in body["explanation_text"].lower()


def test_explain_llm_receives_module_kwarg(monkeypatch):
    """Verify G3's generator passes module= to llm_call (architecture rule)."""
    received_kwargs = {}

    def capture_llm(prompt, **kwargs):
        received_kwargs.update(kwargs)
        return "Score is 74. Matched Python, FastAPI, Docker. Missing Kafka, Airflow. Projects are relevant."

    monkeypatch.setattr("app.modules.explain.generator.llm_call", capture_llm)
    client.post("/explain/", json={"candidate_id": "C1", "job_id": "J1"})
    assert "module" in received_kwargs, "llm_call must receive module= kwarg"
    assert received_kwargs["module"] == "explain"


# ---- copilot scorer ----------------------------------------------------

def test_copilot_intent_scorer_full_match():
    expected = {"type": "filter", "skills_required": ["Python"], "top_k": 5}
    actual = {"type": "filter", "skills_required": ["Python", "SQL"], "top_k": 5,
              "job_id": None, "label_filter": None}
    assert copilot_intent_accuracy(expected, actual) == 1.0


def test_copilot_intent_scorer_partial_match():
    expected = {"type": "filter", "skills_required": ["Python"], "top_k": 5}
    actual = {"type": "filter", "skills_required": ["Python"], "top_k": 10}
    score = copilot_intent_accuracy(expected, actual)
    assert 0.0 < score < 1.0


def test_copilot_intent_scorer_no_match():
    expected = {"type": "filter", "top_k": 5}
    assert copilot_intent_accuracy(expected, "not a dict") == 0.0


# ---- explain scorer ----------------------------------------------------

def test_explain_scorer_valid_response():
    actual = {
        "explanation_text": "Candidate scores 74 for the role. Matched Python, FastAPI. Missing Kafka, Airflow.",
        "top_strengths": ["Python", "FastAPI"],
        "top_gaps": ["Kafka", "Airflow"],
    }
    assert explain_response_valid({}, actual) == 1.0


def test_explain_scorer_not_found_response():
    actual = {
        "explanation_text": "Candidate not found",
        "top_strengths": [],
        "top_gaps": [],
    }
    assert explain_response_valid({}, actual) == 0.0


def test_explain_scorer_short_explanation():
    actual = {
        "explanation_text": "Short.",
        "top_strengths": ["Python"],
        "top_gaps": ["Kafka"],
    }
    assert explain_response_valid({}, actual) == 0.0


# ---- eval runner wiring ------------------------------------------------

def test_copilot_runner_registered():
    assert "copilot" in eval_mod.RUNNERS, "copilot runner must be registered in eval.py"


def test_explain_runner_registered():
    assert "explain" in eval_mod.RUNNERS, "explain runner must be registered in eval.py"


def test_copilot_eval_set_has_correct_format():
    cases = json.loads(Path("data/eval_sets/copilot.json").read_text())
    assert len(cases) >= 5
    for c in cases:
        assert "id" in c
        assert "input" in c
        assert isinstance(c["input"], str)
        assert "expected" in c


def test_explain_eval_set_has_correct_format():
    cases = json.loads(Path("data/eval_sets/explain.json").read_text())
    assert len(cases) >= 2
    for c in cases:
        assert "id" in c
        assert "input" in c
        assert isinstance(c["input"], dict)
        assert "candidate_id" in c["input"]
        assert "job_id" in c["input"]


def test_copilot_eval_runner_with_mock(monkeypatch, tmp_path):
    """run_eval wires through the copilot runner and produces an accuracy."""
    cases = [
        {"id": "c1", "input": "Show Python developers",
         "expected": {"type": "filter", "skills_required": ["Python"], "top_k": 10}},
    ]
    eval_file = tmp_path / "copilot.json"
    eval_file.write_text(json.dumps(cases))
    results_dir = tmp_path / "results"

    monkeypatch.setattr(eval_mod, "EVAL_SETS_DIR", tmp_path)
    monkeypatch.setattr(eval_mod, "EVAL_RESULTS_DIR", results_dir)

    from app.modules.copilot.schemas import QueryIntent
    fake_intent = QueryIntent(
        type="filter", skills_required=["Python"], top_k=10
    )
    eval_mod.RUNNERS["copilot"] = lambda q: fake_intent.model_dump()
    eval_mod.SKIPPED_RUNNERS.pop("copilot", None)
    try:
        summary = run_eval("copilot")
    finally:
        eval_mod.RUNNERS.pop("copilot", None)

    assert summary["accuracy"] == 1.0
    assert summary["count"] == 1
