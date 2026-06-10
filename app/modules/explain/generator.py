from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.llm import llm_call
from app.core.prompts import load_prompt
from app.modules.explain.mock_data import (
    get_candidate_job_data,
    has_candidate,
    has_job,
)
from app.modules.explain.shap_client import get_shap_explanation


def _split_output_list(value: str) -> list[str]:
    if not value or value == "None":
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _fallback_explanation(candidate: dict) -> str:
    return (
        f"{candidate['name']} has a composite score of {candidate['score']}/100 "
        f"for {candidate['job_title']} with a label of {candidate['label']}. "
        f"The profile matches {candidate['matched_skills']} and has "
        f"{candidate['candidate_exp']} years of experience against a requirement "
        f"of {candidate['required_exp']} years. "
        f"Skills not present in the candidate profile are {candidate['missing_skills']}."
    )


def _fallback_shap_explanation(candidate: dict) -> dict:
    return {
        "model_version": "local-shap-v1",
        "score_metadata": {
            "predicted_label": candidate.get("label", "unknown"),
            "confidence": None,
            "probabilities": {},
            "raw_or_normalized": "raw",
        },
        "shap_values": {
            "feature_names": ["skills_match", "project_score"],
            "values": [
                round(float(candidate.get("skills_match", 0)) / 100, 4),
                round(float(candidate.get("project_score", 0)) / 100, 4),
            ],
            "raw_or_normalized": "raw",
            "positive_means": "increases probability of predicted class",
            "predicted_class_index": None,
            "base_value": None,
        },
        "top_positive_drivers": [
            {
                "feature": "skills_match",
                "shap_value": round(float(candidate.get("skills_match", 0)) / 100, 4),
            }
        ],
        "top_negative_drivers": [],
    }


def generate_explanation(candidate_id: str, job_id: str) -> dict:
    if not has_candidate(candidate_id):
        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "explanation_text": "Candidate not found",
            "top_strengths": [],
            "top_gaps": [],
        }

    if not has_job(job_id):
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

    try:
        explanation = llm_call(
            rendered,
            module="explain",
            model=settings.explain_model,
            temperature=prompt_spec.temperature,
            cache_key=cache_key,
            ttl=86400 * 30,  # 30 days
        )
    except Exception:
        explanation = _fallback_explanation(candidate)

    try:
        shap_explanation = get_shap_explanation(candidate)
    except Exception:
        shap_explanation = _fallback_shap_explanation(candidate)

    return {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "explanation_text": explanation,
        "top_strengths": _split_output_list(candidate["matched_skills"]),
        "top_gaps": _split_output_list(candidate["missing_skills"]),
        "shap_values": shap_explanation["shap_values"],
        "top_positive_drivers": shap_explanation["top_positive_drivers"],
        "top_negative_drivers": shap_explanation["top_negative_drivers"],
        "model_version": shap_explanation["model_version"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score_metadata": shap_explanation["score_metadata"],
    }
