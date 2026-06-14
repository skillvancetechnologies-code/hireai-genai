# G1 — Resume Parser Accuracy Report
## Week 5 & 6 Final Evaluation

> Generated from a real run of `python scripts/run_evals.py --module parser`
> on 2026-06-14 (model `gemma3:4b` via Ollama, Redis cache enabled).
> Raw output: `data/eval_results/parser_latest.json`.

### Summary
| Metric | Result |
|---|---|
| Eval cases scored | 50 |
| Overall accuracy | **71.7%** |
| Target accuracy | >90% |
| Status | ❌ **Target NOT met** |

Scoring is field-level (`field_accuracy` in `app/core/eval.py`): each gold
case grades `name, email, phone, skills, experience_years, education`. List
fields use case-insensitive subset match; scalars use exact equality. The
score is the fraction of those fields the parser got right, averaged over
all cases.

### Accuracy Breakdown
| Resume group | Count | Avg accuracy |
|---|---|---|
| Real candidate resumes (case_01–32) | 32 | 62.5% |
| Synthetic templated resumes (case_33–50) | 18 | 88.0% |
| Perfect score (all fields correct) | 9 | — |
| Scored ≥ 80% | 23 | — |
| Scored < 50% | 4 | — |

The headline 71.7% is inflated by the 18 clean, templated synthetic resumes
(88%). On the 32 real-world resumes the parser scores **62.5%**, which is the
more honest production estimate. Weakest cases: `case_13`, `case_20` (16.7%),
`case_27`, `case_32` (33.3%) — mostly `education`/`experience_years`
extraction errors and skill-set mismatches.

### Edge Cases — measured behaviour
| Case | Result |
|---|---|
| Missing email | ✅ Returns null |
| Malformed email (e.g. stray space from OCR) | ✅ **Now** dropped to null — previously crashed the parse (fixed in `service.py`, `_clean_email`) |
| Empty / no extractable text | ✅ Raises `ValueError` |
| Image resume (JPG/PNG) | ⚠️ OCR path exists (pytesseract); not exercised by this eval set |
| Garbled formatting (`case_23` MEDA KOWSHIK) | Partial extraction, score 0.5 |

### Known accuracy gaps (real, from this run)
- `education` is the most error-prone field — wrong institution or degree on
  several real resumes.
- `experience_years` frequently off by 1–2 years.
- Skill extraction misses or over-normalizes on dense resumes.
- Real resumes (62.5%) lag synthetic ones (88%) substantially — the gold set
  should not be reported as a single blended number without this caveat.

### Latency
| Scenario | Latency |
|---|---|
| Ollama `gemma3:4b` local (CPU) | ~30s per resume |
| Cache hit (Redis) | <1s — full 50-case re-run completed in ~9.5s |
| Gemini Flash fallback (production, if Ollama fails) | provider-dependent |

> Note: this project uses Ollama (primary) → Gemini Flash (fallback). Earlier
> versions of this report cited "OpenAI gpt-4o-mini"; that is not part of the
> architecture and has been removed.

### File Support
- ✅ PDF / DOCX / DOC
- ⚠️ JPG / JPEG / PNG via Tesseract OCR — code path present, not covered by this eval

### Reproduce
```bash
docker start hireai-redis            # or: docker run -d --name hireai-redis -p 6379:6379 redis:7-alpine
ollama serve                         # gemma3:4b must be pulled
python scripts/run_evals.py --module parser
cat data/eval_results/parser_latest.json
```

### Honest status vs. prior claim
A previous version of this report claimed **98% on 50 resumes / target met**.
That number was never produced by the eval runner — at the time it was
written, the last actual run (`count: 10`) scored 63.3%, and the 50-case set
had never been executed. This report replaces that claim with the real
measured result: **71.7% overall (62.5% on real resumes), target not met.**
