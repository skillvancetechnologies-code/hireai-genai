from functools import lru_cache
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[3] / "data"

REQUIRED_COLUMNS = {
    "candidates.csv": {
        "candidate_id",
        "name",
        "skills",
        "experience_years",
        "education",
        "projects",
    },
    "jobs.csv": {"job_id", "role", "required_skills", "min_experience"},
    "applications.csv": {"candidate_id", "job_id", "status"},
    "scores.csv": {"candidate_id", "job_id", "score", "label"},
}


class DatasetValidationError(RuntimeError):
    """Raised when a required Week 2 dataset cannot be loaded safely."""


@lru_cache(maxsize=1)
def get_candidate_search_data() -> pd.DataFrame:
    """Load and join the four cleaned datasets into searchable results."""
    candidates = _load_csv("candidates.csv")
    jobs = _load_csv("jobs.csv")
    applications = _load_csv("applications.csv")
    scores = _load_csv("scores.csv")

    try:
        joined = applications.merge(
            scores,
            on=["candidate_id", "job_id"],
            how="inner",
        )
        joined = joined.merge(
            candidates,
            on="candidate_id",
            how="inner",
            validate="many_to_one",
        )
        joined = joined.merge(jobs, on="job_id", how="inner", validate="many_to_one")
    except pd.errors.MergeError as exc:
        raise DatasetValidationError(
            "Cleaned datasets contain duplicate IDs and cannot be joined."
        ) from exc

    if joined.empty:
        raise DatasetValidationError("Cleaned datasets produced no joined records.")

    return joined


def _load_csv(filename: str) -> pd.DataFrame:
    """Load a CSV and ensure required columns exist before filtering."""
    path = DATA_DIR / filename
    if not path.exists():
        raise DatasetValidationError(f"Required dataset is missing: {filename}.")

    try:
        dataframe = pd.read_csv(path)
    except Exception as exc:
        raise DatasetValidationError(f"Could not read dataset: {filename}.") from exc

    missing = REQUIRED_COLUMNS[filename] - set(dataframe.columns)
    if missing:
        columns = ", ".join(sorted(missing))
        raise DatasetValidationError(
            f"Dataset {filename} is missing required columns: {columns}."
        )

    return dataframe
