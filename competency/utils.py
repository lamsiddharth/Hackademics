import re
import json
import google.generativeai as genai
from django.conf import settings
from .models import Question


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
"""

    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    response = model.generate_content(prompt)
    
    return response.text.strip()


def save_generated_questions(raw_response, job_role):
    """Parse AI response and save questions to database."""
    question_lines = raw_response.strip().split('\n')
    saved_count = 0
    
    for line in question_lines:
        line = line.strip()
        if not line:
            continue
            
        # Try to match format: "1. Question text - difficulty"
        match = re.match(r'^\d+\.\s*(.+?)\s*-\s*(easy|medium|hard)\s*$', line, re.IGNORECASE)
        if match:
            text = match.group(1).strip()
            difficulty = match.group(2).lower()
        else:
            # Fallback: just extract the question text, default to medium
            match = re.match(r'^\d+\.\s*(.+)$', line)
            if match:
                text = match.group(1).strip()
                # Remove trailing difficulty if present without dash
                for diff in ['easy', 'medium', 'hard']:
                    if text.lower().endswith(diff):
                        text = text[:-len(diff)].strip(' -')
                        difficulty = diff
                        break
                else:
                    difficulty = 'medium'
            else:
                continue
        
        # Don't create duplicates
        if not Question.objects.filter(job_role=job_role, text=text).exists():
            Question.objects.create(job_role=job_role, text=text, difficulty=difficulty)
            saved_count += 1
    
    return saved_count


def evaluate_all_answers(answers_queryset):
    """
    Evaluate all answers in a test session using AI.
    Returns a dict with question_id -> score mapping.
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    
    # Build the Q&A pairs for evaluation
    qa_pairs = []
    for answer in answers_queryset:
        qa_pairs.append({
            'id': answer.id,
            'question': answer.question.text,
            'answer': answer.selected_answer
        })
    
    if not qa_pairs:
        return {}
    
    # Format Q&A for the prompt
    qa_text = ""
    for i, qa in enumerate(qa_pairs, 1):
        qa_text += f"\nQ{i}: {qa['question']}\nA{i}: {qa['answer']}\n"
    
    prompt = f"""
You are an expert answer evaluator. Evaluate each of the following question-answer pairs.

{qa_text}

For each answer, provide a score from 0.0 to 1.0 based on correctness and completeness.
- 0.0 = completely wrong or irrelevant
- 0.5 = partially correct
- 1.0 = completely correct and comprehensive

IMPORTANT: Respond ONLY with a JSON array of scores in order, like: [0.8, 0.5, 1.0, 0.3, 0.7, 0.9]
No other text, just the JSON array.
"""

    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    response = model.generate_content(prompt)
    
    # Parse the scores
    try:
        response_text = response.text.strip()
        # Extract JSON array from response
        start = response_text.find('[')
        end = response_text.rfind(']') + 1
        if start >= 0 and end > start:
            scores = json.loads(response_text[start:end])
        else:
            scores = json.loads(response_text)
        
        # Map scores to answer IDs
        results = {}
        for i, qa in enumerate(qa_pairs):
            if i < len(scores):
                score = float(scores[i])
                score = max(0.0, min(1.0, score))  # Clamp to 0-1
                results[qa['id']] = score
            else:
                results[qa['id']] = 0.0
        
        return results
    except (json.JSONDecodeError, ValueError, TypeError):
        # Fallback: return 0 for all
        return {qa['id']: 0.0 for qa in qa_pairs}


def evaluate_answer(question_text, user_answer):
    """Evaluate a single answer (kept for backward compatibility)."""
    genai.configure(api_key=settings.GEMINI_API_KEY)

    prompt = f"""
You're an expert answers evaluator. The following question was asked:

Q: {question_text}

User's Answer: {user_answer}

On a scale of 0 to 1, how correct is the user's answer? 
Respond ONLY with a decimal score (e.g., 0.0, 0.5, 1.0)
"""

    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    response = model.generate_content(prompt)

    try:
        score = float(response.text.strip())
        return max(0.0, min(1.0, score))
    except:
        return 0.0