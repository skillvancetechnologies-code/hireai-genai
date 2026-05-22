# Prompt Library — How to Use (G1, G2, G3 read this)

All prompts live in `library.yaml`. You never define prompt strings
inline in your module code. You load them by ID, format them, and pass
the result to `llm_call()`.

## Quickstart

```python
from app.core.prompts import load_prompt
from app.core.llm import llm_call, llm_call_json

prompt = load_prompt("parser_main")
rendered = prompt.format(resume_text=raw_text)

# JSON-mode call (parser, intent_classifier)
data = llm_call_json(
    rendered,
    model=prompt.model,
    temperature=prompt.temperature,
    module="parser",
)

# Free-form call (explanation)
text = llm_call(
    rendered,
    model=prompt.model,
    temperature=prompt.temperature,
    module="explain",
)
```

## Adding a new prompt

1. Open `library.yaml`, add a new top-level key with the full schema:
   `version, description, model, temperature, json_mode, template, changelog`.
2. Start at `version: 1`.
3. Run the eval for the affected module (`python scripts/run_evals.py --module parser`).
4. Open a PR. G4 reviews before merge.

## Changing an existing prompt

1. Bump `version`.
2. Add a line to `changelog`: `"v3: lowered temperature, fixed soft-skill leakage"`.
3. Run the eval, attach the accuracy delta to your PR description.
4. Do not merge if accuracy drops more than 3 percentage points without justification.

## Rules

- **No `import openai` anywhere outside `app/core/llm.py`.**
- **No prompt strings inline in module code.** All prompts come from this file.
- **No real PII or proprietary data in test prompts.** OpenAI logs every call.
- **JSON outputs always go through Pydantic validation** — even with `json_mode: true`, the LLM occasionally returns malformed JSON.

## Current prompts

| id | owner | model | purpose |
|---|---|---|---|
| `parser_main` | G1 | gpt-4o-mini | Resume → candidate JSON |
| `intent_classifier` | G2 | gpt-4o-mini | Free-text query → structured filter |
| `explanation` | G3 | gpt-4o | Score → 3-4 sentence rationale |
