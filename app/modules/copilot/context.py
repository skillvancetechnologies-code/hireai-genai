import json
from dataclasses import dataclass, field
from typing import Any

from app.models.schemas import Candidate
from app.modules.copilot.intent import KNOWN_SKILLS, ROLE_TERMS


class ContextResolutionError(ValueError):
    """Raised when a follow-up query cannot be resolved from history."""


@dataclass
class ContextResolution:
    """Result of applying conversation history to a recruiter query."""

    query: str
    context_used: bool = False
    direct_candidates: list[Candidate] = field(default_factory=list)
    focus_top_candidate: bool = False
    note: str = ""


REFERENCE_TERMS = [
    "his",
    "her",
    "them",
    "those candidates",
    "the first candidate",
    "the top candidate",
    "shortlisted ones",
]


def resolve_context(query: str, history: list[dict[str, Any]] | None) -> ContextResolution:
    """Resolve simple follow-up references using the last 5 conversation turns."""
    if history is None:
        return ContextResolution(query=query)
    if not isinstance(history, list):
        raise ContextResolutionError("History must be a list of conversation turns.")

    recent_history = history[-5:]
    if not recent_history:
        return ContextResolution(query=query)

    normalized_query = query.lower()

    if _asks_for_projects(normalized_query):
        candidate = _last_candidate_from_history(recent_history)
        if candidate is not None:
            return ContextResolution(
                query=f"Show projects for {candidate.name}",
                context_used=True,
                direct_candidates=[candidate],
                focus_top_candidate=True,
                note=f"Resolved follow-up to candidate {candidate.name}.",
            )

        previous_query = _last_query_from_history(recent_history)
        if previous_query:
            return ContextResolution(
                query=previous_query,
                context_used=True,
                focus_top_candidate=True,
                note="Resolved follow-up to the top candidate from the previous query.",
            )

        raise ContextResolutionError(
            "Could not resolve which candidate the follow-up query refers to."
        )

    if _uses_contextual_filter(normalized_query):
        previous_query = _last_query_from_history(recent_history)
        resolved_query = _merge_follow_up_filters(query, previous_query)
        return ContextResolution(
            query=resolved_query,
            context_used=resolved_query != query,
            note="Resolved follow-up filters from previous query.",
        )

    if any(term in normalized_query for term in REFERENCE_TERMS):
        raise ContextResolutionError(
            "The follow-up reference could not be resolved from conversation history."
        )

    return ContextResolution(query=query)


def _asks_for_projects(normalized_query: str) -> bool:
    return "project" in normalized_query and any(
        term in normalized_query
        for term in ["his", "her", "their", "first candidate", "top candidate"]
    )


def _uses_contextual_filter(normalized_query: str) -> bool:
    return any(
        phrase in normalized_query
        for phrase in [
            "shortlisted ones",
            "only the shortlisted",
            "show shortlisted",
            "show only",
            "those candidates",
        ]
    )


def _merge_follow_up_filters(query: str, previous_query: str) -> str:
    fragments: list[str] = []
    previous_lower = previous_query.lower()
    current_lower = query.lower()

    if "shortlisted" in current_lower:
        fragments.append("shortlisted")
    if "hired" in current_lower:
        fragments.append("hired")
    if "rejected" in current_lower:
        fragments.append("rejected")
    if "applied" in current_lower:
        fragments.append("applied")
    if "interviewed" in current_lower:
        fragments.append("interviewed")

    for token, display_name in KNOWN_SKILLS.items():
        if token in previous_lower and display_name not in fragments:
            fragments.append(display_name)

    for role in ROLE_TERMS:
        if role in previous_lower and role not in fragments:
            fragments.append(role)

    if not fragments:
        return query

    return "Show " + " ".join(fragments) + " candidates"


def _last_query_from_history(history: list[dict[str, Any]]) -> str:
    for turn in reversed(history):
        turn = _as_mapping(turn)
        if not isinstance(turn, dict):
            continue
        for key in ["query", "content", "message", "user", "recruiter_query"]:
            value = turn.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _last_candidate_from_history(history: list[dict[str, Any]]) -> Candidate | None:
    for turn in reversed(history):
        candidates = _extract_candidates(turn)
        if candidates:
            return candidates[0]
    return None


def _extract_candidates(turn: dict[str, Any]) -> list[Candidate]:
    turn = _as_mapping(turn)
    if not isinstance(turn, dict):
        return []

    raw_candidates = _find_candidates(turn)

    if not isinstance(raw_candidates, list):
        return []

    candidates: list[Candidate] = []
    for raw_candidate in raw_candidates:
        if isinstance(raw_candidate, Candidate):
            candidates.append(raw_candidate)
        elif isinstance(raw_candidate, dict):
            candidate = _candidate_from_mapping(raw_candidate)
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def _as_mapping(value: Any) -> dict[str, Any] | Any:
    """Support both raw dict history and typed Pydantic history turns."""
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if hasattr(value, "dict"):
        return value.dict(exclude_none=True)
    return value


def _find_candidates(value: Any) -> Any:
    """Find a candidates list across common history payload shapes."""
    value = _as_mapping(value)
    if isinstance(value, dict):
        direct_candidates = value.get("candidates")
        if isinstance(direct_candidates, list) and direct_candidates:
            return direct_candidates

        for key in ["response", "body", "assistant", "output", "data", "result"]:
            nested = value.get(key)
            found = _find_candidates(nested)
            if isinstance(found, list):
                return found

        for key in ["content", "message"]:
            parsed = _parse_json_string(value.get(key))
            found = _find_candidates(parsed)
            if isinstance(found, list):
                return found

        if isinstance(direct_candidates, list):
            return direct_candidates

    return None


def _parse_json_string(value: Any) -> Any:
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _candidate_from_mapping(raw_candidate: dict[str, Any]) -> Candidate | None:
    """Accept full API candidates and minimal history candidates."""
    candidate_data = {
        "candidate_id": raw_candidate.get("candidate_id") or raw_candidate.get("id") or 0,
        "name": raw_candidate.get("name") or "Referenced Candidate",
        "skills": raw_candidate.get("skills") or [],
        "experience_years": raw_candidate.get("experience_years")
        or raw_candidate.get("experience")
        or 0,
        "education": raw_candidate.get("education") or "",
        "projects": raw_candidate.get("projects") or [],
        "job_id": raw_candidate.get("job_id") or 0,
        "role": raw_candidate.get("role") or "",
        "status": raw_candidate.get("status") or "",
        "score": raw_candidate.get("score") or 0,
        "label": raw_candidate.get("label") or "",
    }
    try:
        return Candidate.model_validate(candidate_data)
    except Exception:
        return None
