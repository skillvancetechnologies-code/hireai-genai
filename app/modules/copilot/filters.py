import re

import pandas as pd

from app.models.schemas import QueryIntent


IGNORED_FREE_TEXT_WORDS = {
    "candidate",
    "candidates",
    "developer",
    "developers",
    "experience",
    "for",
    "me",
    "profiles",
    "show",
    "top",
    "with",
    "years",
}


def apply_filters(dataframe: pd.DataFrame, intent: QueryIntent) -> pd.DataFrame:
    """Apply structured intent filters and return highest-scoring candidates."""
    filtered = dataframe.copy()

    if intent.job_id is not None:
        filtered = filtered[filtered["job_id"] == intent.job_id]

    if intent.min_experience is not None:
        filtered = filtered[
            filtered["experience_years"] >= intent.min_experience
        ]

    if intent.label_filter:
        filtered = filtered[
            filtered["label"].str.casefold() == intent.label_filter.casefold()
        ]

    if intent.status_filter:
        filtered = filtered[
            filtered["status"].str.casefold() == intent.status_filter.casefold()
        ]

    for skill in intent.skills_required:
        filtered = filtered[
            filtered["skills"].fillna("").apply(
                lambda values: _contains_pipe_value(values, skill)
            )
        ]

    keywords = _meaningful_keywords(intent.free_text)
    for keyword in keywords:
        searchable = (
            filtered["role"].fillna("")
            + " "
            + filtered["skills"].fillna("")
            + " "
            + filtered["projects"].fillna("")
        )
        filtered = filtered[
            searchable.str.contains(re.escape(keyword), case=False, regex=True)
        ]

    return (
        filtered.sort_values("score", ascending=False)
        .drop_duplicates(subset=["candidate_id"])
        .head(intent.top_k)
    )


def _contains_pipe_value(values: str, expected: str) -> bool:
    """Match a skill as a full pipe-separated value, case-insensitively."""
    available = {skill.strip().casefold() for skill in str(values).split("|")}
    return expected.strip().casefold() in available


def _meaningful_keywords(free_text: str) -> list[str]:
    """Ignore generic recruiter words while keeping role-search terms."""
    return [
        word
        for word in re.findall(r"[a-zA-Z]+", free_text.casefold())
        if word not in IGNORED_FREE_TEXT_WORDS
    ]
