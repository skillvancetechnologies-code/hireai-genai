"""Copilot routes — owned by G2. W1 stub returns a hardcoded shape."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/copilot", tags=["copilot"])


class CopilotRequest(BaseModel):
    query: str
    history: list[dict] | None = None
    job_context: str | None = None


@router.post("")
def copilot_query(req: CopilotRequest) -> dict:
    # W1 mock contract.
    return {
        "candidates": [],
        "summary": f"Stub response for query: {req.query!r}. G2 replaces this in W2.",
        "query_interpreted": {
            "type": "filter",
            "skills_required": [],
            "top_k": 10,
        },
    }
