"""Candidate/job lookup tables for the explain module.

Built from the shared cleaned datasets in app/data via
app.services.dataset_loader, so G2 and G3 read the same source of truth.
The tables refresh automatically when the underlying CSVs change.
"""

import pandas as pd

from app.services.dataset_loader import (
    DatasetValidationError,
    get_candidate_search_data,
    get_candidates_data,
    get_dataset_version,
    get_jobs_data,
)


_candidate_data: dict[str, dict] = {}
_job_data: dict[str, dict] = {}
_candidate_job_data: dict[tuple[str, str], dict] = {}
_loaded_version: tuple | None = None


def has_candidate(candidate_id: str) -> bool:
    _ensure_loaded()
    return str(candidate_id) in _candidate_data


def has_job(job_id: str) -> bool:
    _ensure_loaded()
    return str(job_id) in _job_data


def get_candidate_job_data(candidate_id: str, job_id: str) -> dict | None:
    _ensure_loaded()
    return _candidate_job_data.get((str(candidate_id), str(job_id)))


def _ensure_loaded() -> None:
    global _loaded_version
    version = get_dataset_version()
    if version == _loaded_version:
        return

    try:
        candidates, jobs, pairs = _build_lookups()
    except DatasetValidationError as exc:
        print(f"WARNING: explain data unavailable: {exc}")
        candidates, jobs, pairs = {}, {}, {}

    _candidate_data.clear()
    _candidate_data.update(candidates)
    _job_data.clear()
    _job_data.update(jobs)
    _candidate_job_data.clear()
    _candidate_job_data.update(pairs)
    _loaded_version = version


def _build_lookups() -> tuple[dict, dict, dict]:
    candidates = {
        str(row["candidate_id"]).strip(): {
            "candidate_id": str(row["candidate_id"]).strip(),
            "name": _title(row.get("name"), "Candidate"),
            "skills": _split_pipe(row.get("skills")),
            "education": _clean_str(row.get("education")),
            "experience_years": _to_float(row.get("experience_years")),
            "projects": _split_pipe(row.get("projects")),
        }
        for row in get_candidates_data().to_dict("records")
    }

    jobs = {
        str(row["job_id"]).strip(): {
            "job_id": str(row["job_id"]).strip(),
            "job_title": _title(row.get("role"), "Job"),
            "required_skills": _split_pipe(row.get("required_skills")),
            "role": _clean_str(row.get("role")),
            "min_experience": _to_float(row.get("min_experience")),
        }
        for row in get_jobs_data().to_dict("records")
    }

    pairs = {}
    for row in get_candidate_search_data().to_dict("records"):
        cid = str(row["candidate_id"]).strip()
        jid = str(row["job_id"]).strip()
        candidate = candidates.get(cid)
        job = jobs.get(jid)
        if not candidate or not job:
            continue

        candidate_skills = candidate["skills"]
        required_skills = job["required_skills"]
        candidate_skills_lower = {skill.lower(): skill for skill in candidate_skills}
        matched_skills = [
            skill for skill in required_skills
            if skill.lower() in candidate_skills_lower
        ]
        missing_skills = [
            skill for skill in required_skills
            if skill.lower() not in candidate_skills_lower
        ]

        pairs[(cid, jid)] = {
            "candidate_id": cid,
            "job_id": jid,
            "name": candidate["name"],
            "job_title": job["job_title"],
            "education": candidate["education"],
            "skills": _format_list(candidate_skills),
            "projects": _format_list(candidate["projects"]),
            "role": job["role"],
            "required_skills": _format_list(required_skills),
            "score": _to_float(row.get("score")),
            "label": _title(row.get("label"), "Unknown Fit"),
            "skills_match": _to_float(row.get("skills_match")),
            "experience_score": _to_float(row.get("experience_score")),
            "matched_count": len(matched_skills),
            "required_count": len(required_skills),
            "num_candidate_skills": len(candidate_skills),
            "num_required_skills": len(required_skills),
            "matched_skills": _format_list(matched_skills),
            "missing_skills": _format_list(missing_skills),
            "candidate_exp": candidate["experience_years"],
            "required_exp": job["min_experience"],
            "project_score": _to_float(row.get("project_score")),
            "application_status": _clean_str(row.get("status")) or "unknown",
            "application_date": _clean_str(row.get("application_date")) or "unknown",
        }

    return candidates, jobs, pairs


def _clean_str(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _split_pipe(value) -> list[str]:
    cleaned = _clean_str(value)
    if not cleaned:
        return []
    return [item.strip() for item in cleaned.split("|") if item.strip()]


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "None"


def _to_float(value, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return default if pd.isna(result) else result


def _title(value, fallback: str) -> str:
    clean_value = _clean_str(value)
    return clean_value.title() if clean_value else fallback
