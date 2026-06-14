# G2 Week 4 Flagship Demo Queries

These five queries are intended for reliable Week 4 demos.

## 1. Filter Search

```json
{
  "query": "Show top 5 Python developers"
}
```

Expected behavior:
- Intent type: `filter`
- Extracts `Python`
- Returns top 5 ranked candidates
- Generates a recruiter-friendly summary

## 2. Multi-Filter Search

```json
{
  "query": "Show shortlisted React developers with 2 years experience"
}
```

Expected behavior:
- Intent type: `filter`
- Extracts `React`, `Shortlisted`, and minimum experience `2`
- Returns matching ranked candidates

## 3. Semantic Search

```json
{
  "query": "Find candidates experienced in AI chatbot projects"
}
```

Expected behavior:
- Intent type: `semantic`
- Uses FAISS search over candidate skills, education, and projects
- Returns semantically relevant candidate profiles

## 4. Similar Candidate Search

```json
{
  "query": "Candidates similar to Priya Singh"
}
```

Expected behavior:
- Intent type: `semantic`
- Routes to FAISS search
- Returns profiles semantically close to the query

## 5. Follow-Up Query With History

```json
{
  "query": "Show me his projects",
  "history": [
    {
      "query": "Candidates similar to Priya who built fintech apps",
      "candidates": [
        {
          "candidate_id": 1001,
          "name": "Priya Chauhan",
          "skills": ["python", "sql"],
          "experience_years": 5,
          "education": "b.tech computer science",
          "projects": ["fintech dashboard", "ai chatbot"],
          "job_id": 1,
          "role": "Backend Engineer",
          "status": "Shortlisted",
          "score": 91.0,
          "label": "Good Fit"
        }
      ]
    }
  ]
}
```

Expected behavior:
- Resolves `his` / candidate reference from history
- Returns the referenced candidate
- Sets `conversation_context_used` to `true`
- Generates a summary focused on that candidate's projects
