from pydantic import BaseModel
from typing import List


class ExplainRequest(BaseModel):
    candidate_id: str
    job_id: str


class ExplainResponse(BaseModel):
    candidate_id: str
    job_id: str
    explanation_text: str
    top_strengths: List[str]
    top_gaps: List[str]