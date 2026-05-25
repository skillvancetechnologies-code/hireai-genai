from fastapi import APIRouter
from app.modules.explain.schemas import ExplainRequest, ExplainResponse
from app.modules.explain.generator import generate_explanation

router = APIRouter(prefix="/explain", tags=["Explain"])

@router.post("/", response_model=ExplainResponse)
def explain_candidate(request: ExplainRequest):
    return generate_explanation(
        request.candidate_id,
        request.job_id
    )