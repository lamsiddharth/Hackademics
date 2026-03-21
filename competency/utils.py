import json
import logging

from config.ai_client import get_gemini_response, GeminiError
from .models import Question

logger = logging.getLogger(__name__)


def generate_questions_for_job(job_title, seniority='mid', company_type='', num_questions=6):
    """Generate structured competency questions using AI."""
    seniority_label = dict(
        junior='Junior/Entry-level', mid='Mid-level', senior='Senior', staff='Staff/Lead'
    ).get(seniority, 'Mid-level')

    company_context = f" at a {company_type} company" if company_type else ""

    prompt = f"""You are an expert technical interviewer. Generate exactly {num_questions} competency questions for a {seniority_label} {job_title}{company_context}.

Difficulty distribution: 1 conceptual, 1 applied, 2 scenario-based, 1 system-design, 1 behavioral.

Questions must be SPECIFIC, not generic.
Bad example: "Explain machine learning"
Good example: "You have a churn prediction model in production. F1 score dropped 8% last week. Walk me through your debugging process."

Return a JSON array with exactly {num_questions} objects:
[
  {{
    "text": "The specific question",
    "difficulty": "easy|medium|hard",
    "category": "conceptual|applied|scenario|system_design|behavioral",
    "model_answer": "A comprehensive expert answer (3-5 sentences)",
    "evaluation_rubric": "Key points a good answer should cover"
  }}
]

Distribution: 2 easy, 2 medium, 2 hard.
Return ONLY the JSON array. No markdown fences. No other text."""

    return get_gemini_response(prompt, parse_json=True)


def save_generated_questions(raw_response, job_role):
    """Parse structured JSON response and save questions to database."""
    saved_count = 0

    # raw_response is already a parsed list from parse_json=True
    questions = raw_response if isinstance(raw_response, list) else []

    for q in questions:
        if not isinstance(q, dict) or 'text' not in q:
            continue

        text = q['text'].strip()
        difficulty = q.get('difficulty', 'medium').lower()
        if difficulty not in ('easy', 'medium', 'hard'):
            difficulty = 'medium'

        # Store model_answer and rubric in correct_answer as JSON
        extra_data = json.dumps({
            'category': q.get('category', ''),
            'model_answer': q.get('model_answer', ''),
            'evaluation_rubric': q.get('evaluation_rubric', ''),
        })

        if not Question.objects.filter(job_role=job_role, text=text).exists():
            Question.objects.create(
                job_role=job_role,
                text=text,
                difficulty=difficulty,
                correct_answer=extra_data,
            )
            saved_count += 1

    return saved_count


def evaluate_all_answers(answers_queryset):
    """
    Evaluate all answers with structured feedback.
    Returns a dict mapping answer.id -> evaluation dict.
    """
    qa_pairs = []
    for answer in answers_queryset:
        # Try to get rubric from question's correct_answer JSON
        rubric = ''
        try:
            extra = json.loads(answer.question.correct_answer or '{}')
            rubric = extra.get('evaluation_rubric', '')
        except (json.JSONDecodeError, TypeError):
            pass

        qa_pairs.append({
            'id': answer.id,
            'question': answer.question.text,
            'answer': answer.selected_answer,
            'rubric': rubric,
        })

    if not qa_pairs:
        return {}

    qa_text = ""
    for i, qa in enumerate(qa_pairs, 1):
        qa_text += f"\nQ{i}: {qa['question']}"
        if qa['rubric']:
            qa_text += f"\nRubric: {qa['rubric']}"
        qa_text += f"\nAnswer: {qa['answer']}\n"

    prompt = f"""You are an expert answer evaluator. Evaluate each answer below.

{qa_text}

For EACH answer, return a JSON object with:
- score: float 0.0-1.0 (0=wrong, 0.5=partial, 1.0=excellent)
- strengths: array of 1-2 specific things done well
- gaps: array of 1-2 specific things missing or wrong
- model_answer: a 2-3 sentence ideal answer
- skill_tags: array of 1-3 skills demonstrated (e.g., "Python", "System Design", "Communication")

Return a JSON array of {len(qa_pairs)} evaluation objects in order.
ONLY return the JSON array. No markdown. No other text."""

    try:
        evaluations = get_gemini_response(prompt, parse_json=True)

        results = {}
        for i, qa in enumerate(qa_pairs):
            if i < len(evaluations) and isinstance(evaluations[i], dict):
                ev = evaluations[i]
                score = max(0.0, min(1.0, float(ev.get('score', 0))))
                results[qa['id']] = {
                    'score': score,
                    'strengths': ev.get('strengths', []),
                    'gaps': ev.get('gaps', []),
                    'model_answer': ev.get('model_answer', ''),
                    'skill_tags': ev.get('skill_tags', []),
                }
            else:
                results[qa['id']] = {
                    'score': 0.0, 'strengths': [], 'gaps': [],
                    'model_answer': '', 'skill_tags': [],
                }
        return results

    except GeminiError:
        return {qa['id']: {
            'score': 0.0, 'strengths': [], 'gaps': [],
            'model_answer': '', 'skill_tags': [],
        } for qa in qa_pairs}


def evaluate_answer(question_text, user_answer):
    """Evaluate a single answer (backward compatibility)."""
    prompt = f"""Evaluate this answer on a scale of 0 to 1.

Q: {question_text}
Answer: {user_answer}

Respond ONLY with a decimal score (e.g., 0.0, 0.5, 1.0)"""

    try:
        text = get_gemini_response(prompt)
        return max(0.0, min(1.0, float(text.strip())))
    except (GeminiError, ValueError):
        return 0.0
