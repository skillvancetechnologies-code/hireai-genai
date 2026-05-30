import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"

CANDIDATES_PATH = DATA_DIR / "candidates.csv"
JOBS_PATH = DATA_DIR / "jobs.csv"
SCORES_PATH = DATA_DIR / "scores.csv"
APPLICATIONS_PATH = DATA_DIR / "applications.csv"

candidate_data = {}
job_data = {}
candidate_job_data = {}


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _split_pipe(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split("|") if item.strip()]


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "None"


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _title(value, fallback: str) -> str:
    clean_value = str(value or "").strip()
    return clean_value.title() if clean_value else fallback


def _load_real_data() -> None:
    candidates = {
        str(row["candidate_id"]).strip(): {
            "candidate_id": str(row["candidate_id"]).strip(),
            "name": _title(row.get("name"), "Candidate"),
            "skills": _split_pipe(row.get("skills")),
            "experience_years": _to_float(row.get("experience_years")),
            "projects": _split_pipe(row.get("projects")),
        }
        for row in _read_csv(CANDIDATES_PATH)
    }

    jobs = {
        str(row["job_id"]).strip(): {
            "job_id": str(row["job_id"]).strip(),
            "job_title": _title(row.get("role"), "Job"),
            "required_skills": _split_pipe(row.get("required_skills")),
            "min_experience": _to_float(row.get("min_experience")),
        }
        for row in _read_csv(JOBS_PATH)
    }

    applications = {
        (str(row["candidate_id"]).strip(), str(row["job_id"]).strip()): row
        for row in _read_csv(APPLICATIONS_PATH)
    }

    candidate_data.update(candidates)
    job_data.update(jobs)

    for score_row in _read_csv(SCORES_PATH):
        cid = str(score_row["candidate_id"]).strip()
        jid = str(score_row["job_id"]).strip()
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
        application = applications.get((cid, jid), {})

        candidate_job_data[(cid, jid)] = {
            "candidate_id": cid,
            "job_id": jid,
            "name": candidate["name"],
            "job_title": job["job_title"],
            "score": _to_float(score_row.get("score")),
            "label": _title(score_row.get("label"), "Unknown Fit"),
            "skills_match": _to_float(score_row.get("skills_match")),
            "matched_count": len(matched_skills),
            "required_count": len(required_skills),
            "matched_skills": _format_list(matched_skills),
            "missing_skills": _format_list(missing_skills),
            "candidate_exp": candidate["experience_years"],
            "required_exp": job["min_experience"],
            "project_score": _to_float(score_row.get("project_score")),
            "application_status": application.get("status", "unknown"),
            "application_date": application.get("application_date", "unknown"),
        }


def get_candidate_job_data(candidate_id: str, job_id: str) -> dict | None:
    return candidate_job_data.get((str(candidate_id), str(job_id)))


try:
    _load_real_data()
except FileNotFoundError as exc:
    print(f"WARNING: required data file not found: {exc.filename}")
    candidate_data.clear()
    job_data.clear()
    candidate_job_data.clear()
