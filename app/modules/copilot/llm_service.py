import json
from typing import Any

from app.core.config import get_settings
from app.core.llm import llm_call


INTENT_PROMPT_TEMPLATE = """
Convert this recruiter query into a structured candidate filter search.

Week 2 supports filtering only. Do not use semantic search.

Return ONLY valid JSON with this schema:
{{
  "type": "filter",
  "job_id": <integer or null>,
  "skills_required": ["skill names"],
  "min_experience": <number or null>,
  "label_filter": "Good Fit" | "Average Fit" | "Poor Fit" | null,
  "status_filter": "Applied" | "Shortlisted" | "Interviewed" | "Hired" | "Rejected" | null,
  "top_k": <integer, default 10>,
  "free_text": "<remaining meaningful role or keyword text, or empty string>"
}}

Examples:
Query: "Show top 5 Good Fit Python developers"
Output: {{"type":"filter","job_id":null,"skills_required":["Python"],"min_experience":null,"label_filter":"Good Fit","status_filter":null,"top_k":5,"free_text":""}}

Query: "Show shortlisted Python developers with 2 years experience"
Output: {{"type":"filter","job_id":null,"skills_required":["Python"],"min_experience":2,"label_filter":null,"status_filter":"Shortlisted","top_k":10,"free_text":""}}

Query: "Top 3 backend developers"
Output: {{"type":"filter","job_id":null,"skills_required":[],"min_experience":null,"label_filter":null,"status_filter":null,"top_k":3,"free_text":"backend"}}

Recruiter query: {query}
"""


def parse_intent_with_llm(query: str) -> dict[str, Any]:
    """Ask the local LLM to convert recruiter text into JSON filter intent."""
    settings = get_settings()
    prompt = INTENT_PROMPT_TEMPLATE.format(query=query)
    raw_response = llm_call(
        prompt,
        module="copilot",
        model=settings.copilot_model,
        temperature=0.1,
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
