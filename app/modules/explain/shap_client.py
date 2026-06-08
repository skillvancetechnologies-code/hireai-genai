from __future__ import annotations

from typing import Any
from datetime import datetime

import requests

from app.core.config import get_settings


CLASSIFICATION_POSITIVE_MEANING = "increases probability of predicted class"
LOCAL_MODEL_VERSION = "local-shap-v1"
CLASSIFICATION_FEATURE_NAMES = [
    "skills",
    "experience_years",
    "education",
    "projects",
    "role",
    "required_skills",
    "min_experience",
    "num_candidate_skills",
    "num_required_skills",
    "application_date_year",
    "application_date_month",
    "application_date_weekday",
    "application_date_quarter",
    "application_date_is_weekend",
]


def get_shap_explanation(candidate: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    payload = _build_ml_payload(candidate)

    if settings.ml_score_base_url:
        try:
            response = requests.post(
                f"{settings.ml_score_base_url.rstrip('/')}/explain",
                json=payload,
                timeout=3,
            )
            response.raise_for_status()
            return _normalize_ml_response(response.json(), candidate)
        except requests.RequestException:
            pass

    return _build_local_shap_response(candidate)


def _build_ml_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": _coerce_int(candidate["candidate_id"]),
        "job_id": _coerce_int(candidate["job_id"]),
        "features": {
            "experience_years": candidate["candidate_exp"],
            "education": candidate.get("education", ""),
            "skills": candidate.get("skills", ""),
            "projects": candidate.get("projects", ""),
            "role": candidate.get("role", candidate["job_title"]),
            "required_skills": candidate.get("required_skills", ""),
            "num_candidate_skills": candidate.get("num_candidate_skills", 0),
            "num_required_skills": candidate.get("num_required_skills", 0),
            "min_experience": candidate["required_exp"],
            "application_date": candidate.get("application_date", "unknown"),
        },
    }


def _normalize_ml_response(data: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    shap_values = data.get("shap_values") or {}
    feature_names = shap_values.get("feature_names") or []
    values = [float(value) for value in shap_values.get("values", [])]
    drivers = _rank_drivers(feature_names, values)

    return {
        "model_version": data.get("model") or LOCAL_MODEL_VERSION,
        "score_metadata": {
            "predicted_label": data.get("predicted_label", candidate["label"]),
            "confidence": data.get("confidence"),
            "probabilities": data.get("probabilities", {}),
            "raw_or_normalized": shap_values.get("raw_or_normalized", "raw"),
        },
        "shap_values": {
            "feature_names": feature_names,
            "values": values,
            "raw_or_normalized": shap_values.get("raw_or_normalized", "raw"),
            "positive_means": shap_values.get(
                "positive_means",
                CLASSIFICATION_POSITIVE_MEANING,
            ),
            "predicted_class_index": shap_values.get("predicted_class_index"),
            "base_value": shap_values.get("base_value"),
        },
        "top_positive_drivers": data.get("top_positive_drivers") or drivers["positive"],
        "top_negative_drivers": data.get("top_negative_drivers") or drivers["negative"],
    }


def _build_local_shap_response(candidate: dict[str, Any]) -> dict[str, Any]:
    date_parts = _application_date_parts(candidate.get("application_date"))
    required_count = max(float(candidate.get("required_count", 0)), 1.0)
    matched_count = float(candidate.get("matched_count", 0))
    missing_count = max(required_count - matched_count, 0)
    experience_gap = max(candidate.get("required_exp", 0) - candidate.get("candidate_exp", 0), 0)

    feature_values = {
        "skills": _scale(candidate.get("skills_match", 0)),
        "experience_years": _scale(candidate.get("experience_score", 0)),
        "education": 0.0,
        "projects": _scale(candidate.get("project_score", 0)),
        "role": 0.0,
        "required_skills": round(matched_count / required_count, 4),
        "min_experience": -_scale(experience_gap * 10),
        "num_candidate_skills": round(float(candidate.get("num_candidate_skills", 0)) / 100, 4),
        "num_required_skills": -round(missing_count / required_count, 4),
        "application_date_year": date_parts["year"],
        "application_date_month": date_parts["month"],
        "application_date_weekday": date_parts["weekday"],
        "application_date_quarter": date_parts["quarter"],
        "application_date_is_weekend": date_parts["is_weekend"],
    }
    feature_names = CLASSIFICATION_FEATURE_NAMES
    values = [feature_values[feature] for feature in feature_names]
    drivers = _rank_drivers(feature_names, values)

    return {
        "model_version": LOCAL_MODEL_VERSION,
        "score_metadata": {
            "predicted_label": candidate.get("label", "unknown"),
            "confidence": None,
            "probabilities": {},
            "raw_or_normalized": "raw",
        },
        "shap_values": {
            "feature_names": feature_names,
            "values": values,
            "raw_or_normalized": "raw",
            "positive_means": CLASSIFICATION_POSITIVE_MEANING,
            "predicted_class_index": None,
            "base_value": None,
        },
        "top_positive_drivers": drivers["positive"],
        "top_negative_drivers": drivers["negative"],
    }


def _rank_drivers(feature_names: list[str], values: list[float]) -> dict[str, list[dict[str, Any]]]:
    pairs = [
        {"feature": feature, "shap_value": round(value, 4)}
        for feature, value in zip(feature_names, values)
    ]
    positives = sorted(
        [item for item in pairs if item["shap_value"] > 0],
        key=lambda item: abs(item["shap_value"]),
        reverse=True,
    )[:3]
    negatives = sorted(
        [item for item in pairs if item["shap_value"] < 0],
        key=lambda item: abs(item["shap_value"]),
        reverse=True,
    )[:3]
    return {"positive": positives, "negative": negatives}


def _scale(value: float) -> float:
    return round(float(value) / 100, 4)


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _application_date_parts(value: Any) -> dict[str, float]:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return {
            "year": 0.0,
            "month": 0.0,
            "weekday": 0.0,
            "quarter": 0.0,
            "is_weekend": 0.0,
        }

    return {
        "year": round(parsed.year / 10000, 4),
        "month": round(parsed.month / 12, 4),
        "weekday": round(parsed.weekday() / 6, 4),
        "quarter": round(((parsed.month - 1) // 3 + 1) / 4, 4),
        "is_weekend": 1.0 if parsed.weekday() >= 5 else 0.0,
    }
