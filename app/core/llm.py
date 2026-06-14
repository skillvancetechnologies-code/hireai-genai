"""The ONE place that talks to the LLM backend (Ollama, local inference).

Every module (parser, copilot, explain) calls `llm_call()`. Nobody
imports the openai SDK directly. This wrapper handles:

- Redis caching keyed on (model, temperature, json_mode, prompt)
- Exponential backoff retry (3 attempts, for Ollama cold-start delays)
- Gemini fallback (team docs 8.3): if the primary model fails after all
  retries, the same call is retried against Gemini Flash through Google's
  OpenAI-compatible endpoint (requires GEMINI_API_KEY; no google.* SDK)
- Local last-resort fallback: if Gemini is unconfigured or also fails,
  the call is retried once against settings.fallback_model
- JSON-mode handling
- Per-call token + cost logging via app.core.cost

LLM backend: Ollama running locally at http://localhost:11434/v1
Default model: gemma3:4b (no API key required)
To change model: set OLLAMA_MODEL or PARSER_MODEL/COPILOT_MODEL/EXPLAIN_MODEL in .env
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.core.cost import log_call, project_total

log = logging.getLogger(__name__)
_settings = get_settings()

# Ollama's OpenAI-compatible endpoint — no real API key needed
_client = OpenAI(
    api_key="ollama",
    base_url=_settings.ollama_base_url,
)

_gemini_client: Optional[OpenAI] = None


def _get_gemini_client() -> Optional[OpenAI]:
    """Lazy Gemini client via Google's OpenAI-compatible endpoint.
    Returns None when GEMINI_API_KEY is not configured."""
    global _gemini_client
    if not _settings.gemini_api_key:
        return None
    if _gemini_client is None:
        _gemini_client = OpenAI(
            api_key=_settings.gemini_api_key,
            base_url=_settings.gemini_base_url,
        )
    return _gemini_client


def _build_cache_key(model: str, temperature: float, json_mode: bool, prompt: str) -> str:
    raw = f"{model}|{temperature}|{int(json_mode)}|{prompt.strip()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"llm:{digest}"


class LLMError(Exception):
    pass


class BudgetExceeded(Exception):
    """Raised before any LLM call when project_total() has reached
    settings.project_spend_cap_usd. Cache hits are exempt.
    (Local models cost $0 so this guard effectively never triggers.)"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _call_ollama(model: str, prompt: str, temperature: float, json_mode: bool) -> tuple[str, int, int]:
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = _client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    return text, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def _call_gemini(prompt: str, temperature: float, json_mode: bool) -> tuple[str, int, int]:
    client = _get_gemini_client()
    if client is None:
        raise LLMError("GEMINI_API_KEY not configured")
    kwargs = {
        "model": _settings.gemini_fallback_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    usage = resp.usage
    return text, getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0)


def llm_call(
    prompt: str,
    *,
    module: str,
    model: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.2,
    cache: bool = True,
    ttl: Optional[int] = None,
    cache_key: Optional[str] = None,
) -> str:
    """Single entry point for every LLM call in this codebase.

    Args:
        prompt: the full prompt string (already formatted).
        model: override default; falls back to PARSER_MODEL env var.
        json_mode: enforce JSON response_format.
        temperature: sampling temperature.
        cache: enable Redis caching.
        ttl: cache TTL seconds; defaults to settings.default_cache_ttl_seconds.
        cache_key: explicit key (use for deterministic content like
            explanations keyed on candidate_id/job_id/model_version).
            If None, key is hashed from inputs.
        module: tag for cost tracking (`parser`, `copilot`, `explain`).
    """
    model = model or _settings.parser_model
    ttl = ttl if ttl is not None else _settings.default_cache_ttl_seconds

    key = cache_key or _build_cache_key(model, temperature, json_mode, prompt)

    if cache:
        hit = cache_get(key)
        if hit is not None:
            log_call(model=model, module=module, cache_hit=True)
            return hit

    # Budget guard: local models cost $0 so this never triggers in practice,
    # but the guard is kept for structural consistency.
    cap = _settings.project_spend_cap_usd
    spent = project_total()
    if spent >= cap:
        raise BudgetExceeded(
            f"project_total ${spent:.4f} >= cap ${cap:.2f}; refusing LLM call"
        )

    used_model = model
    result = None
    errors: list[str] = []
    try:
        result = _call_ollama(model, prompt, temperature, json_mode)
    except Exception as e:
        errors.append(f"primary {model}: {e}")

        # 1) Gemini fallback (team docs 8.3) — only when a key is configured.
        if _settings.fallback_enabled and _settings.gemini_api_key:
            gemini_model = _settings.gemini_fallback_model
            log.warning(
                "Primary model %s failed after retries (%s) — falling back to Gemini (%s)",
                model, e, gemini_model,
            )
            try:
                result = _call_gemini(prompt, temperature, json_mode)
                used_model = gemini_model
            except Exception as ge:
                errors.append(f"gemini {gemini_model}: {ge}")
                log.warning("Gemini fallback failed: %s", ge)

        # 2) Local last-resort fallback (keeps offline dev working).
        local_fb = _settings.fallback_model
        if (
            result is None
            and _settings.fallback_enabled
            and local_fb
            and local_fb != model
        ):
            log.warning("Falling back to local model %s", local_fb)
            try:
                result = _call_ollama(local_fb, prompt, temperature, json_mode)
                used_model = local_fb
            except Exception as le:
                errors.append(f"local fallback {local_fb}: {le}")

        if result is None:
            log.error("All LLM backends failed: %s", "; ".join(errors))
            raise LLMError("; ".join(errors)) from e

    text, p_tokens, c_tokens = result
    log_call(model=used_model, module=module, prompt_tokens=p_tokens, completion_tokens=c_tokens)

    if cache:
        cache_set(key, text, ttl=ttl)
    return text


def llm_call_json(
    prompt: str,
    *,
    module: str,
    model: Optional[str] = None,
    temperature: float = 0.1,
    **kwargs,
) -> dict:
    """Convenience: call with json_mode=True and parse the response."""
    raw = llm_call(
        prompt,
        model=model,
        json_mode=True,
        temperature=temperature,
        module=module,
        **kwargs,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMError(f"LLM returned invalid JSON: {e}; raw={raw[:200]}")
