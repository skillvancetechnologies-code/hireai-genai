from app.models.schemas import Candidate, QueryIntent
from app.services.dataset_loader import get_candidate_search_data
from app.services.filters import apply_filters


def get_candidates(intent: QueryIntent) -> list[Candidate]:
    """Retrieve ranked candidate results using cleaned Week 2 datasets."""
    filtered = apply_filters(get_candidate_search_data(), intent)

    results: list[Candidate] = []
    for _, row in filtered.iterrows():
        results.append(
            Candidate(
                candidate_id=int(row["candidate_id"]),
                name=str(row["name"]).title(),
                skills=_split_values(row["skills"]),
                experience_years=float(row["experience_years"]),
                education=str(row["education"]),
                projects=_split_values(row["projects"]),
                job_id=int(row["job_id"]),
                role=str(row["role"]).title(),
                status=str(row["status"]).title(),
                score=float(row["score"]),
                label=str(row["label"]).title(),
            )
        )

    return results


def _split_values(value: object) -> list[str]:
    """Turn pipe-separated dataset fields into clean response lists."""
    return [part.strip() for part in str(value).split("|") if part.strip()]
