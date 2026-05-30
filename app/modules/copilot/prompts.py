INTENT_PROMPT_TEMPLATE = """
Convert this recruiter query into a structured candidate search.

Classify the query as exactly one of:
- "filter": explicit filters such as skills, experience, job, label, status, or top-K.
- "semantic": natural-language similarity or project/background searches.

Return ONLY valid JSON with this schema:
{{
  "type": "filter" | "semantic",
  "job_id": <integer or null>,
  "skills_required": ["skill names"],
  "min_experience": <number or null>,
  "label_filter": "Good Fit" | "Average Fit" | "Poor Fit" | null,
  "status_filter": "Applied" | "Shortlisted" | "Interviewed" | "Hired" | "Rejected" | null,
  "top_k": <integer, default 10>,
  "free_text": "<semantic search text or remaining meaningful role/keyword text>"
}}

Examples:
Query: "Show top 5 Good Fit Python developers"
Output: {{"type":"filter","job_id":null,"skills_required":["Python"],"min_experience":null,"label_filter":"Good Fit","status_filter":null,"top_k":5,"free_text":""}}

Query: "Show shortlisted Python developers with 2 years experience"
Output: {{"type":"filter","job_id":null,"skills_required":["Python"],"min_experience":2,"label_filter":null,"status_filter":"Shortlisted","top_k":10,"free_text":""}}

Query: "Candidates similar to Priya who built fintech apps"
Output: {{"type":"semantic","job_id":null,"skills_required":[],"min_experience":null,"label_filter":null,"status_filter":null,"top_k":10,"free_text":"Candidates similar to Priya who built fintech apps"}}

Recruiter query: {query}
"""
