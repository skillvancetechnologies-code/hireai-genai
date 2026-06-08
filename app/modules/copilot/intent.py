import re
from typing import Any

from pydantic import ValidationError

from app.models.schemas import QueryIntent
from app.services.llm_service import parse_intent_with_llm


class IntentParseError(ValueError):
    """Raised when a recruiter query cannot be turned into search intent."""


KNOWN_SKILLS = {
    "python": "Python",
    "react": "React",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "sql": "SQL",
    "django": "Django",
    "docker": "Docker",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "java": "Java",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
}

LABELS = {
    "good fit": "Good Fit",
    "average fit": "Average Fit",
    "poor fit": "Poor Fit",
}

STATUSES = {
    "applied": "Applied",
    "shortlisted": "Shortlisted",
    "interviewed": "Interviewed",
    "hired": "Hired",
    "rejected": "Rejected",
}

ROLE_TERMS = [
    "full stack",
    "machine learning",
    "data scientist",
    "data engineer",
    "product manager",
    "backend",
    "frontend",
    "devops",
    "mobile",
    "qa",
]

SEMANTIC_CUES = [
    "similar to",
    "built",
    "worked on",
    "projects",
    "systems",
    "automation",
    "chatbot",
    "fintech",
    "scalable api",
    "experienced in",
    "strong machine learning",
]


def parse_query(query: str) -> QueryIntent:
    """Convert recruiter text into validated Week 3 search intent."""
    if not query or not query.strip():
        raise IntentParseError("Query cannot be empty.")

    if _looks_semantic(query.lower()):
        return _validate_intent(_parse_with_rules(query), original_query=query)

    try:
        return _validate_intent(parse_intent_with_llm(query), original_query=query)
    except Exception:
        return _validate_intent(_parse_with_rules(query), original_query=query)


def _validate_intent(data: dict[str, Any], original_query: str = "") -> QueryIntent:
    """Apply defaults and normalize common LLM output variations."""
    normalized = dict(data)
    parsed_type = str(normalized.get("type") or "filter").lower()
    normalized["type"] = "semantic" if parsed_type == "semantic" else "filter"

    job_id = normalized.get("job_id")
    if isinstance(job_id, str):
        match = re.search(r"\d+", job_id)
        normalized["job_id"] = int(match.group()) if match else None

    skills = normalized.get("skills_required") or []
    if isinstance(skills, str):
        skills = [skills]
    normalized["skills_required"] = [
        KNOWN_SKILLS.get(str(skill).lower(), str(skill).strip()) for skill in skills
    ]

    for key, mapping in (("label_filter", LABELS), ("status_filter", STATUSES)):
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = mapping.get(value.lower(), value.title())

    normalized.setdefault("min_experience", None)
    normalized.setdefault("label_filter", None)
    normalized.setdefault("status_filter", None)
    normalized.setdefault("job_id", None)
    normalized.setdefault("top_k", 10)
    normalized.setdefault("free_text", "")

    if normalized["type"] == "semantic" and not normalized["free_text"]:
        normalized["free_text"] = original_query.strip()

    try:
        return QueryIntent.model_validate(normalized)
    except ValidationError as exc:
        raise IntentParseError("Could not understand this recruiter query.") from exc


def _parse_with_rules(query: str) -> dict[str, Any]:
    """Parse the supported Week 3 routes without depending on an LLM call."""
    normalized = query.lower()

    top_match = re.search(r"\btop\s+(\d+)\b", normalized)
    top_k = int(top_match.group(1)) if top_match else 10

    if _looks_semantic(normalized):
        return {
            "type": "semantic",
            "job_id": None,
            "skills_required": [],
            "min_experience": None,
            "label_filter": None,
            "status_filter": None,
            "top_k": top_k,
            "free_text": query.strip(),
        }

    job_match = re.search(r"\bjob\s*(?:id\s*)?0*(\d+)\b", normalized)
    experience_match = re.search(
        r"\b(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\b", normalized
    )

    skills = [
        display_name
        for token, display_name in KNOWN_SKILLS.items()
        if re.search(rf"\b{re.escape(token)}\b", normalized)
    ]
    skills = list(dict.fromkeys(skills))

    label = next(
        (display for token, display in LABELS.items() if token in normalized), None
    )
    status = next(
        (display for token, display in STATUSES.items() if token in normalized), None
    )
    role_term = next((term for term in ROLE_TERMS if term in normalized), "")

    return {
        "type": "filter",
        "job_id": int(job_match.group(1)) if job_match else None,
        "skills_required": skills,
        "min_experience": (
            float(experience_match.group(1)) if experience_match else None
        ),
        "label_filter": label,
        "status_filter": status,
        "top_k": top_k,
        "free_text": role_term,
    }


def _looks_semantic(normalized_query: str) -> bool:
    """Classify natural-language similarity/project searches as semantic."""
    return any(cue in normalized_query for cue in SEMANTIC_CUES)
