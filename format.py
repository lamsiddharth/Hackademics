with open("competency/utils.py", "r") as f:
    text = f.read()

import re
text = re.sub(
    r'def generate_questions_for_job.*?return response.text.strip()',
    '''def extract_skills_from_text(text):
    """Extract a concise list of key skills from a long job description or text."""
    genai.configure(api_key=settings.GEMINI_API_KEY)
    try:
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        prompt = f"Extract a clean, comma-separated list of the 1 to 3 most important core technical or professional skills from this text: '{text}'. Respond ONLY with the skills separated by commas, no other text."
        response = model.generate_content(prompt)
        skills = response.text.strip().split(',')
        return [s.strip() for s in skills if s.strip()]
    except Exception:
        # Fallback to the whole text if it fails
        return [text.strip()[:50]]

def generate_questions_for_job(job_title, num_questions=6):
    """Generate competency questions using AI and store them in the database."""
    genai.configure(api_key=settings.GEMINI_API_KEY)

    prompt = f"""
You are an expert technical interviewer. Generate exactly {num_questions} subjective competency questions for the job role: '{job_title}'.

Each question should:
- Test relevant skills for this role
- Be clear and specific
- Have a difficulty level (easy, medium, or hard)

IMPORTANT: Follow this EXACT format for each question:
1. [Question text here] - easy
2. [Question text here] - medium
3. [Question text here] - hard

Generate 2 easy, 2 medium, and 2 hard questions.
Respond ONLY with the numbered questions, no additional text.
\"\"\"

    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    response = model.generate_content(prompt)
    
    return response.text.strip()''',
    text,
    flags=re.DOTALL
)

with open("competency/utils.py", "w") as f:
    f.write(text)
