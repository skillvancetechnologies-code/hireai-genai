# Week 2 Status

## G4 Infra — Complete

All W2 deliverables shipped and passing.

| Deliverable | File | Status |
|---|---|---|
| Parser eval runner | `app/core/eval.py` | ✓ |
| Nightly automation | `scripts/nightly.py` | ✓ |
| Slack integration | `app/core/slack.py` | ✓ |
| Redis health check | `scripts/check_infra.py` | ✓ |
| Budget guard (`BudgetExceeded`) | `app/core/llm.py` | ✓ |
| `module=` required on all LLM calls | `app/core/llm.py` | ✓ |
| Gemini 2.0 Flash fallback (on OpenAI 429) | `app/core/llm.py` | ✓ |
| Gemini pricing in cost tracker | `app/core/cost.py` | ✓ |
| W2 test suite | `app/tests/test_w2.py` | ✓ 27/27 passing |

Run to verify:

```bash
pytest app/tests/ -v                       # 27 tests, all green
python scripts/run_evals.py --all          # runs parser evals (needs PDF files + API quota)
python scripts/nightly.py                  # evals + cost summary, Slack no-ops offline
python scripts/check_infra.py              # exit 0 if Redis up
```

---

## G1 Parser Module — Complete

All G1 W2 deliverables are implemented and integrated.

| Deliverable | File | Status |
|---|---|---|
| Pydantic schema | `app/modules/parser/schemas.py` | ✓ |
| PDF/DOCX text extraction | `app/modules/parser/extract.py` | ✓ |
| Skill canonicalization | `app/modules/parser/normalize.py` | ✓ |
| Skill alias map | `app/modules/parser/skill_map.yaml` | ✓ 100+ mappings |
| Parser service | `app/modules/parser/service.py` | ✓ |
| Upload route (POST /parse) | `app/modules/parser/routes.py` | ✓ |
| Eval dataset | `data/eval_sets/parser.json` | ✓ 10 cases |
| requirements.txt | updated | ✓ PyMuPDF, python-docx, python-multipart, google-genai |

### Issues found and fixed during review

| Issue | Fix |
|---|---|
| case_09 `input` was `Mughal_Arshad_Resume.pdf` — did not match actual PDF on disk | Updated `parser.json` case_09 `input` to `Mughal Arshad - Resume.pdf` |
| `google-generativeai` package deprecated, Gemini 1.5 Flash model 404 | Switched to `google-genai` SDK with `gemini-2.0-flash` model |
| Tenacity retried 429 on top of OpenAI SDK's internal retries (9 total calls) | Changed `retry_if_exception_type(Exception)` → `retry_if_exception(lambda e: not isinstance(e, OpenAIRateLimitError))` |

---

## Remaining Blockers (infrastructure, not code)

### 1. Missing PDF eval files (9 of 10)

Only `Mughal Arshad - Resume.pdf` (case_09) is present in `data/eval_sets/parser_resumes/`.
Cases 01–08 and 10 will `FileNotFoundError` until the PDFs are dropped in that folder with filenames matching `parser.json` exactly.

Team members: add your resume PDFs with the exact filenames listed in `parser.json`.

### 2. API quota exhausted

Both providers are out of quota:
- **OpenAI**: `insufficient_quota` — add credits at platform.openai.com
- **Gemini**: `RESOURCE_EXHAUSTED` on free tier — add credits or wait for quota reset

The fallback chain (OpenAI → Gemini 2.0 Flash) is wired and working correctly. Case_09 correctly reaches Gemini after OpenAI 429, then hits Gemini quota. No code changes needed — this unblocks when credits are added.

---

## Architecture rules (for all team members)

1. `from openai import OpenAI` only in `app/core/llm.py` — never import the SDK directly in module code.
2. All prompts from `library.yaml` — no inline prompt strings.
3. Every `llm_call()` / `llm_call_json()` must pass `module=`.
4. Prompt changes need version bump + changelog entry + eval delta on PR.
5. Use `google-genai` (not `google-generativeai`) — the old package is fully deprecated.
