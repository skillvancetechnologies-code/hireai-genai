import json
from typing import Any

from app.core.config import get_settings
from app.core.llm import llm_call
from app.core.prompts import load_prompt


def parse_intent_with_llm(query: str) -> dict[str, Any]:
    """Ask the local LLM to convert recruiter text into JSON filter intent."""
    settings = get_settings()
    prompt_spec = load_prompt("intent_classifier")
    rendered = prompt_spec.format(query=query)
    raw_response = llm_call(
        rendered,
        module="copilot",
        model=settings.copilot_model,
        temperature=prompt_spec.temperature,
    )
    return _extract_json(raw_response)


def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").replace("json", "", 1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("LLM did not return a JSON object.")

    return json.loads(cleaned[start : end + 1])
