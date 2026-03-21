import google.generativeai as genai
from django.conf import settings
import json


def generate_full_resume(profile, email):
    """
    Uses Gemini to FORMAT the user's profile into a structured resume schema.

    STRICT RULES enforced in the prompt:
    - Never invent, fabricate, or add information not in the user's profile.
    - Only polish grammar, fix action verbs, and add structure.
    - Return a clean JSON structure with typed arrays for each section.
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    prompt = f"""You are a professional resume formatter. Your ONLY job is to take the raw profile data below and REFORMAT it into a clean, structured JSON — without inventing, fabricating, adding, or implying ANY information not explicitly present in the input.

PROFILE DATA (this is the ONLY source of truth — do NOT add anything else):
- Name: {profile.full_name}
- Phone: {profile.phone_number}
- Location: {profile.location}
- Skills: {profile.skills}
- Education: {profile.education}
- Experience: {profile.experience}
- Projects: {profile.projects}
- Achievements: {profile.achievements}

YOUR FORMATTING RULES:
1. SUMMARY: Write 2 concise sentences. Use only facts from the profile. NEVER add technologies, companies, or metrics not mentioned.
2. SKILLS: Parse the skills text into categories. Each category has a name and a list of skills. Keep all skills that were mentioned — do not remove any.
3. EDUCATION: Parse into a list. Each entry: institution, degree, field, dates (only if mentioned). Use "Not specified" for truly missing dates — do not guess.
4. EXPERIENCE: Parse into a list of roles. Each role: company, title, dates (only if mentioned), and 2-3 bullet_points.
   - Bullet points MUST start with a strong action verb (Led, Built, Developed, Optimized, Designed, etc.)
   - You MAY elaborate and expand on what the user wrote to make each bullet sound professional and impactful.
   - You MUST stay faithful to the core facts — do NOT invent new companies, job titles, or technologies not mentioned.
   - You CAN add professional context, describe likely scope/impact, or rephrase vaguely described tasks using industry-standard language.
   - Example: "worked on backend" → "Engineered RESTful backend services using Django, improving API response time and enabling scalable data delivery."
5. PROJECTS: Parse into a list. Each project: name, tech_stack (only what is mentioned), and 2-3 bullet_points.
   - Same rules as experience — elaborate and make it sound impressive, but do NOT invent technologies, users counts, or data not mentioned.
   - Describe what was built, the technical approach, and likely impact in professional language.
   - Example: "made a chatbot" → "Designed and deployed a conversational AI chatbot using Python and OpenAI API, enabling natural language query resolution."
6. ACHIEVEMENTS: Parse into a clean list of achievement strings. Preserve all numbers/metrics exactly as given. Do NOT modify any numbers.

If a section is empty or says "Not provided", return an empty array [] for it.

Return ONLY this exact JSON. No markdown. No commentary. No extra keys:
{{
  "summary": "A concise 2-sentence professional summary using only provided facts.",
  "skills": [
    {{"category": "Languages", "items": ["Python", "JavaScript"]}},
    {{"category": "Frameworks", "items": ["Django", "React"]}}
  ],
  "education": [
    {{"institution": "IIT Delhi", "degree": "B.Tech", "field": "Computer Science", "dates": "2019 – 2023"}}
  ],
  "experience": [
    {{
      "title": "Software Engineer",
      "company": "Accenture",
      "dates": "Jan 2023 – Present",
      "bullets": [
        "Developed REST APIs serving 50,000+ daily active users using Django and PostgreSQL.",
        "Reduced page load time by 40% through Redis caching and query optimization.",
        "Led migration from monolithic architecture to microservices, improving deployment frequency by 3x."
      ]
    }}
  ],
  "projects": [
    {{
      "name": "E-commerce Platform",
      "tech": "Django, React, PostgreSQL, AWS S3",
      "bullets": [
        "Built a full-stack marketplace supporting 500+ product listings with secure checkout.",
        "Implemented JWT authentication and role-based access control for admin and buyer roles.",
        "Deployed on AWS EC2 with CI/CD pipeline reducing deployment time from 2 hours to 15 minutes."
      ]
    }}
  ],
  "achievements": [
    "Ranked in top 5% of 10,000+ participants in HackerRank Python certification.",
    "Winner of National Level Hackathon 2023 among 200+ competing teams."
  ]
}}"""

    try:
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Strip markdown code fences if present
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()

        result = json.loads(raw)

        # Validate expected structure — return fallback for any missing key
        return {
            'summary': result.get('summary', ''),
            'skills': result.get('skills', []),
            'education': result.get('education', []),
            'experience': result.get('experience', []),
            'projects': result.get('projects', []),
            'achievements': result.get('achievements', []),
        }

    except Exception:
        # Fallback: return raw profile data as plain-text arrays
        return _plain_fallback(profile)


def _plain_fallback(profile):
    """Return structured skeleton from raw profile data when AI fails."""
    def split_lines(text):
        if not text:
            return []
        return [line.strip() for line in text.replace('\r', '').split('\n') if line.strip()]

    return {
        'summary': '',
        'skills': [{'category': 'Skills', 'items': [s.strip() for s in (profile.skills or '').split(',') if s.strip()]}],
        'education': [{'institution': profile.education or '', 'degree': '', 'field': '', 'dates': ''}],
        'experience': [{'title': '', 'company': '', 'dates': '', 'bullets': split_lines(profile.experience)}],
        'projects': [{'name': '', 'tech': '', 'bullets': split_lines(profile.projects)}],
        'achievements': split_lines(profile.achievements),
    }


def enhance_with_ollama(prompt_text: str) -> str:
    """
    Legacy enhancement function kept for backward compatibility.
    Used for quick single-field polishing.
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    system_prompt = (
        "You are a professional resume writer. "
        "Improve the grammar, clarity and professional tone of the following text. "
        "Use strong action verbs. Do NOT invent new information. "
        "Return the improved text only, no commentary."
    )
    response = model.generate_content(f"{system_prompt}\n\n{prompt_text}")
    return response.text