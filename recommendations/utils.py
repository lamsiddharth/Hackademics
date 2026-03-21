import google.generativeai as genai
from django.conf import settings
import requests


def generate_learning_roadmap(skills, projects, experience, target_job):
    genai.configure(api_key=settings.GEMINI_API_KEY)

    # Format the input into a clean prompt
    prompt = f"""
You are a career mentor. Based on the following user profile, identify the skills they are lacking to become a successful {target_job}.
Then, generate a detailed, step-by-step learning roadmap for the next 3–4 months.
Give the roadmap in bullet points without using asteriks or hashes.
you can underline the headings for better readability.
Also provide any sources like documentation, courses, or articles that can help the user learn these skills.

Current Skills:
{', '.join(skills)}

Projects:
{projects if isinstance(projects, str) else '.'.join(projects)}

Experience:
{experience}

Output Format:
1. Lacking Skills: (List format)
2. Roadmap: (Detailed weekly or monthly roadmap)

Be realistic, practical, and focused on relevant technologies and goals. Avoid suggesting skills the user already has.
"""

    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    response = model.generate_content(prompt)

    return response.text


import http.client
import json


def extract_skills_from_profile(location, skills, experience, projects):
    genai.configure(api_key=settings.GEMINI_API_KEY)
    try:
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        prompt = f"""
        Based on the user's professional information, extract a clean and concise list of technical and relevant soft skills only. Avoid repetitions.

        Location: {location}
        Skills mentioned: {skills}
        Experience: {experience}
        Projects: {projects}

        Respond with only a comma-separated list of skills.
        """

        response = model.generate_content(prompt)
        extracted_skills = response.text.strip()

        # Optional: Clean up whitespace and return as list
        return [skill.strip() for skill in extracted_skills.split(',') if skill.strip()]

    except Exception as e:
        return [f"Error: {str(e)}"]


def fetch_jobs(keywords, location):
    host = 'jooble.org'
    key = settings.JOOBLE_API_KEY
    connection = http.client.HTTPSConnection(host)
    headers = {"Content-type": "application/json"}

    # Build a meaningful search query from extracted skills
    if isinstance(keywords, list):
        query = ', '.join(keywords[:5])  # Use top 5 skills as search terms
    else:
        query = str(keywords)

    body = json.dumps({
        "keywords": query,
        "location": location or '',
    })

    try:
        connection.request('POST', f'/api/{key}', body, headers)
        response = connection.getresponse()
        data = response.read().decode()
        if not data:
            return []
        parsed_data = json.loads(data)
        return parsed_data.get("jobs", [])
    except Exception:
        return []
    finally:
        connection.close()


def _normalize_remotive_jobs(jobs):
    normalized = []
    for job in jobs:
        normalized.append({
            "title": job.get("title"),
            "company": job.get("company_name"),
            "location": job.get("candidate_required_location"),
            "type": job.get("job_type"),
            "snippet": job.get("description"),
            "link": job.get("url"),
            "source": "Remotive",
        })
    return normalized


def fetch_jobs_remotive(query, limit=10):
    if not query:
        return []

    api_url = f"https://remotive.com/api/remote-jobs?search={query}&limit={limit}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(api_url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    jobs = data.get("jobs", [])
    return _normalize_remotive_jobs(jobs)

