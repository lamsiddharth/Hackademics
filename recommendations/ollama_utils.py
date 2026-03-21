# recommendations/ollama_utils.py
# Replaces dead Ollama/Mistral calls with Gemini for live job matching

import re
from config.ai_client import get_gemini_response, GeminiError


def extract_skills_from_profile(profile_data: str) -> list[str]:
    """Extract skills from free-form profile text using Gemini."""
    prompt = f"""You are a skill extraction assistant. Extract a clean list of hard skills, soft skills, technologies, and tools from this profile:

{profile_data}

Return only a comma-separated list of skills. No commentary. No markdown."""

    try:
        content = get_gemini_response(prompt)
        skills = [skill.strip() for skill in content.split(",") if skill.strip()]
        return skills
    except GeminiError:
        return []


def match_live_jobs(skills: list[str], jobs: list[dict]) -> list[dict]:
    """Match live jobs to user skills using Gemini instead of local Ollama."""
    if not skills or not jobs:
        return []

    skill_str = ", ".join(skills)

    # Clean job descriptions — strip HTML tags and truncate for token efficiency
    def clean_desc(text):
        text = re.sub(r'<[^>]+>', ' ', text or '')
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:400]  # Cap at 400 chars per job

    job_block = "\n\n".join([
        f"[{i+1}] Title: {job['title']}\nDescription: {clean_desc(job['description'])}"
        for i, job in enumerate(jobs)
    ])

    prompt = f"""You are an AI job matching assistant.

The user has these skills:
{skill_str}

Here are live job openings:
{job_block}

Pick the top 5 most relevant jobs for the user based on skills match.
Return ONLY a JSON array in this exact format:
[
  {{ "index": 3, "reason": "Strong match with backend Python skills" }},
  ...
]
No commentary. No markdown. Only valid JSON."""

    try:
        return get_gemini_response(prompt, parse_json=True)
    except GeminiError:
        return []
