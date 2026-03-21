# recommendations/ollama_utils.py
# Replaces dead Ollama/Mistral calls with Gemini for live job matching

import json
import google.generativeai as genai
from django.conf import settings


def extract_skills_from_profile(profile_data: str) -> list[str]:
    """Extract skills from free-form profile text using Gemini."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    prompt = f"""You are a skill extraction assistant. Extract a clean list of hard skills, soft skills, technologies, and tools from this profile:

{profile_data}

Return only a comma-separated list of skills. No commentary. No markdown."""

    try:
        response = model.generate_content(prompt)
        content = response.text.strip()
        skills = [skill.strip() for skill in content.split(",") if skill.strip()]
        return skills
    except Exception:
        return []


def match_live_jobs(skills: list[str], jobs: list[dict]) -> list[dict]:
    """Match live jobs to user skills using Gemini instead of local Ollama."""
    if not skills or not jobs:
        return []

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    skill_str = ", ".join(skills)

    # Clean job descriptions — strip HTML tags and truncate for token efficiency
    import re
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
        response = model.generate_content(prompt)
        raw = response.text.strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        return json.loads(raw)
    except Exception:
        return []