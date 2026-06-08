"""G2 AI Copilot schemas."""

from typing import Any

from pydantic import BaseModel, Field

from app.models.schemas import Candidate, CopilotResponse, QueryIntent  # noqa: F401


class CopilotRequest(BaseModel):
    """Incoming G2 recruiter query."""

    query: str = Field(
        ...,
        examples=["Show top 5 Good Fit Python developers"],
    )
    history: list[dict[str, Any]] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "Last 5 conversation turns. Query-only history is supported for "
            "pronoun follow-ups."
        ),
        examples=[
            [
                {
                    "query": "Find candidates experienced in AI chatbot projects",
                }
            ]
        ],
    )
