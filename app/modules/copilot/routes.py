from fastapi import APIRouter, HTTPException, status

from app.modules.copilot.schemas import CopilotRequest, CopilotResponse, QueryIntent
from app.modules.copilot.candidate_service import get_candidates
from app.modules.copilot.dataset_loader import DatasetValidationError
from app.modules.copilot.intent_parser import IntentParseError, parse_query


router = APIRouter(tags=["copilot"])


@router.post(
    "/copilot",
    response_model=CopilotResponse,
    responses={
        200: {
            "description": "Candidates matching the parsed filters.",
            "content": {
                "application/json": {
                    "example": {
                        "query_interpreted": {
                            "type": "filter",
                            "job_id": None,
                            "skills_required": ["Python"],
                            "min_experience": None,
                            "label_filter": "Good Fit",
                            "status_filter": None,
                            "top_k": 5,
                            "free_text": "",
                        },
                        "candidates": [
                            {
                                "candidate_id": 23478,
                                "name": "Ayesha Li",
                                "skills": [
                                    "kubernetes",
                                    "mlflow",
                                    "onnx",
                                    "pytorch",
                                    "python",
                                    "sql",
                                    "seaborn",
                                    "spark",
                                ],
                                "experience_years": 8.0,
                                "education": "b.sc computer science",
                                "projects": [
                                    "iot data ingestion system with spark streaming",
                                    "blockchain-based supply chain tracking system",
                                    "data pipeline for real-time analytics dashboard",
                                ],
                                "job_id": 6,
                                "role": "Machine Learning Engineer",
                                "status": "Shortlisted",
                                "score": 99.1,
                                "label": "Good Fit",
                            },
                            {
                                "candidate_id": 29079,
                                "name": "Sneha Girma",
                                "skills": [
                                    "aws",
                                    "excel",
                                    "hadoop",
                                    "kafka",
                                    "python",
                                    "sql",
                                    "snowflake",
                                    "spark",
                                    "dbt",
                                ],
                                "experience_years": 6.0,
                                "education": "b.tech computer science",
                                "projects": [
                                    "kafka-based event streaming data platform",
                                    "restful api for inventory management system",
                                ],
                                "job_id": 8,
                                "role": "Data Engineer",
                                "status": "Applied",
                                "score": 97.7,
                                "label": "Good Fit",
                            },
                            {
                                "candidate_id": 43347,
                                "name": "Chidi Kobayashi",
                                "skills": [
                                    "aws",
                                    "airflow",
                                    "databricks",
                                    "hadoop",
                                    "jira",
                                    "kafka",
                                    "python",
                                    "sql",
                                    "dbt",
                                ],
                                "experience_years": 5.0,
                                "education": "b.tech electrical engineering",
                                "projects": [
                                    "real-time stock market data ingestion pipeline",
                                    "portfolio risk assessment using python and ml",
                                    "data pipeline for real-time analytics dashboard",
                                ],
                                "job_id": 8,
                                "role": "Data Engineer",
                                "status": "Hired",
                                "score": 97.2,
                                "label": "Good Fit",
                            },
                            {
                                "candidate_id": 35119,
                                "name": "Haruto Rodriguez",
                                "skills": [
                                    "kubernetes",
                                    "mlflow",
                                    "onnx",
                                    "pytorch",
                                    "python",
                                    "ray",
                                    "sql",
                                    "spark",
                                    "tensorflow",
                                ],
                                "experience_years": 10.0,
                                "education": "m.tech data engineering",
                                "projects": [
                                    "nlp-based resume parser and classifier",
                                    "automated testing framework for web applications",
                                ],
                                "job_id": 6,
                                "role": "Machine Learning Engineer",
                                "status": "Interviewed",
                                "score": 96.3,
                                "label": "Good Fit",
                            },
                            {
                                "candidate_id": 4631,
                                "name": "Fang Thompson",
                                "skills": [
                                    "bdd",
                                    "jira",
                                    "postman",
                                    "pytest",
                                    "python",
                                    "rest api",
                                    "selenium",
                                ],
                                "experience_years": 3.0,
                                "education": "m.tech information security",
                                "projects": [
                                    "chatbot for customer support using llm fine-tuning",
                                    "cross-platform mobile app for expense tracking",
                                ],
                                "job_id": 9,
                                "role": "Qa Engineer",
                                "status": "Shortlisted",
                                "score": 95.9,
                                "label": "Good Fit",
                            },
                        ],
                        "summary": (
                            "Found top 5 Good Fit candidates skilled in Python, "
                            "ranked by score."
                        ),
                    }
                }
            },
        },
        400: {
            "description": "Invalid or unsupported recruiter query.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "Could not understand the filters in this "
                            "recruiter query."
                        )
                    }
                }
            },
        },
        404: {
            "description": "No candidates found for the requested job.",
            "content": {
                "application/json": {
                    "example": {"detail": "No candidates match the requested filters."}
                }
            },
        },
        500: {
            "description": "Dataset configuration problem.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Required dataset is missing: candidates_cleaned.csv."
                    }
                }
            },
        },
    },
)
def copilot(request: CopilotRequest) -> CopilotResponse:
    """
    Parse recruiter language and search the cleaned Week 2 candidate datasets.
    """
    try:
        interpreted_query = parse_query(request.query)
    except IntentParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        candidates = get_candidates(interpreted_query)
    except DatasetValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No candidates match the requested filters.",
        )

    return CopilotResponse(
        query_interpreted=interpreted_query,
        candidates=candidates,
        summary=_build_summary(interpreted_query, len(candidates)),
    )


def _build_summary(intent: QueryIntent, result_count: int) -> str:
    """Describe exactly which structured filters produced the result set."""
    filters: list[str] = []
    if intent.label_filter:
        filters.append(intent.label_filter)
    if intent.status_filter:
        filters.append(intent.status_filter)
    filters.append("candidates")
    if intent.skills_required:
        filters.append(f"skilled in {', '.join(intent.skills_required)}")
    if intent.min_experience is not None:
        filters.append(f"with at least {intent.min_experience:g} years experience")
    if intent.job_id is not None:
        filters.append(f"for job {intent.job_id}")
    if intent.free_text:
        filters.append(f"matching '{intent.free_text}'")

    return (
        f"Found top {result_count} {' '.join(filters)}, "
        "ranked by score."
    )
