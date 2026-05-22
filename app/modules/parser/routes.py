"""Parser routes — owned by G1. W1 stub returns a hardcoded shape.

G1 replaces the stub body in W2 with real PDF/DOCX extraction and
the parser_main prompt.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/parse", tags=["parser"])


@router.post("")
def parse_resume() -> dict:
    # W1 mock contract - same JSON shape the real endpoint will return.
    return {
        "name": "Sample Candidate",
        "email": "sample@example.com",
        "phone": None,
        "skills": ["Python", "FastAPI"],
        "experience_years": 3.0,
        "education": "B.Tech, Sample Institute",
        "projects": ["Sample project"],
        "summary": "Stub response from W1. G1 replaces this in W2.",
        "parse_confidence": 0.0,
    }
