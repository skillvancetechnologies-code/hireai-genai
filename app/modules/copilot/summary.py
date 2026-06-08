import json

from langchain_core.prompts import PromptTemplate

from app.models.schemas import Candidate
from app.modules.copilot.prompts import SUMMARY_PROMPT_TEMPLATE
from app.services.llm_service import get_llm


def generate_candidate_summary(candidates: list[Candidate], recruiter_query: str) -> str:
    """Generate a concise recruiter-friendly summary using LangChain + Ollama."""
    if not candidates:
        return "No matching candidates were found for this recruiter query."

    try:
        prompt = PromptTemplate.from_template(SUMMARY_PROMPT_TEMPLATE)
        chain = prompt | get_llm()
        result = chain.invoke(
            {
                "query": recruiter_query,
                "candidates": _candidate_summary_payload(candidates),
            }
        )
        cleaned = str(result).strip()
        return cleaned or _fallback_summary(candidates, recruiter_query)
    except Exception:
        return _fallback_summary(candidates, recruiter_query)


def _candidate_summary_payload(candidates: list[Candidate]) -> str:
    """Keep the LLM input compact by sending only top candidate highlights."""
    highlights = []
    for candidate in candidates[:5]:
        highlights.append(
            {
                "name": candidate.name,
                "skills": candidate.skills[:8],
                "experience_years": candidate.experience_years,
                "role": candidate.role,
                "status": candidate.status,
                "score": candidate.score,
                "label": candidate.label,
                "projects": candidate.projects[:3],
            }
        )
    return json.dumps(highlights, ensure_ascii=True)


def _fallback_summary(candidates: list[Candidate], recruiter_query: str) -> str:
    """Deterministic fallback when the local LLM is unavailable."""
    top_skills = sorted(
        {
            skill
            for candidate in candidates[:5]
            for skill in candidate.skills[:5]
        }
    )[:6]
    avg_experience = sum(c.experience_years for c in candidates) / len(candidates)
    return (
        f"The top {len(candidates)} candidates are relevant for '{recruiter_query}' "
        f"with strengths across {', '.join(top_skills) or 'the requested skills'}. "
        f"They average {avg_experience:.1f} years of experience and include profiles "
        "with matching project and role backgrounds."
    )
