from app.core.config import get_settings
from app.core.llm import llm_call
from app.core.prompts import load_prompt
from app.modules.explain.mock_data import (
    candidate_data,
    get_candidate_job_data,
    job_data,
)


def _split_output_list(value: str) -> list[str]:
    if not value or value == "None":
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def generate_explanation(candidate_id: str, job_id: str) -> dict:
    if candidate_id not in candidate_data:
        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "explanation_text": "Candidate not found",
            "top_strengths": [],
            "top_gaps": [],
        }

    if job_id not in job_data:
        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "explanation_text": "Job not found",
            "top_strengths": [],
            "top_gaps": [],
        }

    candidate = get_candidate_job_data(candidate_id, job_id)
    if candidate is None:
        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "explanation_text": "Score not found for this candidate and job",
            "top_strengths": [],
            "top_gaps": [],
        }

    settings = get_settings()
    prompt_spec = load_prompt("explanation")

    rendered = prompt_spec.format(
        name=candidate["name"],
        job_title=candidate["job_title"],
        score=candidate["score"],
        label=candidate["label"],
        skills_match=candidate["skills_match"],
        matched_count=candidate["matched_count"],
        required_count=candidate["required_count"],
        candidate_exp=candidate["candidate_exp"],
        required_exp=candidate["required_exp"],
        project_score=candidate["project_score"],
        matched_skills=candidate["matched_skills"],
        missing_skills=candidate["missing_skills"],
    )

    # Cache key is deterministic on (candidate, job, prompt version) — never
    # regenerates unless the prompt version bumps.
    cache_key = f"explain:{candidate_id}:{job_id}:v{prompt_spec.version}"

    explanation = llm_call(
        rendered,
        module="explain",
        model=settings.explain_model,
        temperature=prompt_spec.temperature,
        cache_key=cache_key,
        ttl=86400 * 30,  # 30 days
    )

    return {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "explanation_text": explanation,
        "top_strengths": _split_output_list(candidate["matched_skills"]),
        "top_gaps": _split_output_list(candidate["missing_skills"]),
    }
