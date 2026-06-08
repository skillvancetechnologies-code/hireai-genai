from app.models.schemas import CopilotResponse, QueryIntent
from app.modules.copilot.intent import parse_query
from app.modules.copilot.retriever import semantic_search
from app.services.candidate_service import get_candidates


def run_copilot(query: str) -> CopilotResponse:
    """Parse a recruiter query and route it to filter or semantic search."""
    intent = parse_query(query)

    if intent.type == "semantic":
        candidates = semantic_search(intent.free_text or query, intent.top_k)
    else:
        candidates = get_candidates(intent)

    return CopilotResponse(
        query_interpreted=intent,
        candidates=candidates,
        summary=_build_summary(intent, len(candidates)),
    )


def _build_summary(intent: QueryIntent, result_count: int) -> str:
    """Create a static, search-aware summary without advanced LLM generation."""
    if intent.type == "semantic":
        return (
            f"Found top {result_count} semantic matches for "
            f"'{intent.free_text}', ranked by vector similarity."
        )

    filters: list[str] = []
    if intent.label_filter:
        filters.append(intent.label_filter)
    if intent.status_filter:
        filters.append(intent.status_filter)
    filters.append("candidates")
    if intent.skills_required:
        filters.append(f"skilled in {', '.join(intent.skills_required)}")
    if intent.min_experience is not None:
        filters.append(f"with at least {intent.min_experience:g} years experience")
    if intent.job_id is not None:
        filters.append(f"for job {intent.job_id}")
    if intent.free_text:
        filters.append(f"matching '{intent.free_text}'")

    return f"Found top {result_count} {' '.join(filters)}, ranked by score."
