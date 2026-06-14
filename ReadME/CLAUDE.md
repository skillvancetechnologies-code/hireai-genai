# HireAI GenAI — Claude Code Instructions

## LLM Backend: Ollama (local, no API keys)

**This project uses Ollama for all LLM inference. There are no OpenAI or Gemini API keys.**

- All LLM calls go through `app/core/llm.py` → `_call_ollama()` → Ollama at `http://localhost:11434/v1`
- The OpenAI Python SDK is used as an HTTP client only — pointed at Ollama's OpenAI-compatible endpoint (primary) and Google's OpenAI-compatible endpoint (Gemini fallback)
- Default model: `gemma3:4b` (set via `PARSER_MODEL`, `COPILOT_MODEL`, `EXPLAIN_MODEL` in `.env`)
- **Never add `OPENAI_API_KEY` — OpenAI is not used as a provider**
- **Never import `openai` outside of `app/core/llm.py`**
- **Never import `google.genai` or `google.generativeai`** — the Gemini fallback uses Google's OpenAI-compatible REST endpoint through the existing client, no Google SDK
- Fallback chain (W4): primary Ollama model → Gemini Flash (`GEMINI_API_KEY` + `GEMINI_FALLBACK_MODEL` in `.env`, skipped when key is empty) → local `FALLBACK_MODEL` (default `mistral:latest`); toggle with `FALLBACK_ENABLED`
- Gemini calls are billed — pricing lives in `app/core/cost.py` and counts against the $200 budget guard

## Ollama setup (one-time per machine)

```bash
# 1. Install Ollama
# Windows: https://ollama.com/download
# Mac:     brew install ollama
# Linux:   curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull the default model
ollama pull gemma3:4b

# 3. Ollama runs as a background service automatically after install
#    Verify: curl http://localhost:11434/api/tags
```

### Available models (change in .env to switch)

| Model | RAM needed | Best for |
|---|---|---|
| `gemma3:4b` | ~4 GB | Default — fast, good JSON following |
| `gemma3:12b` | ~8 GB | Better accuracy for parsing |
| `gemma3:27b` | ~20 GB | Highest accuracy |
| `llama3.2:3b` | ~3 GB | Fastest, lighter tasks |
| `llama3.1:8b` | ~6 GB | Strong instruction following |

## Architecture rules

1. **One LLM entry point**: all calls go through `llm_call()` or `llm_call_json()` in `app/core/llm.py`
2. **All prompts in `app/prompts/library.yaml`** — no inline prompt strings in module code
3. **Every `llm_call()` must pass `module=`** — used for cost/usage tracking
4. **Prompt changes** need version bump + changelog entry in `library.yaml`
5. **No cloud credentials** anywhere in the codebase or `.env`

## Running the project

```bash
# Start Ollama (if not already running as a service)
ollama serve

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Run tests
pytest app/tests/ -v

# Run evals (needs PDFs in data/eval_sets/parser_resumes/)
python scripts/run_evals.py --all
```

## Module ownership

| Module | Owner | Entry point |
|---|---|---|
| Parser (resume → JSON) | G1 | `app/modules/parser/` |
| Copilot (recruiter queries) | G2 | `app/modules/copilot/` |
| XAI (score explanations) | G3 | `app/modules/explain/` |
| Infra (llm, cache, eval, cost) | G4 | `app/core/` |
