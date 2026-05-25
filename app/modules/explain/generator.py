from app.core.config import get_settings
from app.core.llm import llm_call
from app.core.prompts import load_prompt
from app.modules.explain.mock_data import candidate_data, job_data


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

    candidate = candidate_data[candidate_id]
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
        "top_strengths": candidate["matched_skills"].split(", "),
        "top_gaps": candidate["missing_skills"].split(", "),
    }
