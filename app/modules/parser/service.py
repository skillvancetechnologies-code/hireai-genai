"""Parser service — the single function the eval runner and routes both call.

eval.py imports: from app.modules.parser.service import parse_resume_file
"""
from __future__ import annotations

import logging

from app.core.llm import LLMError, llm_call_json
from app.core.prompts import load_prompt
from app.modules.parser.extract import extract_text
from app.modules.parser.normalize import normalize_skills
from app.modules.parser.schemas import ParsedCandidate

log = logging.getLogger(__name__)


def parse_resume_file(file_path: str) -> dict:
    """Extract, parse, validate and return a candidate dict from a resume file.

    Args:
        file_path: absolute path to a .pdf or .docx resume.

    Returns:
        dict matching the ParsedCandidate schema.

    Raises:
        ValueError: if the file yields no usable text.
        LLMError: if the LLM fails after all retries.
        pydantic.ValidationError: if the LLM output violates the schema.
    """
    raw_text = extract_text(file_path)
    if not raw_text.strip():
        raise ValueError(
            "No text could be extracted — the file may be empty or a scanned image without OCR."
        )

    prompt_spec = load_prompt("parser_main")
    rendered = prompt_spec.format(resume_text=raw_text)

    data = _call_with_retry(rendered, model=prompt_spec.model, temperature=prompt_spec.temperature)

    data["skills"] = normalize_skills(data.get("skills") or [])
    data.setdefault("raw_text", raw_text)
    data.setdefault("projects", [])
    data.setdefault("phone", None)
    data.setdefault("summary", "")

    candidate = ParsedCandidate(**data)
    return candidate.model_dump()


def _call_with_retry(initial_prompt: str, *, model: str, temperature: float) -> dict:
    """Call the LLM up to 3 times, feeding back the JSON error on each retry."""
    prompt = initial_prompt
    last_error = ""
    for attempt in range(3):
        try:
            return llm_call_json(prompt, model=model, temperature=temperature, module="parser")
        except LLMError as exc:
            last_error = str(exc)
            if "invalid JSON" in last_error and attempt < 2:
                log.warning("Parser attempt %d: malformed JSON — retrying with error feedback", attempt + 1)
                prompt = (
                    f"Your previous output was invalid JSON. Error: {last_error}\n\n"
                    f"Try again. Return ONLY valid JSON — no markdown, no explanation:\n\n"
                    f"{initial_prompt}"
                )
            else:
                raise
    raise LLMError(f"Parser gave up after 3 attempts. Last error: {last_error}")
