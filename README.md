# HireAI GenAI

AI-powered resume parsing, recruiter copilot, and explainable scoring — all running locally via Ollama (no API keys required).

```
hireai-genai/
├── app/
│   ├── main.py                 # FastAPI app, mounts all 3 routers
│   ├── core/                   # G4 owns — shared infra
│   │   ├── config.py           #   env vars + settings
│   │   ├── llm.py              #   the ONE LLM wrapper (Ollama)
│   │   ├── cache.py            #   Redis (with in-memory fallback)
│   │   ├── cost.py             #   per-call token/cost tracking
│   │   ├── prompts.py          #   prompt library loader
│   │   └── eval.py             #   eval runner framework
│   ├── modules/
│   │   ├── parser/             # G1 — resume → JSON
│   │   ├── copilot/            # G2 — recruiter query engine
│   │   └── explain/            # G3 — score explanation
│   └── prompts/
│       └── library.yaml        # all prompts live here (versioned)
├── data/
│   ├── eval_sets/              # gold cases per module
│   └── eval_results/           # nightly run outputs
├── scripts/
│   ├── run_evals.py            # nightly eval runner
│   ├── nightly.py              # evals + cost summary + Slack alerts
│   └── cost_summary.py         # daily spend report
├── .env.example
├── requirements.txt
└── README.md
```

---

## Setup & Run Instructions

### 1 — Install Ollama (one-time per machine)

```bash
# Windows: download the installer from https://ollama.com/download
# Mac:
brew install ollama

# Linux:
curl -fsSL https://ollama.com/install.sh | sh
```

### 2 — Pull the default model

```bash
# Downloads gemma3:4b (~2.5 GB). Only needed once.
ollama pull gemma3:4b

# Verify Ollama is running (it starts as a background service after install)
curl http://localhost:11434/api/tags
```

### 3 — Configure environment

```bash
# Copy the example file — no API keys needed
cp .env.example .env

# Open .env and optionally:
#   - Change PARSER_MODEL to gemma3:12b or gemma3:27b for higher accuracy (needs more RAM)
#   - Set REDIS_URL if Redis is on a non-default host
#   - Set SLACK_WEBHOOK_URL for nightly cost/regression alerts
```

### 4 — Install Python dependencies

```bash
# Python 3.11+ recommended
pip install -r requirements.txt
```

### 5 — (Optional) Start Redis for persistent caching

```bash
# Without Redis the service falls back to in-memory cache automatically.
# No data is lost — just no cache persistence across restarts.
docker compose up -d redis
```

### 6 — Start the FastAPI server

```bash
# Starts on port 8001. --reload restarts on every file save (dev mode).
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 7 — Verify the service is up

```bash
# Should return {"status": "ok"}
curl http://localhost:8001/healthz

# Should return Redis status — "ok" if connected, "degraded" if using memory fallback
curl http://localhost:8001/readyz

# Open the interactive API docs in a browser
# http://localhost:8001/docs
```

### 8 — Run the test suite

```bash
pytest app/tests/ -v
```

### 9 — Run the parser eval (optional)

```bash
# Place benchmark PDFs in data/eval_sets/parser_resumes/ first (filenames must
# match the "input" field in data/eval_sets/parser.json)
python scripts/run_evals.py --all
```

### 10 — Nightly automation

```bash
# Runs evals + posts cost summary + regression alerts to Slack
python scripts/nightly.py

# Cron line (add to server crontab):
# 0 6 * * * cd /path/to/hireai-genai && .venv/bin/python scripts/nightly.py
```

### Switching models

Edit `.env` and restart the server — no code changes needed.

| Model | RAM needed | Notes |
|---|---|---|
| `gemma3:4b` | ~4 GB | Default — fast, good JSON following |
| `gemma3:12b` | ~8 GB | Better accuracy for parsing |
| `gemma3:27b` | ~20 GB | Highest accuracy |
| `llama3.2:3b` | ~3 GB | Fastest option |
| `llama3.1:8b` | ~6 GB | Strong instruction following |

---

## API Reference — Week 2

Base URL: `http://localhost:8001`

---

### Health & Infra

#### `GET /healthz`
Liveness probe. Returns `{"status": "ok"}` if the process is up.

#### `GET /readyz`
Readiness probe. Reports whether Redis is reachable.

| `status` | Meaning |
|---|---|
| `"ok"` | Redis connected — cache is persistent |
| `"degraded"` | Redis unreachable — service still works via in-memory fallback |

#### `GET /admin/cost/today`
Token usage and estimated cost per module for the current day, read from `data/cost_log.jsonl`.
> Local Ollama runs cost $0 — the tracker is wired for when the project migrates to cloud models.

#### `GET /admin/cost/total`
Cumulative project spend vs. the configured `PROJECT_SPEND_CAP_USD`.

---

### Parser — `POST /parse`

**Owner:** G1 | **Status: fully implemented in Week 2**

Accepts a resume file upload and returns a structured candidate JSON record.

**Request:** `multipart/form-data`, field name `file` — `.pdf` or `.docx` only.

**Response:**
```json
{
  "name": "Jane Smith",
  "email": "jane@example.com",
  "phone": "+1-555-0100",
  "skills": ["Python", "FastAPI", "PostgreSQL"],
  "experience_years": 4.5,
  "education": "B.Sc. Computer Science, MIT, 2019",
  "projects": ["Resume parser using LLMs", "E-commerce backend"],
  "summary": "Backend engineer with 4+ years of Python experience...",
  "parse_confidence": 0.91,
  "raw_text": "..."
}
```

**What it does:**
1. Extracts raw text from the uploaded file — PyMuPDF for PDFs, python-docx for DOCX.
2. Sends the text to Ollama (`PARSER_MODEL`) using the `parser_main` prompt from `app/prompts/library.yaml`.
3. Retries up to 3 times on malformed JSON — feeds the parse error back to the model each attempt.
4. Normalises skill names through `parser/skill_map.yaml` — e.g. `"JS"` → `"JavaScript"`.
5. Validates the result against the `ParsedCandidate` Pydantic schema before returning.

**Error responses:**
| Code | Reason |
|---|---|
| `415` | Unsupported file type (not `.pdf` or `.docx`) |
| `422` | Empty file, or LLM output failed schema validation after all retries |
| `500` | Parsing failed for an unexpected reason |

**Quick test:**
```bash
curl -X POST http://localhost:8001/parse \
  -F "file=@/path/to/resume.pdf"
```

---

### Copilot — `POST /copilot`

**Owner:** G2 | **Status: Week 1 stub — real implementation coming in Week 3**

Recruiter natural-language query interface (e.g. "find Python engineers with 3+ years in fintech").

**Request:**
```json
{
  "query": "Find senior ML engineers with PyTorch experience",
  "history": [],
  "job_context": "Optional job description text for context"
}
```

**Response (current stub):**
```json
{
  "candidates": [],
  "summary": "Stub response for query: '...'. G2 replaces this in W3.",
  "query_interpreted": {
    "type": "filter",
    "skills_required": [],
    "top_k": 10
  }
}
```

> G2 wires real candidate retrieval and LLM-generated summaries in Week 3.

---

### Explain — `POST /explain`

**Owner:** G3 | **Status: Week 1 stub — real implementation coming in Week 3**

Returns an LLM-generated explanation of why a candidate scored the way they did for a given job.

**Request:**
```json
{
  "candidate_id": "abc123",
  "job_id": "job456"
}
```

**Response (current stub):**
```json
{
  "candidate_id": "abc123",
  "job_id": "job456",
  "explanation_text": "Stub explanation from W1 — G3 replaces this in W3.",
  "top_strengths": [],
  "top_gaps": [],
  "shap_values": [],
  "model_version": "stub-v0",
  "generated_at": "2026-05-25T10:00:00+00:00"
}
```

> G3 wires a real LLM-generated 3–4 sentence rationale plus SHAP-style feature attribution in Week 3.

---

## Architecture Rules

1. **One LLM entry point** — all inference goes through `app/core/llm.py` → Ollama at `http://localhost:11434/v1` via the OpenAI-compatible API.
2. **All prompts in `app/prompts/library.yaml`** — no inline prompt strings in module code. Prompt changes need a version bump + changelog entry.
3. **Every `llm_call()` must pass `module=`** — required for cost attribution.
4. **Redis cache wraps every LLM call** — TTL 1 hour (configurable). Falls back to in-memory dict when Redis is down.
5. **No cloud credentials** — `.env` has no `OPENAI_API_KEY` or `GEMINI_API_KEY`. Never add them.

## Module Owners

| Module | Owner | Endpoint |
|---|---|---|
| Parser (resume → JSON) | G1 | `POST /parse` |
| Copilot (recruiter queries) | G2 | `POST /copilot` |
| XAI (score explanations) | G3 | `POST /explain` |
| Infra (llm, cache, eval, cost) | G4 | `app/core/`, `scripts/` |
