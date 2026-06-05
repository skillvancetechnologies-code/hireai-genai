# G1 — Resume Parser Module

## Endpoint

**POST** `/parse`

Accepts a resume file and returns a structured candidate JSON record.

---

## Request

- **Content-Type:** `multipart/form-data`
- **Field:** `file` — the resume file to parse

**Supported file types:** PDF, DOCX, DOC, JPG, JPEG, PNG

---

## Response

```json
{
  "name": "string",
  "email": "string or null",
  "phone": "string or null",
  "skills": ["array of strings"],
  "experience_years": 0.0,
  "education": "string",
  "projects": ["array of strings"],
  "raw_text": "string",
  "summary": "string",
  "parse_confidence": 0.95
}
```

---

## Error Responses

| Code | Reason |
|---|---|
| 400 | File is empty or no text could be extracted |
| 415 | Unsupported file type |
| 422 | LLM failed to parse after 3 attempts |
| 500 | Internal server error |

---

## Example

```bash
curl -X POST http://localhost:8001/parse \
  -F "file=@resume.pdf"
```

---

## Database Integration

The web team should POST the parsed response to `/api/candidates` with this exact shape:

```json
{
  "name": "string",
  "email": "string or null",
  "phone": "string or null",
  "skills": ["array of strings"],
  "experience_years": 0.0,
  "education": "string",
  "projects": ["array of strings"],
  "raw_text": "string",
  "summary": "string",
  "parse_confidence": 0.95
}
```

All fields except `email` and `phone` are required.

---

## Notes
- Skills are automatically normalized (React.js → React, Postgres → PostgreSQL)
- Email is optional — returns null if missing or malformed
- parse_confidence below 0.5 indicates low quality input
- JPG/PNG support requires Tesseract OCR installed on the server