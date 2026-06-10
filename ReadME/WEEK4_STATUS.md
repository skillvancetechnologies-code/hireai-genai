# Week 4 Status

## G4 Infra — Complete

Week 4 deliverable per team docs: *"Cost tracking dashboards ready for PM.
Gemini fallback implemented and tested. Library has 15+ versioned prompts."*

| Deliverable | File | Status |
|---|---|---|
| PM cost dashboard endpoint `GET /dashboard/costs` (daily trend, budget vs $200 cap) | `app/core/dashboard.py` | ✓ |
| PM eval dashboard endpoint `GET /dashboard/evals` (latest accuracy + regression flags) | `app/core/dashboard.py` | ✓ |
| Gemini fallback (docs 8.3): primary fails after retries → same call retried on Gemini Flash, then local `mistral:latest` as last resort | `app/core/llm.py`, `app/core/config.py` | ✓ |
| Prompt library expanded to **15 versioned prompts** with changelogs | `app/prompts/library.yaml` | ✓ |
| Restored `parser_main` + `intent_classifier` (dropped in a W4 merge — broke `parser/service.py` and `test_core.py`) | `app/prompts/library.yaml` | ✓ |
| Parser retry prompt moved from inline string into the library (`parser_retry_fix`) | `app/modules/parser/service.py` | ✓ |
| Fixed library model tags (`gemma3:latest` is not pulled; all entries now use installed models) | `app/prompts/library.yaml` | ✓ |
| Resolved `requirements.txt` merge conflict (union of G4 pinned deps + G2 LangChain/FAISS deps) | `requirements.txt` | ✓ |
| W4 test suite: fallback (4), library standards (5), dashboards (3) | `app/tests/test_w4.py` | ✓ 12/12 |

Run to verify:

```bash
pytest app/tests/ -v                 # 58 tests, all green
python scripts/run_evals.py --all    # nightly eval runner
curl http://localhost:8001/dashboard/costs   # PM cost dashboard
curl http://localhost:8001/dashboard/evals   # PM eval dashboard
```

### Fallback chain

Per team docs 8.3, Gemini is the fallback provider. The chain in `llm_call()`:

1. **Primary**: Ollama model (3 retries, exponential backoff)
2. **Gemini Flash** via Google's OpenAI-compatible endpoint — used only when
   `GEMINI_API_KEY` is set in `.env` (get one at https://aistudio.google.com/apikey).
   No `google.*` SDK is imported; the existing OpenAI client is pointed at
   `generativelanguage.googleapis.com/v1beta/openai/`.
3. **Local last resort**: `FALLBACK_MODEL` (default `mistral:latest`) so
   offline dev and the demo keep working even without a key or network.

The fallback result is cached under the original cache key, so subsequent
calls are hits. Gemini usage is billed: pricing for `gemini-2.5-flash` is in
`app/core/cost.py` and counts against the $200 budget guard, which refuses
calls once the cap is hit. Toggle everything with `FALLBACK_ENABLED`.
The local leg was verified live (nonexistent primary model → valid completion
from `mistral:latest`); the Gemini leg is covered by mocked tests and needs a
one-time live check once a `GEMINI_API_KEY` is added to `.env`.

### Prompt library contents (15)

| Prompt | v | Owner module |
|---|---|---|
| `parser_main` | 3 | parser |
| `parser_retry_fix` | 1 | parser |
| `parser_card_summary` | 1 | parser |
| `intent_classifier` | 2 | copilot |
| `g2_intent_parser` | 5 | copilot |
| `g2_candidate_summary` | 2 | copilot |
| `g2_followup_resolver` | 1 | copilot |
| `g2_comparison_summary` | 1 | copilot |
| `g2_skill_gap_analysis` | 1 | copilot |
| `explanation` | 1 | explain |
| `explain_edge_perfect_fit` | 1 | explain |
| `explain_edge_poor_fit` | 1 | explain |
| `explain_edge_missing_data` | 1 | explain |
| `eval_rubric_judge` | 1 | eval (G4) |
| `tone_guard` | 1 | eval (G4) |

Library standards now enforced by tests: every entry has
version/description/model/temperature/template/changelog, changelog length ≥
version, model tag must be installed locally, and every template must render
with `str.format()` (catches unescaped JSON braces).

---

## Carried from earlier weeks (already complete)

- `llm.py` / `cache.py` / `cost.py` wrappers (W1)
- Eval runner + all three module eval sets wired in, regression detection (W2–W3)
- Nightly automation with Slack summaries (`scripts/nightly.py`)
- Pre-cache script for demo flow (`scripts/precache_explanations.py`) — W5/W6 task

## Known limitations / W5 follow-ups

- ~~G3 explain mock data~~ — resolved: explain now loads the real CSVs
  (50,000 candidates, 10 jobs). W3's status note is outdated.
- `g2_followup_resolver`, comparison, and skill-gap prompts are registered and
  renderable but G2's pipeline still uses its heuristic resolver; wiring is a
  W5 item if the heuristics fall short on demo queries.
- Eval set sizes vs doc targets: parser 10 gold cases (32 resume PDFs on disk,
  target 50), copilot 10 (target 30), explain 30 (target met). Extending gold
  cases is owned by G1/G2 respectively; the runner handles any count.
