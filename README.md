# hireai-genai

GenAI services for HireAI Copilot: resume parsing, AI Copilot query engine, and Explainable AI score rationales. Three FastAPI modules sharing one infrastructure layer.

```
hireai-genai/
├── app/
│   ├── main.py                 # FastAPI app, mounts all 3 routers
│   ├── core/                   # G4 owns - shared infra
│   │   ├── config.py           #   env vars + settings
│   │   ├── llm.py              #   the ONE LLM wrapper
│   │   ├── cache.py            #   Redis (with in-memory fallback)
│   │   ├── cost.py             #   per-call $ tracking
│   │   ├── prompts.py          #   prompt library loader
│   │   └── eval.py             #   eval runner framework
│   ├── modules/
│   │   ├── parser/             # G1
│   │   ├── copilot/            # G2
│   │   └── explain/            # G3
│   ├── prompts/
│   │   ├── library.yaml        # versioned prompts (3 starters)
│   │   └── README.md           # how G1/G2/G3 use the library
│   └── tests/                  # smoke tests for the W1 infra
├── data/
│   ├── eval_sets/              # gold cases per module
│   └── eval_results/           # nightly run outputs
├── scripts/
│   ├── run_evals.py            # nightly eval runner
│   ├── cost_summary.py         # daily Slack-ready spend summary
│   └── precache_explanations.py # W5+ pre-warm script
├── .env.example
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set OPENAI_API_KEY, point REDIS_URL at hireai-web's docker-compose Redis

uvicorn app.main:app --reload --port 8001
```

Verify:

```bash
curl http://localhost:8001/healthz                 # {"status":"ok"}
curl http://localhost:8001/readyz                  # reports Redis status
curl -X POST http://localhost:8001/parse           # G1 stub response
curl -X POST http://localhost:8001/copilot \
  -H "Content-Type: application/json" \
  -d '{"query":"top 5 python devs"}'               # G2 stub response
curl -X POST http://localhost:8001/explain \
  -H "Content-Type: application/json" \
  -d '{"candidate_id":"CAND0001","job_id":"JOB0001"}'  # G3 stub response
```

## Week 1 Demo Checklist (G4)

These are what you show on Friday. Every item is independently demonstrable.

### 1. The LLM wrapper works end-to-end

```python
from app.core.llm import llm_call
print(llm_call("Say hello in one word.", model="gpt-4o-mini", module="demo"))
print(llm_call("Say hello in one word.", model="gpt-4o-mini", module="demo"))  # cache hit
```

Second call is instant. Check `data/cost_log.jsonl` — second record has `"cache_hit": true` and `"cost_usd": 0.0`.

### 2. Smoke tests pass

```bash
pytest app/tests/ -v
```

15 tests cover: prompt loading, cache roundtrip, retry/cache logic on `llm_call`, JSON parsing, custom cache keys (the explain-module case), cost estimation, and cost logging.

### 3. Prompt library has 3 versioned prompts

```bash
python -c "from app.core.prompts import list_prompts; print(list_prompts())"
# ['parser_main', 'intent_classifier', 'explanation']
```

Open `app/prompts/library.yaml` — show the schema (`version`, `model`, `temperature`, `template`, `changelog`) and the three committed prompts.

### 4. Cost summary works

```bash
python scripts/cost_summary.py --slack
```

Prints the Slack-ready daily summary. Empty on Day 1, populates as G1/G2/G3 start calling `llm_call`.

### 5. Eval runner skeleton works

```bash
python scripts/run_evals.py --all
```

Loads the three eval sets, reports each module (W1: no runner registered yet — that's expected; W2 wires real runners).

### 6. Onboarding doc exists

`app/prompts/README.md` — the quickstart G1/G2/G3 read on day 1.

## Week 2 (G4 infra additions)

### Eval runner — parser

- Canonical eval set format: `data/eval_sets/<module>.json` = list of `{id, input, expected}`.
- Parser eval drives G1's module the same way production does — pass a resume FILE, let G1 extract text. The runner does NOT reimplement PDF parsing.
- PDFs live in `data/eval_sets/parser_resumes/` (gitignored — real PII). G1 drops the 10 files there; filenames must match the `input` field in `parser.json`.
- If G1's parser is not yet importable, or the PDF folder is empty, `run_eval("parser")` records `accuracy=null` with a clean skip message and does not crash.
- `field_accuracy` grades ONLY the keys present in each case's `expected` object — extra fields G1 returns (`projects`, `summary`, `parse_confidence`) are neither rewarded nor penalized.

### Nightly automation

```bash
python scripts/nightly.py            # runs evals + posts cost summary + regression alerts
```

Cron line (add to your server's crontab):

```
0 6 * * * cd /path/to/hireai-genai && .venv/bin/python scripts/nightly.py
```

Without `SLACK_WEBHOOK_URL` set, messages are logged instead of posted (offline-safe).

### Slack setup

Set `SLACK_WEBHOOK_URL` in `.env` to an incoming-webhook URL for `#genai-team`. The nightly job posts:

1. Eval summary (per-module accuracy)
2. Cost summary (yesterday's spend + project total vs cap)
3. One regression alert per module that dropped >3pts vs its 7-day average, tagging the owner from `module_owners` in `config.py`.

### Redis check

```bash
python scripts/check_infra.py        # exit 0 if Redis up, 1 if down
```

`REDIS_URL` must point at the same Redis instance hireai-web's docker-compose runs (so cache hits are shared). When connected, `GET /readyz` returns `{"status":"ok"}`. A response of `{"status":"degraded"}` means the wrapper is on memory fallback — fix Redis before treating cost numbers as authoritative.

### Cost integrity

- `module=` is now a REQUIRED keyword arg on `llm_call` / `llm_call_json` — every call must be attributable.
- `BudgetExceeded` is raised before any OpenAI call once `project_total() >= PROJECT_SPEND_CAP_USD`. Cache hits are exempt.

## Architecture Rules (enforced)

1. **`from openai import OpenAI` only lives in `app/core/llm.py`.** Nobody else imports the SDK directly.
2. **All prompts live in `library.yaml`.** No inline prompt strings in module code.
3. **All LLM calls pass a `module=` tag.** This is how cost is attributed.
4. **Cache TTL is always explicit or comes from settings.** Never hardcoded constants.
5. **Prompt changes require version bump + changelog entry.** Enforced via PR review by G4.

## Cost Targets

Total project budget: **<$200 over 6 weeks**.

| Module | Model | Strategy |
|---|---|---|
| Parser | gpt-4o-mini | Cache by file hash. Most resumes parsed once. |
| Copilot | gpt-4o-mini | Cache by normalized query. |
| Explain | gpt-4o | Pre-cache top 1000 pairs in W5. |

Daily summary posted to `#genai-team` Slack via `scripts/cost_summary.py --slack`.

## Module Owners

| Module | Owner | Endpoint |
|---|---|---|
| Parser | G1 | `POST /parse` |
| Copilot | G2 | `POST /copilot` |
| Explain | G3 | `POST /explain` |
| Infra (this) | G4 | `core/*`, `prompts/*`, `scripts/*` |
