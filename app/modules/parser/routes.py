import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.modules.parser.extract import extract_text
from app.modules.parser.schemas import ParsedCandidate
from app.core.llm import llm_call

router = APIRouter()

PARSER_PROMPT = """You are a recruitment data extraction system. Read the resume below and extract structured fields. Return ONLY valid JSON matching this exact schema:

{{
  "name": "string",
  "email": "string",
  "phone": "string or null",
  "skills": ["array of strings, technical skills only, no soft skills"],
  "experience_years": 0,
  "education": "highest degree + institution, e.g. B.Tech, IIT Madras",
  "projects": ["array of project titles, max 5"],
  "summary": "1-2 sentences on what this candidates strengths are",
  "parse_confidence": 0.9
}}

Rules:
- If experience years are not explicitly stated, infer from earliest job date.
- Normalize skills: React.js becomes React, Postgres becomes PostgreSQL.
- DO NOT include soft skills like teamwork or leadership in the skills array.
- If the email is missing or malformed, return parse_confidence below 0.5.
- Output JSON only. No markdown, no explanation.

Resume:
{resume_text}
"""


def parse_resume_with_llm(resume_text: str) -> ParsedCandidate:
    prompt = PARSER_PROMPT.format(resume_text=resume_text)
    last_error = None

    for attempt in range(3):
        if attempt > 0:
            prompt = PARSER_PROMPT.format(resume_text=resume_text)
            prompt += f"\n\nIMPORTANT: Your previous output was invalid. Error: {last_error}. Fix it and return valid JSON only."

        raw = llm_call(prompt=prompt, json_mode=True, temperature=0.1)

        try:
            data = json.loads(raw)
            data["raw_text"] = resume_text
            return ParsedCandidate(**data)
        except Exception as e:
            last_error = str(e)
            continue

    raise HTTPException(
        status_code=422,
        detail=f"Failed to parse resume after 3 attempts. Last error: {last_error}"
    )


@router.post("/parse", response_model=ParsedCandidate)
async def parse_resume(file: UploadFile = File(...)):
    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        resume_text = extract_text(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract any text from the file.")

    return parse_resume_with_llm(resume_text)