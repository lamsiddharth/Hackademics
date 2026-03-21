from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required as _login_required
from .utils import generate_questions_for_job, save_generated_questions
from .models import Question


@_login_required
def generate_test_questions(request):
    if request.method == 'POST':
        job_role = request.POST.get('job_role')
        if job_role:
            try:
                raw_output = generate_questions_for_job(job_role)
                save_generated_questions(raw_output, job_role)
                return redirect('view_questions', job_role=job_role)
            except Exception:
                return render(request, 'competency/generate_test.html', {
                    'error': 'The AI service is temporarily unavailable. Please try again later.'
                })
    return render(request, 'competency/generate_test.html')

def view_questions(request, job_role):
    questions = Question.objects.filter(job_role=job_role)
    return render(request, 'competency/view_questions.html', {'questions': questions, 'job_role': job_role})


from .models import CompetencyTestSession, Question, Answer
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def start_test(request, job_role):
    # Check if questions exist for this job role
    question = Question.objects.filter(job_role=job_role).order_by('?').first()
    
    if not question:
        # No questions exist — generate them first
        from .utils import generate_questions_for_job, save_generated_questions
        try:
            raw_output = generate_questions_for_job(job_role)
            save_generated_questions(raw_output, job_role)
            question = Question.objects.filter(job_role=job_role).order_by('?').first()
        except Exception:
            pass
    
    if not question:
        messages.error(request, f'No questions available for "{job_role}". Please generate questions first.')
        return redirect('generate_test')
    
    session = CompetencyTestSession.objects.create(user=request.user, job_role=job_role)
    return redirect('question', session_id=session.id, question_id=question.id)

@login_required
def question_view(request, session_id, question_id):
    session = CompetencyTestSession.objects.get(id=session_id, user=request.user)
    question = Question.objects.get(id=question_id)

    if request.method == 'POST':
        answer = request.POST.get('answer')
        # Just save the answer - evaluation happens at the end
        Answer.objects.create(
            session=session,
            question=question,
            selected_answer=answer,
            is_correct=False  # Will be updated after batch evaluation
        )

        # Fetch next unanswered question
        answered_ids = Answer.objects.filter(session=session).values_list('question_id', flat=True)
        next_question = Question.objects.filter(job_role=session.job_role).exclude(id__in=answered_ids).order_by('?').first()

        if next_question:
            return redirect('question', session_id=session.id, question_id=next_question.id)
        else:
            # All questions answered - redirect to evaluation
            return redirect('test_result', session_id=session.id)
        
        

    return render(request, 'competency/test_question.html', {
        'session': session,
        'question': question
    })

@login_required
def test_result(request, session_id):
    session = CompetencyTestSession.objects.get(id=session_id, user=request.user)
    answers = Answer.objects.filter(session=session)
    
    # Batch evaluate all answers using AI if not already evaluated
    evaluation_failed = False
    if not session.completed:
        from .utils import evaluate_all_answers
        try:
            scores = evaluate_all_answers(answers)
            if not scores:
                evaluation_failed = True
            else:
                # Update each answer with its score
                for answer in answers:
                    if answer.id in scores:
                        score = scores[answer.id]
                        answer.is_correct = score >= 0.5
                        answer.save()
        except Exception:
            evaluation_failed = True
    
    # Calculate final score
    total_answers = answers.count()
    correct_answers = answers.filter(is_correct=True).count()
    
    if total_answers > 0:
        score_percentage = round((correct_answers / total_answers) * 100, 2)
    else:
        score_percentage = 0
    
    session.score = score_percentage
    session.completed = True
    session.save()
    
    from users.models import ActivityLog
    ActivityLog.objects.create(
        user=request.user, action='test_completed',
        detail=f'{session.job_role} — {session.score}%'
    )
    
    return render(request, 'competency/test_result.html', {
        'session': session,
        'answers': answers,
        'correct_count': correct_answers,
        'total_count': total_answers,
        'evaluation_failed': evaluation_failed,
    }) 
    
@login_required
def history_test(request):
    sessions = CompetencyTestSession.objects.filter(user=request.user)
    return render(request, 'competency/history_test.html', {'sessions': sessions})



# @login_required
# def history_graph(request):
#     sessions = CompetencyTestSession.objects.filter(user=request.user).order_by('created_at')

#     # Preprocess performance data
#     for session in sessions:
#         answers = session.answer_set.all()
#         total = answers.count()
#         correct = answers.filter(is_correct=True).count()
#         percentage = round((correct / total) * 100) if total > 0 else 0

#         # Attach data to each session
#         session.total = total
#         session.correct = correct
#         session.percentage = percentage

#     return render(request, 'competency/graphs.html', {'sessions': sessions})
from django.db.models import Count, Case, When, IntegerField, FloatField
from django.db.models.functions import Cast


@login_required
def history_graph(request):
    sessions = CompetencyTestSession.objects.filter(user=request.user).annotate(
        total_questions=Count('answer'),
        correct_answers=Count(Case(When(answer__is_correct=True, then=1))),
        accuracy=Cast('correct_answers', FloatField()) / Cast('total_questions', FloatField()) * 100
    ).order_by('created_at')
    
    # Calculate totals
    total_correct = sum(session.correct_answers for session in sessions)
    total_questions = sum(session.total_questions for session in sessions)
    overall_accuracy = round((total_correct / total_questions) * 100, 1) if total_questions > 0 else 0
    
    return render(request, 'competency/graphs.html', {
        'sessions': sessions,
        'total_correct': total_correct,
        'overall_accuracy': overall_accuracy
    })


# ─── Interview Prep ───────────────────────────────────────────────

import google.generativeai as genai
from django.conf import settings
from .models import InterviewQuestion
import json as _json


@login_required
def interview_prep_view(request):
    """Generate interview prep questions for a target role."""
    questions = InterviewQuestion.objects.filter(user=request.user)[:20]

    if request.method == 'POST':
        job_role = request.POST.get('job_role', '').strip()
        category = request.POST.get('category', 'technical')
        if not job_role:
            return render(request, 'competency/interview_prep.html', {
                'questions': questions, 'error': 'Please enter a job role.'
            })

        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            prompt = f"""Generate 5 {category} interview questions for the role of "{job_role}".
For each question, provide a concise model answer.

Return as a JSON array:
[
  {{"question": "...", "answer": "..."}},
  ...
]
Only return valid JSON. No markdown fences. No commentary."""

            response = model.generate_content(prompt)
            raw = response.text.strip()
            if raw.startswith('```'):
                raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            items = _json.loads(raw)

            from users.models import ActivityLog
            for item in items:
                InterviewQuestion.objects.create(
                    user=request.user,
                    job_role=job_role,
                    category=category,
                    question_text=item.get('question', ''),
                    model_answer=item.get('answer', ''),
                )
            ActivityLog.objects.create(user=request.user, action='interview_prep', detail=job_role)

            questions = InterviewQuestion.objects.filter(user=request.user)[:20]
            return render(request, 'competency/interview_prep.html', {
                'questions': questions,
                'success': f'Generated 5 {category} questions for {job_role}!',
                'job_role': job_role,
            })
        except Exception:
            return render(request, 'competency/interview_prep.html', {
                'questions': questions,
                'error': 'The AI service is temporarily unavailable. Please try again later.'
            })

    return render(request, 'competency/interview_prep.html', {'questions': questions})


@login_required
def interview_practice_view(request, pk):
    """Practice answering a specific interview question and get AI feedback."""
    question = InterviewQuestion.objects.get(pk=pk, user=request.user)

    if request.method == 'POST':
        user_answer = request.POST.get('user_answer', '').strip()
        if user_answer:
            question.user_answer = user_answer
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel(settings.GEMINI_MODEL)
                prompt = f"""You are an expert interview coach. Evaluate the following answer.

Question: {question.question_text}
Model Answer: {question.model_answer}
User's Answer: {user_answer}

Return a JSON object:
{{
  "score": 0.75,
  "feedback": "Specific 2-3 sentence feedback on the answer."
}}
Only return valid JSON. No markdown."""

                response = model.generate_content(prompt)
                raw = response.text.strip()
                if raw.startswith('```'):
                    raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
                result = _json.loads(raw)
                question.score = result.get('score', 0)
                question.feedback = result.get('feedback', '')
            except Exception:
                question.feedback = 'Could not generate feedback. AI service is temporarily unavailable.'
                question.score = 0
            question.save()

    return render(request, 'competency/interview_practice.html', {'question': question})


@login_required
def clear_interview_questions(request):
    """Clear all interview prep questions for the user."""
    InterviewQuestion.objects.filter(user=request.user).delete()
    return redirect('interview_prep')