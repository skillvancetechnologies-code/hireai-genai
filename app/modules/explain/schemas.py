from pydantic import BaseModel
from pydantic import Field
from typing import Any, List


class ExplainRequest(BaseModel):
    candidate_id: str
    job_id: str


class ShapDriver(BaseModel):
    feature: str
    shap_value: float


class ShapValues(BaseModel):
    feature_names: List[str]
    values: List[float]
    raw_or_normalized: str
    positive_means: str
    predicted_class_index: int | None = None
    base_value: float | None = None


class ExplainResponse(BaseModel):
    candidate_id: str
    job_id: str
    explanation_text: str
    top_strengths: List[str]
    top_gaps: List[str]
    shap_values: ShapValues | None = None
    top_positive_drivers: List[ShapDriver] = Field(default_factory=list)
    top_negative_drivers: List[ShapDriver] = Field(default_factory=list)
    model_version: str | None = None
    generated_at: str | None = None
    score_metadata: dict[str, Any] = Field(default_factory=dict)
