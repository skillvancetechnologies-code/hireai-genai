from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[1] / "data"

REQUIRED_COLUMNS = {
    "candidates_cleaned.csv": {
        "candidate_id",
        "name",
        "skills",
        "experience_years",
        "education",
        "projects",
    },
    "jobs_cleaned.csv": {"job_id", "role", "required_skills", "min_experience"},
    "applications_cleaned.csv": {"candidate_id", "job_id", "status"},
    "scores_cleaned.csv": {"candidate_id", "job_id", "score", "label"},
}

# Cached frames keyed by name, each stored with the dataset version it was
# built from so edits to the CSVs are picked up without restarting the app.
_cache: dict[str, tuple[tuple, pd.DataFrame]] = {}


class DatasetValidationError(RuntimeError):
    """Raised when a required Week 2 dataset cannot be loaded safely."""


def get_dataset_version() -> tuple:
    """Snapshot of (mtime, size) for every dataset file, in a stable order."""
    return tuple(_file_stamp(DATA_DIR / name) for name in sorted(REQUIRED_COLUMNS))


def get_candidates_data() -> pd.DataFrame:
    """Load the cleaned candidate profile dataset."""
    return _cached("candidates", lambda: _load_csv("candidates_cleaned.csv"))


def get_jobs_data() -> pd.DataFrame:
    """Load the cleaned jobs dataset."""
    return _cached("jobs", lambda: _load_csv("jobs_cleaned.csv"))


def get_candidate_search_data() -> pd.DataFrame:
    """Load and join the four cleaned datasets into searchable results."""
    return _cached("search", _build_search_data)


def _build_search_data() -> pd.DataFrame:
    candidates = get_candidates_data()
    jobs = get_jobs_data()
    applications = _load_csv("applications_cleaned.csv")
    scores = _load_csv("scores_cleaned.csv")

    try:
        joined = applications.merge(
            scores,
            on=["candidate_id", "job_id"],
            how="inner",
            validate="one_to_one",
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


def _cached(key: str, builder) -> pd.DataFrame:
    version = get_dataset_version()
    entry = _cache.get(key)
    if entry is not None and entry[0] == version:
        return entry[1]

    frame = builder()
    _cache[key] = (version, frame)
    return frame


def _file_stamp(path: Path) -> tuple | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


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
