from fastapi import APIRouter, HTTPException, status

from app.models.schemas import CopilotRequest, CopilotResponse
from app.modules.copilot.intent import IntentParseError
from app.modules.copilot.pipeline import run_copilot
from app.modules.copilot.retriever import SemanticSearchError, build_faiss_index
from app.services.dataset_loader import DatasetValidationError


router = APIRouter(tags=["copilot"])


@router.post("/copilot", response_model=CopilotResponse)
def copilot(request: CopilotRequest) -> CopilotResponse:
    """Route recruiter queries to structured filtering or semantic FAISS search."""
    try:
        response = run_copilot(request.query)
    except IntentParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SemanticSearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except DatasetValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    if not response.candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No candidates match the requested search.",
        )

    return response


@router.post("/copilot/reindex")
def reindex(limit: int | None = None) -> dict[str, int | str]:
    """Rebuild the FAISS index on demand for Week 3 semantic search."""
    try:
        return build_faiss_index(limit=limit)
    except (SemanticSearchError, DatasetValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
