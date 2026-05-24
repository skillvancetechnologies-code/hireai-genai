"""Parser routes — owned by G1.

POST /parse — accepts a PDF or DOCX file upload and returns a
ParsedCandidate JSON record validated by Pydantic.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.modules.parser.service import parse_resume_file

log = logging.getLogger(__name__)
router = APIRouter(prefix="/parse", tags=["parser"])

_ALLOWED_SUFFIXES = {".pdf", ".docx"}


@router.post("")
async def parse_resume(file: UploadFile = File(...)) -> dict:
    """Parse a resume file and return a structured candidate record.

    Accepts: multipart/form-data with field `file` (PDF or DOCX).
    Returns: ParsedCandidate JSON.
    """
    suffix = Path(file.filename or "upload.bin").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Upload a .pdf or .docx file.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        return parse_resume_file(tmp_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        log.exception("parse_resume failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=500, detail="Resume parsing failed — please try again.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
