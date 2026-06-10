# GenAI Service — Integration Handoff (Week 4)

**Audience:** Web team (W1 candidate drawer, W3 chat UI, W6 proxy layer) and PM.
**From:** GenAI team (G4 on behalf of G1/G2/G3).
**Service base URL:** `http://localhost:8001` (FastAPI; deploy host/port via `SERVICE_HOST`/`SERVICE_PORT`).

Live, always-current contract: **`http://localhost:8001/docs`** (Swagger UI) and
`http://localhost:8001/openapi.json`. The shapes below are a snapshot of that spec.

Health check for your proxy: `GET /health` → `{"status": "ok"}`.

---

## 1. POST /parse — Resume Parser (G1) — for W6 proxy → DB insert

`multipart/form-data`, field `file`. Accepts PDF, DOCX, DOC, JPG, PNG.

```bash
curl -X POST http://localhost:8001/parse -F "file=@resume.pdf"
```

Response — `ParsedCandidate` (insert into candidates table via your `/api/candidates`):

```json
{
  "name": "string",
  "email": "string|null",
  "phone": "string|null",
  "skills": ["normalized skill names"],
  "experience_years": 4.5,
  "education": "string",
  "projects": ["string"],
  "raw_text": "full extracted text (audit)",
  "summary": "1-2 sentence card snippet",
  "parse_confidence": 0.92
}
```

Errors: `415` unsupported file type, `422` empty/unreadable file (message in `detail`),
`500` parse failure (safe message, no stack trace).

## 2. POST /copilot — AI Copilot (G2) — for W3 chat UI

```json
{
  "query": "Show top 5 Good Fit Python developers",
  "history": [ { "query": "previous turn" } ]   // optional, last 5 turns max
}
```

Response:

```json
{
  "query_interpreted": {
    "type": "filter|semantic", "job_id": 1, "skills_required": ["Python"],
    "min_experience": 2, "label_filter": "Good Fit", "status_filter": null,
    "top_k": 5, "free_text": ""
  },
  "candidates": [
    { "candidate_id": 1003, "name": "...", "skills": [], "experience_years": 3,
      "education": "...", "projects": [], "job_id": 1, "role": "...",
      "status": "...", "score": 78.5, "label": "Good Fit" }
  ],
  "summary": "2-3 sentence recruiter-friendly summary",
  "conversation_context_used": false
}
```

Errors: `400` query empty / couldn't be understood (show `detail` as the friendly
"try rephrasing" message), `404` no candidates matched, `503` semantic index unavailable.

**Suggested-chip queries for the chat UI** (the 5 flagship queries we guarantee):

1. Show top 5 Python developers for JOB0012
2. Who has React and Node.js with 2+ years of experience?
3. Compare top 3 candidates for the ML Engineer role
4. List all Good Fit candidates for JOB0003
5. Which roles have the biggest skill gap right now?

Maintenance endpoint (not for UI): `POST /copilot/reindex` rebuilds the FAISS index.

## 3. POST /explain — Explainable AI (G3) — for W1 candidate drawer

```json
{ "candidate_id": "1003", "job_id": "3" }
```

Response:

```json
{
  "candidate_id": "1003",
  "job_id": "3",
  "explanation_text": "3-4 neutral sentences",
  "top_strengths": ["Python (5y exp)", "SQL"],
  "top_gaps": ["Kafka"],
  "shap_values": {
    "feature_names": ["skills_match", "exp_score"],
    "values": [0.42, 0.18],
    "raw_or_normalized": "normalized",
    "positive_means": "pushes score up",
    "predicted_class_index": 1,
    "base_value": 0.5
  },
  "top_positive_drivers": [ { "feature": "skills_match", "shap_value": 0.42 } ],
  "top_negative_drivers": [ { "feature": "exp_gap", "shap_value": -0.11 } ],
  "model_version": "v1",
  "generated_at": "ISO timestamp",
  "score_metadata": {}
}
```

**ID space:** real dataset IDs resolve — candidates `"1001"`+ (50,000 loaded from
`candidates.csv`) and jobs `"1"`–`"10"`. Both fields are strings. Unknown IDs
return an in-schema response with `explanation_text: "Candidate not found"` /
`"Job not found"` rather than an HTTP error — check for that in the drawer.

Note: the route was `/explain/` (trailing slash) until today; it is now exactly
`/explain`. Old `/explain/` calls still work via 307 redirect, but point proxies
at `/explain`.

## 4. GET /dashboard/costs and /dashboard/evals — for PM

- `GET /dashboard/costs?days=7` — daily LLM spend/call/cache-hit trend, project
  total vs the $200 cap, budget status.
- `GET /dashboard/evals` — latest nightly eval accuracy per module + regression flags.

Read-only JSON; safe to poll or wire into any internal admin page.

---

## Operational notes for the proxy (W6)

- **Latency:** cache hits return in <500ms; cache misses run a local LLM and can
  take seconds (budgets: parse <3s, copilot <4s, explain <3s). Set proxy timeouts
  to ≥30s rather than the usual 5s.
- **Failures:** every error returns JSON `{"detail": "..."}` with a safe message —
  never a stack trace. `4xx` = caller/input issue, `503` = retry later, `500` = our bug.
- **Resilience:** LLM calls fall back automatically (local primary → Gemini Flash →
  local backup); you do not need provider-level retry logic in the proxy. Idempotent
  retries on `503` are fine — responses are cached, so retries are cheap.
- **CORS:** not enabled — we assume server-side proxying, not browser-direct calls.
  Tell us if you need browser-direct access.
