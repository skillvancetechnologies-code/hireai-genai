from typing import Literal

from pydantic import BaseModel, Field


class CopilotRequest(BaseModel):
    """Incoming recruiter query."""

    query: str = Field(
        ...,
        examples=["Show top 5 Good Fit Python developers"],
    )


class QueryIntent(BaseModel):
    """Structured filter specification extracted from recruiter text."""

    type: Literal["filter"] = "filter"
    job_id: int | None = Field(default=None, gt=0, examples=[1])
    skills_required: list[str] = Field(default_factory=list, examples=[["Python"]])
    min_experience: float | None = Field(default=None, ge=0, examples=[2])
    label_filter: str | None = Field(default=None, examples=["Good Fit"])
    status_filter: str | None = Field(default=None, examples=["Shortlisted"])
    top_k: int = Field(default=10, gt=0, le=50, examples=[5])
    free_text: str = ""


class Candidate(BaseModel):
    """Candidate result assembled from cleaned Week 2 datasets."""

    candidate_id: int
    name: str
    skills: list[str]
    experience_years: float
    education: str
    projects: list[str]
    job_id: int
    role: str
    status: str
    score: float
    label: str


class CopilotResponse(BaseModel):
    """Successful copilot response."""

    query_interpreted: QueryIntent
    candidates: list[Candidate]
    summary: str
