"""Explain routes — owned by G3. W1 stub returns a hardcoded shape."""
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/explain", tags=["explain"])


class ExplainRequest(BaseModel):
    candidate_id: str
    job_id: str


@router.post("")
def explain_score(req: ExplainRequest) -> dict:
    # W1 mock contract.
    return {
        "candidate_id": req.candidate_id,
        "job_id": req.job_id,
        "explanation_text": (
            "Stub explanation from W1. G3 replaces this in W2 with a real "
            "LLM-generated 3-4 sentence rationale."
        ),
        "top_strengths": [],
        "top_gaps": [],
        "shap_values": [],
        "model_version": "stub-v0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
