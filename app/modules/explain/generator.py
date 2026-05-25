from app.modules.explain.prompts import build_prompt
from app.modules.explain.mock_data import candidate_data, job_data
from app.core.llm import llm_call


def generate_explanation(candidate_id, job_id):

    # Candidate validation
    if candidate_id not in candidate_data:
        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "explanation_text": "Candidate not found",
            "top_strengths": [],
            "top_gaps": []
        }

    # Job validation
    if job_id not in job_data:
        return {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "explanation_text": "Job not found",
            "top_strengths": [],
            "top_gaps": []
        }

    # Fetch data
    candidate = candidate_data[candidate_id]
    job = job_data[job_id]

    # Build prompt
    prompt = build_prompt(candidate)

    # Call LLM
    explanation = llm_call(prompt, module="explain")

    # Return API response
    return {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "explanation_text": explanation,
        "top_strengths": candidate["matched_skills"].split(", "),
        "top_gaps": candidate["missing_skills"].split(", ")
    }