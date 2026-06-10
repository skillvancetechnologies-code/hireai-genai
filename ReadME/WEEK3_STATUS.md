# Week 3 Status

## G4 Infra — Complete

| Deliverable | File | Status |
|---|---|---|
| Fix G2 broken import paths (5 files) | `app/modules/copilot/routes.py`, `intent_parser.py`, `candidate_service.py`, `filters.py` | ✓ |
| Fix G2 DATA_DIR path (`parents[1]` → `parents[3]`) | `app/modules/copilot/dataset_loader.py` | ✓ |
| Fix G2 CSV filenames (`_cleaned.csv` → `.csv`) | `app/modules/copilot/dataset_loader.py` | ✓ |
| Fix G2 LLM layer (LangChain → `app.core.llm`) | `app/modules/copilot/llm_service.py` | ✓ |
| Fix G3 missing `module=` on `llm_call` | `app/modules/explain/generator.py` | ✓ |
| Wire G2 copilot eval runner | `app/core/eval.py` | ✓ |
| Wire G3 explain eval runner | `app/core/eval.py` | ✓ |
| Replace `recall_at_k` with `copilot_intent_accuracy` scorer | `app/core/eval.py` | ✓ |
| Add `explain_response_valid` scorer | `app/core/eval.py` | ✓ |
| Reformat copilot eval set to `id`/`input` schema | `data/eval_sets/copilot.json` | ✓ 10 cases |
| Update explain eval set to G3's mock IDs (C1-C5, J1-J5) | `data/eval_sets/explain.json` | ✓ 5 cases |
| W3 integration test suite | `app/tests/test_w3.py` | ✓ 18/18 passing |

Run to verify:

```bash
pytest app/tests/ -v                    # 45 tests, all green
python scripts/run_evals.py --all       # copilot + explain runners now active
```

---

## G1 Parser — No changes in W3

G1's module is stable from W2. All parser tests continue to pass.

---

## G2 Copilot — Fixed by G4 (W3)

Issues found and fixed during W3 integration review:

| Issue | Fix |
|---|---|
| `routes.py` imported from `app.models.schemas` and `app.services.*` (don't exist) | Updated all 4 affected files to import from `app.modules.copilot.*` |
| `DATA_DIR` resolved to `app/modules/data/` (non-existent) | Changed `parents[1]` → `parents[3]` to reach repo-level `data/` |
| Dataset filenames expected `_cleaned.csv` suffix | Updated to match actual filenames (`candidates.csv` etc.) |
| Used LangChain + `OllamaLLM` directly, bypassing `app.core.llm` | Rewrote `llm_service.py` to use `llm_call(module="copilot")` |
| `validate="one_to_one"` on applications-scores merge (data may have duplicates) | Removed strict validation — merge still uses inner join |

G2 still needs to submit: nothing (all blockers resolved with the CSV datasets now in `data/`).

---

## G3 Explainable AI — Fixed by G4 (W3)

| Issue | Fix |
|---|---|
| `llm_call(prompt)` missing required `module=` kwarg → `TypeError` on every call | Changed to `llm_call(prompt, module="explain")` |

G3 known limitation: explain module uses hardcoded mock data (`C1–C5`, `J1–J5`). Connection to real candidate datasets is a W4 task for G3.

---

## Architecture rule violations resolved

| Rule | Violator | Status |
|---|---|---|
| All LLM calls through `app.core.llm` | G2 (used LangChain directly) | ✓ Fixed |
| Every `llm_call()` must pass `module=` | G3 (missing `module=`) | ✓ Fixed |
