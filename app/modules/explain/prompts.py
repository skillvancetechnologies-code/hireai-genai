def build_prompt(candidate):
    return f"""You are explaining an AI-generated candidate score to a recruiter.

Be concise, factual, and neutral. Do NOT use subjective or negative words like
'great', 'excellent', 'unfortunately', 'sadly', 'lacking', 'weak', or 'limited'.

Do NOT mention demographics, age, gender, or location.

Instead of saying a skill is lacking, say it is not present in the candidate profile.

Inputs:
- Candidate name: {candidate['name']}
- Job title: {candidate['job_title']}
- Composite score: {candidate['score']}/100, label: {candidate['label']}
- Skills match: {candidate['skills_match']}/100 ({candidate['matched_count']} of {candidate['required_count']} required skills)
- Experience: {candidate['candidate_exp']} years (job requires {candidate['required_exp']})
- Project relevance: {candidate['project_score']}/100
- Matched skills: {candidate['matched_skills']}
- Missing skills: {candidate['missing_skills']}

Write EXACTLY 3-4 sentences in this structure:
1. State the candidate name, job title, score, and label.
2. State strengths: which required skills they match and their experience.
3. State gaps: which required skills are not present in the profile.
4. Optional: comment on project relevance only if score >75 or <40.

Output the explanation only -- no preamble, no extra text.
"""