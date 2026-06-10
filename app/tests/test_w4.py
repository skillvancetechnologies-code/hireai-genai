"""W4 tests for G4's deliverables:

1. Local fallback model (Ollama-only equivalent of the doc's Gemini fallback)
2. Prompt library: 15+ versioned prompts, all renderable
3. PM dashboard endpoints (/dashboard/costs, /dashboard/evals)

Run with: pytest app/tests/test_w4.py -v
"""
from __future__ import annotations

import string

import pytest
from fastapi.testclient import TestClient

from app.core import cache, llm
from app.core.prompts import _load_library, list_prompts, load_prompt, reload_library
from app.main import app


# ---- 1. fallback chain: Ollama -> Gemini -> local ------------------------

def _unique_prompt(tmp_path) -> str:
    return f"w4-fallback-test-{tmp_path.name}"


def _no_gemini(monkeypatch):
    monkeypatch.setattr(llm._settings, "gemini_api_key", "")


def _with_gemini(monkeypatch):
    monkeypatch.setattr(llm._settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(llm._settings, "gemini_fallback_model", "gemini-2.5-flash")


def test_gemini_used_when_primary_fails(monkeypatch, tmp_path):
    ollama_calls, gemini_calls = [], []

    def fake_ollama(model, prompt, temperature, json_mode):
        ollama_calls.append(model)
        raise ConnectionError("primary model down")

    def fake_gemini(prompt, temperature, json_mode):
        gemini_calls.append(prompt)
        return ("gemini says hi", 5, 2)

    monkeypatch.setattr(llm, "_call_ollama", fake_ollama)
    monkeypatch.setattr(llm, "_call_gemini", fake_gemini)
    monkeypatch.setattr(llm._settings, "fallback_enabled", True)
    _with_gemini(monkeypatch)

    result = llm.llm_call(
        _unique_prompt(tmp_path), model="gemma3:4b", cache=False, module="test"
    )
    assert result == "gemini says hi"
    assert ollama_calls == ["gemma3:4b"], "local fallback must not run when Gemini succeeds"
    assert len(gemini_calls) == 1


def test_local_fallback_used_when_no_gemini_key(monkeypatch, tmp_path):
    calls = []

    def fake_ollama(model, prompt, temperature, json_mode):
        calls.append(model)
        if model == "gemma3:4b":
            raise ConnectionError("primary model down")
        return ("fallback says hi", 5, 2)

    monkeypatch.setattr(llm, "_call_ollama", fake_ollama)
    monkeypatch.setattr(llm._settings, "fallback_enabled", True)
    monkeypatch.setattr(llm._settings, "fallback_model", "mistral:latest")
    _no_gemini(monkeypatch)

    result = llm.llm_call(
        _unique_prompt(tmp_path) + "-nokey", model="gemma3:4b", cache=False, module="test"
    )
    assert result == "fallback says hi"
    assert calls == ["gemma3:4b", "mistral:latest"]


def test_local_fallback_used_when_gemini_also_fails(monkeypatch, tmp_path):
    calls = []

    def fake_ollama(model, prompt, temperature, json_mode):
        calls.append(model)
        if model == "gemma3:4b":
            raise ConnectionError("primary model down")
        return ("local rescue", 1, 1)

    def fake_gemini(prompt, temperature, json_mode):
        raise ConnectionError("gemini 429")

    monkeypatch.setattr(llm, "_call_ollama", fake_ollama)
    monkeypatch.setattr(llm, "_call_gemini", fake_gemini)
    monkeypatch.setattr(llm._settings, "fallback_enabled", True)
    monkeypatch.setattr(llm._settings, "fallback_model", "mistral:latest")
    _with_gemini(monkeypatch)

    result = llm.llm_call(
        _unique_prompt(tmp_path) + "-geminifail", model="gemma3:4b",
        cache=False, module="test",
    )
    assert result == "local rescue"
    assert calls == ["gemma3:4b", "mistral:latest"]


def test_fallback_disabled_raises(monkeypatch, tmp_path):
    def fake_ollama(model, prompt, temperature, json_mode):
        raise ConnectionError("down")

    monkeypatch.setattr(llm, "_call_ollama", fake_ollama)
    monkeypatch.setattr(llm._settings, "fallback_enabled", False)
    _with_gemini(monkeypatch)  # even with a key, disabled means disabled

    with pytest.raises(llm.LLMError):
        llm.llm_call(
            _unique_prompt(tmp_path) + "-disabled", model="gemma3:4b",
            cache=False, module="test",
        )


def test_all_backends_failing_raises_with_context(monkeypatch, tmp_path):
    def fake_ollama(model, prompt, temperature, json_mode):
        raise ConnectionError(f"{model} down")

    def fake_gemini(prompt, temperature, json_mode):
        raise ConnectionError("gemini down")

    monkeypatch.setattr(llm, "_call_ollama", fake_ollama)
    monkeypatch.setattr(llm, "_call_gemini", fake_gemini)
    monkeypatch.setattr(llm._settings, "fallback_enabled", True)
    monkeypatch.setattr(llm._settings, "fallback_model", "mistral:latest")
    _with_gemini(monkeypatch)

    with pytest.raises(llm.LLMError) as exc:
        llm.llm_call(
            _unique_prompt(tmp_path) + "-allfail", model="gemma3:4b",
            cache=False, module="test",
        )
    msg = str(exc.value)
    assert "primary" in msg and "gemini" in msg and "local fallback" in msg


def test_gemini_result_is_cached_under_original_key(monkeypatch, tmp_path):
    """A fallback response must still satisfy later cache hits for the
    original (primary-model) cache key."""
    gemini_calls = []

    def fake_ollama(model, prompt, temperature, json_mode):
        raise ConnectionError("primary down")

    def fake_gemini(prompt, temperature, json_mode):
        gemini_calls.append(prompt)
        return ("cached-gemini", 1, 1)

    monkeypatch.setattr(llm, "_call_ollama", fake_ollama)
    monkeypatch.setattr(llm, "_call_gemini", fake_gemini)
    monkeypatch.setattr(llm._settings, "fallback_enabled", True)
    _with_gemini(monkeypatch)

    prompt = _unique_prompt(tmp_path) + "-cachekey"
    cache.cache_invalidate(llm._build_cache_key("gemma3:4b", 0.2, False, prompt))

    r1 = llm.llm_call(prompt, model="gemma3:4b", cache=True, module="test")
    r2 = llm.llm_call(prompt, model="gemma3:4b", cache=True, module="test")
    assert r1 == r2 == "cached-gemini"
    assert len(gemini_calls) == 1, "second call must be a cache hit"


def test_gemini_cost_is_nonzero():
    from app.core.cost import estimate_cost
    # 1M in + 1M out on gemini-2.5-flash must register real spend
    assert estimate_cost("gemini-2.5-flash", 1_000_000, 1_000_000) == pytest.approx(2.80)
    assert estimate_cost("gemma3:4b", 1_000_000, 1_000_000) == 0.0


# ---- 2. prompt library ---------------------------------------------------

REQUIRED_KEYS = {"version", "description", "model", "temperature", "template", "changelog"}
INSTALLED_MODELS = {"gemma3:4b", "mistral:latest", "qwen3.5:latest", "zephyr:7b-beta"}


def test_library_has_fifteen_plus_prompts():
    reload_library()
    assert len(list_prompts()) >= 15


def test_every_prompt_has_required_metadata():
    reload_library()
    library = _load_library()
    for prompt_id, spec in library.items():
        missing = REQUIRED_KEYS - set(spec)
        assert not missing, f"{prompt_id} missing keys: {missing}"
        assert isinstance(spec["version"], int) and spec["version"] >= 1
        assert spec["changelog"], f"{prompt_id} has an empty changelog"
        assert len(spec["changelog"]) >= spec["version"], (
            f"{prompt_id}: changelog must have one entry per version"
        )


def test_every_prompt_uses_an_installed_model():
    reload_library()
    library = _load_library()
    for prompt_id, spec in library.items():
        assert spec["model"] in INSTALLED_MODELS, (
            f"{prompt_id} uses {spec['model']!r} which is not pulled locally"
        )


def test_every_template_is_renderable():
    """str.format must not choke on any template (catches unescaped braces)."""
    reload_library()
    library = _load_library()
    fmt = string.Formatter()
    for prompt_id, spec in library.items():
        fields = {
            name
            for _, name, _, _ in fmt.parse(spec["template"])
            if name  # None for literal chunks, '' for positional {}
        }
        assert "" not in fields, f"{prompt_id} has a positional {{}} placeholder"
        rendered = spec["template"].format(**{f: "X" for f in fields})
        assert rendered  # formatting succeeded


def test_parser_retry_prompt_renders():
    p = load_prompt("parser_retry_fix")
    rendered = p.format(error="Expecting ',' at line 3", original_prompt="PARSE THIS")
    assert "Expecting ','" in rendered
    assert "PARSE THIS" in rendered


# ---- 3. PM dashboard -----------------------------------------------------

client = TestClient(app)


def test_dashboard_costs_shape():
    resp = client.get("/dashboard/costs")
    assert resp.status_code == 200
    body = resp.json()
    assert {"today", "daily", "project_total_usd", "project_cap_usd",
            "budget_used_pct", "on_track"} <= set(body)
    assert len(body["daily"]) == 7
    assert body["project_cap_usd"] == 200.0


def test_dashboard_costs_custom_days():
    resp = client.get("/dashboard/costs?days=3")
    assert resp.status_code == 200
    assert len(resp.json()["daily"]) == 3


def test_dashboard_evals_shape():
    resp = client.get("/dashboard/evals")
    assert resp.status_code == 200
    modules = resp.json()["modules"]
    assert {"parser", "copilot", "explain"} == set(modules)
    for mod in modules.values():
        assert "accuracy" in mod
        assert "regression" in mod
