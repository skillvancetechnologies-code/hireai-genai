"""Smoke tests for G4's W1 infrastructure.

These run without hitting Ollama - we monkeypatch the network call.
Goal: prove the wrapper, cache, cost log, and prompt library all
work together. Run with:

    pytest app/tests/ -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import cache, llm
from app.core.cost import estimate_cost, project_total, summarize_day
from app.core.prompts import list_prompts, load_prompt, reload_library


# ---- prompt library ----------------------------------------------------

def test_library_has_three_starter_prompts():
    reload_library()
    prompts = list_prompts()
    assert {"parser_main", "intent_classifier", "explanation"} <= set(prompts)


def test_parser_prompt_renders():
    p = load_prompt("parser_main")
    rendered = p.format(resume_text="John Doe, Python dev, 5y exp.")
    assert "John Doe" in rendered
    assert p.version >= 1
    assert p.json_mode is True


def test_intent_prompt_renders():
    p = load_prompt("intent_classifier")
    rendered = p.format(query="top 5 Python devs")
    assert "top 5 Python devs" in rendered


def test_explanation_prompt_renders():
    p = load_prompt("explanation")
    rendered = p.format(
        name="A", job_title="B", score=80, label="Good Fit",
        skills_match=90, matched_count=9, required_count=10,
        candidate_exp=5, required_exp=3, project_score=85,
        matched_skills="Python, SQL", missing_skills="Kafka",
    )
    assert "Good Fit" in rendered
    assert "Kafka" in rendered


# ---- cache -------------------------------------------------------------

def test_cache_set_and_get_roundtrip():
    cache.cache_set("test:key1", "hello", ttl=60)
    assert cache.cache_get("test:key1") == "hello"


def test_cache_invalidate():
    cache.cache_set("test:key2", "value", ttl=60)
    cache.cache_invalidate("test:key2")
    assert cache.cache_get("test:key2") is None


def test_cache_miss_returns_none():
    assert cache.cache_get("test:nonexistent:xyz") is None


# ---- llm wrapper (mocked network) --------------------------------------

def test_llm_call_caches(monkeypatch, tmp_path):
    """First call hits the (fake) API; second call hits the cache."""
    calls = {"count": 0}

    def fake_ollama(model, prompt, temperature, json_mode):
        calls["count"] += 1
        return ("hello world", 5, 2)

    monkeypatch.setattr(llm, "_call_ollama", fake_ollama)
    # Use a unique prompt so cache from prior runs doesn't interfere.
    prompt = f"unit-test-{tmp_path.name}"

    r1 = llm.llm_call(prompt, model="gemma3:4b", cache=True, module="test")
    r2 = llm.llm_call(prompt, model="gemma3:4b", cache=True, module="test")

    assert r1 == r2 == "hello world"
    assert calls["count"] == 1, "Second call should have hit cache, not API."


def test_llm_call_cache_disabled(monkeypatch):
    calls = {"count": 0}

    def fake_ollama(model, prompt, temperature, json_mode):
        calls["count"] += 1
        return ("response", 1, 1)

    monkeypatch.setattr(llm, "_call_ollama", fake_ollama)
    llm.llm_call("no-cache-test", model="gemma3:4b", cache=False, module="test")
    llm.llm_call("no-cache-test", model="gemma3:4b", cache=False, module="test")
    assert calls["count"] == 2


def test_llm_call_json_parses(monkeypatch):
    monkeypatch.setattr(
        llm, "_call_ollama",
        lambda model, prompt, temperature, json_mode: ('{"ok": true, "n": 3}', 4, 2),
    )
    data = llm.llm_call_json("test-json", model="gemma3:4b", module="test", cache=False)
    assert data == {"ok": True, "n": 3}


def test_llm_call_json_raises_on_invalid(monkeypatch):
    monkeypatch.setattr(
        llm, "_call_ollama",
        lambda *a, **k: ("not valid json {", 1, 1),
    )
    with pytest.raises(llm.LLMError):
        llm.llm_call_json("bad-json", model="gemma3:4b", module="test", cache=False)


def test_llm_call_custom_cache_key(monkeypatch):
    """Verifies explicit cache_key is honored (used by explain module)."""
    calls = {"count": 0}

    def fake_ollama(model, prompt, temperature, json_mode):
        calls["count"] += 1
        return (f"resp-{calls['count']}", 1, 1)

    monkeypatch.setattr(llm, "_call_ollama", fake_ollama)
    key = "explain:CAND0001:JOB0001:v1"
    cache.cache_invalidate(key)

    r1 = llm.llm_call("prompt A", cache_key=key, module="explain")
    r2 = llm.llm_call("prompt B (different but same key)", cache_key=key, module="explain")
    assert r1 == r2, "Same cache key should return same cached value regardless of prompt."
    assert calls["count"] == 1


# ---- cost --------------------------------------------------------------

def test_estimate_cost_known_model():
    # Local Ollama models cost $0
    assert estimate_cost("gemma3:4b", 1_000_000, 1_000_000) == 0.0


def test_estimate_cost_unknown_model_returns_zero():
    assert estimate_cost("unknown-model", 1000, 1000) == 0.0


def test_cost_logged_per_call(monkeypatch, tmp_path):
    log_file = tmp_path / "cost.jsonl"
    monkeypatch.setattr("app.core.cost._settings.cost_log_path", str(log_file))
    monkeypatch.setattr(
        llm, "_call_ollama",
        lambda *a, **k: ("ok", 10, 5),
    )
    llm.llm_call("cost-test", model="gemma3:4b", cache=False, module="test")
    assert log_file.exists()
    lines = log_file.read_text().strip().split("\n")
    record = json.loads(lines[-1])
    assert record["module"] == "test"
    assert record["model"] == "gemma3:4b"
    assert record["prompt_tokens"] == 10
    assert record["completion_tokens"] == 5
    assert record["cost_usd"] == 0.0  # local model, no cost


def test_summarize_day_empty_returns_zero(monkeypatch, tmp_path):
    monkeypatch.setattr("app.core.cost._settings.cost_log_path", str(tmp_path / "empty.jsonl"))
    s = summarize_day("2099-01-01")
    assert s["total_usd"] == 0.0
    assert s["calls"] == 0
