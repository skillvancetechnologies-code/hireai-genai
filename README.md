# G2 AI Copilot Engine - Week 3

FastAPI backend for the HireAI G2 AI Copilot Engine.

Week 3 supports both:

- Structured filter queries
- Semantic candidate search with FAISS and sentence-transformers

## Supported Examples

Filter queries:

```text
Show top 5 Good Fit Python developers
Show shortlisted Python developers with 2 years experience
Top 3 backend developers
```

Semantic queries:

```text
Candidates similar to Priya who built fintech apps
Find developers experienced in AI chatbot projects
People who worked on backend automation systems
Candidates with strong machine learning projects
Developers experienced in scalable API systems
```

## Project Structure

```text
app/
├── main.py
├── modules/
│   └── copilot/
│       ├── routes.py
│       ├── intent.py
│       ├── pipeline.py
│       ├── filters.py
│       ├── retriever.py
│       └── prompts.py
├── services/
│   ├── candidate_service.py
│   ├── dataset_loader.py
│   ├── filters.py
│   └── llm_service.py
├── models/
│   └── schemas.py
├── prompts/
│   └── library.yaml
└── data/
    ├── candidates_cleaned.csv
    ├── jobs_cleaned.csv
    ├── applications_cleaned.csv
    └── scores_cleaned.csv

data/
├── eval_sets/
│   └── copilot_eval.json
└── faiss/
    ├── candidates.index
    └── ids.pkl
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional `.env`:

```env
OLLAMA_MODEL=gemma3:latest
```

## Build FAISS Index

Full index over all candidates:

```powershell
python scripts\build_faiss_index.py
```

Faster local/demo index:

```powershell
python scripts\build_faiss_index.py 5000
```

You can also rebuild through the API:

```text
POST /copilot/reindex
POST /copilot/reindex?limit=5000
```

## Run API

```powershell
uvicorn app.main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## Test Requests

Filter:

```json
{
  "query": "Show top 5 Good Fit Python developers"
}
```

Semantic:

```json
{
  "query": "Candidates similar to Priya who built fintech apps"
}
```

## Week 3 Notes

- FAISS index is saved under `data/faiss/`.
- Candidate embeddings use `sentence-transformers/all-MiniLM-L6-v2`.
- Embedding text uses candidate skills, projects, and education.
- Filter queries still use the Week 2 dataset filtering logic.
- Semantic queries route to FAISS vector search.
- Conversation history, advanced summaries, frontend UI, and advanced reranking are intentionally out of scope.
