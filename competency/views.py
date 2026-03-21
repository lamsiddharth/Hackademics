import json as _json
from urllib.parse import unquote

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Case, When, FloatField
from django.db.models.functions import Cast
from django.http import HttpResponse

from config.ai_client import get_gemini_response, GeminiError
from users.models import ActivityLog
from .models import (
    Question, CompetencyTestSession, Answer,
    InterviewQuestion, InterviewSession,
)
from .utils import generate_questions_for_job, save_generated_questions, evaluate_all_answers


# ─── Competency Test ───────────────────────────────────────────

@login_required
def generate_test_questions(request):
    if request.method == 'POST':
        job_role = request.POST.get('job_role')
        seniority = request.POST.get('seniority', 'mid')
        company_type = request.POST.get('company_type', '')
        if job_role:
            try:
                raw_output = generate_questions_for_job(job_role, seniority, company_type)
                save_generated_questions(raw_output, job_role)
                return redirect('view_questions', job_role=job_role)
            except Exception:
                return render(request, 'competency/generate_test.html', {
                    'error': 'The AI service is temporarily unavailable. Please try again later.'
                })
    return render(request, 'competency/generate_test.html')


def view_questions(request, job_role):
    job_role = unquote(job_role)
    questions = Question.objects.filter(job_role=job_role)
    return render(request, 'competency/view_questions.html', {'questions': questions, 'job_role': job_role})


@login_required
def start_test(request, job_role):
    job_role = unquote(job_role)
    seniority = request.GET.get('seniority', 'mid')
    company_type = request.GET.get('company_type', '')

    question = Question.objects.filter(job_role=job_role).order_by('?').first()

    if not question:
        try:
            raw_output = generate_questions_for_job(job_role, seniority, company_type)
            save_generated_questions(raw_output, job_role)
            question = Question.objects.filter(job_role=job_role).order_by('?').first()
        except Exception:
            pass

    if not question:
        messages.error(request, f'No questions available for "{job_role}". Please generate questions first.')
        return redirect('generate_test')

    session = CompetencyTestSession.objects.create(
        user=request.user, job_role=job_role,
        seniority=seniority, company_type=company_type,
    )
    return redirect('question', session_id=session.id, question_id=question.id)


@login_required
def question_view(request, session_id, question_id):
    session = get_object_or_404(CompetencyTestSession, id=session_id, user=request.user)
    question = get_object_or_404(Question, id=question_id)

    if request.method == 'POST':
        answer_text = request.POST.get('answer', '')
        Answer.objects.create(
            session=session, question=question,
            selected_answer=answer_text, is_correct=False,
        )

        answered_ids = Answer.objects.filter(session=session).values_list('question_id', flat=True)
        next_question = Question.objects.filter(
            job_role=session.job_role
        ).exclude(id__in=answered_ids).order_by('?').first()

        if next_question:
            return redirect('question', session_id=session.id, question_id=next_question.id)
        else:
            return redirect('test_result', session_id=session.id)

    # Count progress
    answered_count = Answer.objects.filter(session=session).count()
    total_questions = Question.objects.filter(job_role=session.job_role).count()

    return render(request, 'competency/test_question.html', {
        'session': session,
        'question': question,
        'answered_count': answered_count,
        'total_questions': total_questions,
    })


@login_required
def test_result(request, session_id):
    session = get_object_or_404(CompetencyTestSession, id=session_id, user=request.user)
    answers = Answer.objects.filter(session=session).select_related('question')

    evaluation_failed = False
    if not session.completed:
        try:
            results = evaluate_all_answers(answers)
            if not results:
                evaluation_failed = True
            else:
                for answer in answers:
                    if answer.id in results:
                        ev = results[answer.id]
                        answer.score = ev['score']
                        answer.is_correct = ev['score'] >= 0.5
                        answer.feedback = _json.dumps(ev)
                        answer.strengths = ev.get('strengths', [])
                        answer.gaps = ev.get('gaps', [])
                        answer.skill_tags = ev.get('skill_tags', [])
                        answer.model_answer = ev.get('model_answer', '')
                        answer.save()
        except Exception:
            evaluation_failed = True

    total_answers = answers.count()
    correct_answers = answers.filter(is_correct=True).count()
    score_percentage = round((correct_answers / total_answers) * 100, 2) if total_answers > 0 else 0

    session.score = score_percentage
    session.completed = True
    session.save()

    ActivityLog.objects.create(
        user=request.user, action='test_completed',
        detail=f'{session.job_role} — {session.score}%'
    )

    # Build category scores for radar chart
    category_scores = {}
    for answer in answers:
        try:
            extra = _json.loads(answer.question.correct_answer or '{}')
            cat = extra.get('category', 'general')
        except (ValueError, TypeError):
            cat = 'general'
        if cat not in category_scores:
            category_scores[cat] = {'total': 0, 'sum': 0}
        category_scores[cat]['total'] += 1
        category_scores[cat]['sum'] += (answer.score or 0)

    radar_labels = []
    radar_values = []
    for cat, data in category_scores.items():
        label = cat.replace('_', ' ').title()
        radar_labels.append(label)
        radar_values.append(round((data['sum'] / data['total']) * 100) if data['total'] > 0 else 0)

    # Collect all skill tags from answers
    all_skills = set()
    for answer in answers:
        if answer.skill_tags:
            all_skills.update(answer.skill_tags)

    return render(request, 'competency/test_result.html', {
        'session': session,
        'answers': answers,
        'correct_count': correct_answers,
        'total_count': total_answers,
        'evaluation_failed': evaluation_failed,
        'radar_labels': _json.dumps(radar_labels),
        'radar_values': _json.dumps(radar_values),
        'all_skills': list(all_skills),
    })


@login_required
def history_test(request):
    sessions = CompetencyTestSession.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'competency/history_test.html', {'sessions': sessions})


@login_required
def history_graph(request):
    sessions = CompetencyTestSession.objects.filter(user=request.user).annotate(
        total_questions=Count('answer'),
        correct_answers=Count(Case(When(answer__is_correct=True, then=1))),
        accuracy=Cast('correct_answers', FloatField()) / Cast('total_questions', FloatField()) * 100
    ).order_by('created_at')

    total_correct = sum(s.correct_answers for s in sessions)
    total_questions = sum(s.total_questions for s in sessions)
    overall_accuracy = round((total_correct / total_questions) * 100, 1) if total_questions > 0 else 0

    return render(request, 'competency/graphs.html', {
        'sessions': sessions,
        'total_correct': total_correct,
        'overall_accuracy': overall_accuracy,
    })


# ─── Interview Prep ───────────────────────────────────────────

@login_required
def interview_prep_view(request):
    """Generate interview prep questions for a target role."""
    questions = InterviewQuestion.objects.filter(user=request.user)[:20]

    if request.method == 'POST':
        job_input = request.POST.get('job_role', '').strip()
        category = request.POST.get('category', 'technical')
        if not job_input:
            return render(request, 'competency/interview_prep.html', {
                'questions': questions, 'error': 'Please enter a job role.'
            })

        # If user pasted a long job description, extract a short title
        if len(job_input) > 120:
            try:
                title_prompt = f'Extract only the job title (max 8 words) from this job posting. Return ONLY the title, nothing else:\n\n{job_input[:1000]}'
                job_role = get_gemini_response(title_prompt).strip().strip('"').strip("'")
            except GeminiError:
                job_role = job_input[:80]
            job_description = job_input
        else:
            job_role = job_input
            job_description = job_input

        try:
            prompt = f"""Generate 5 {category} interview questions for the role of "{job_role}".
{"Job Description context: " + job_description[:2000] if len(job_description) > 120 else ""}
For each question, provide a concise model answer.

Return as a JSON array:
[
  {{"question": "...", "answer": "..."}},
  ...
]
Only return valid JSON. No markdown fences. No commentary."""

            items = get_gemini_response(prompt, parse_json=True)

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
        except (GeminiError, Exception):
            return render(request, 'competency/interview_prep.html', {
                'questions': questions,
                'error': 'The AI service is temporarily unavailable. Please try again later.'
            })

    return render(request, 'competency/interview_prep.html', {'questions': questions})


@login_required
def interview_practice_view(request, pk):
    """Practice answering a specific interview question and get AI feedback."""
    question = get_object_or_404(InterviewQuestion, pk=pk, user=request.user)

    if request.method == 'POST':
        user_answer = request.POST.get('user_answer', '').strip()
        if user_answer:
            question.user_answer = user_answer
            try:
                prompt = f"""You are an expert interview coach. Evaluate the following answer.

Question: {question.question_text}
Model Answer: {question.model_answer}
User's Answer: {user_answer}

Return a JSON object:
{{
  "score": 0.75,
  "feedback": "Specific 2-3 sentence feedback on the answer.",
  "confidence": 0.7
}}
Only return valid JSON. No markdown."""

                result = get_gemini_response(prompt, parse_json=True)
                question.score = result.get('score', 0)
                question.feedback = result.get('feedback', '')
                question.confidence = result.get('confidence', question.score)
            except (GeminiError, Exception):
                question.feedback = 'Could not generate feedback. AI service is temporarily unavailable.'
                question.score = 0
            question.save()

    return render(request, 'competency/interview_practice.html', {'question': question})


@login_required
def clear_interview_questions(request):
    """Clear all interview prep questions for the user."""
    InterviewQuestion.objects.filter(user=request.user).delete()
    return redirect('interview_prep')


# ─── Interview Simulator ──────────────────────────────────────

@login_required
def interview_simulator_start(request):
    """Start a timed interview simulation with 5 questions."""
    if request.method == 'POST':
        job_input = request.POST.get('job_role', '').strip()
        category = request.POST.get('category', 'technical')

        if not job_input:
            messages.error(request, 'Please enter a job role.')
            return redirect('interview_prep')

        # Extract short title from long job descriptions
        if len(job_input) > 120:
            try:
                title_prompt = f'Extract only the job title (max 8 words) from this job posting. Return ONLY the title, nothing else:\n\n{job_input[:1000]}'
                job_role = get_gemini_response(title_prompt).strip().strip('"').strip("'")
            except GeminiError:
                job_role = job_input[:80]
            job_description = job_input
        else:
            job_role = job_input
            job_description = job_input

        try:
            prompt = f"""Generate 5 {category} interview questions for a "{job_role}" position.
{"Job Description context: " + job_description[:2000] if len(job_description) > 120 else ""}
These should be challenging and realistic, like a real interview.
Mix of conceptual and scenario-based questions.

Return as a JSON array:
[
  {{"question": "...", "answer": "A comprehensive model answer (3-4 sentences)"}},
  ...
]
Only return valid JSON. No markdown fences."""

            items = get_gemini_response(prompt, parse_json=True)

            session = InterviewSession.objects.create(
                user=request.user, job_role=job_role,
                category=category, mode='simulator',
            )

            for item in items:
                InterviewQuestion.objects.create(
                    user=request.user,
                    session=session,
                    job_role=job_role,
                    category=category,
                    question_text=item.get('question', ''),
                    model_answer=item.get('answer', ''),
                )

            return redirect('interview_simulator_question', session_id=session.id, question_index=0)

        except (GeminiError, Exception):
            messages.error(request, 'AI service temporarily unavailable. Please try again.')
            return redirect('interview_prep')

    return redirect('interview_prep')


@login_required
def interview_simulator_question(request, session_id, question_index):
    """Display a timed question in the simulator. Forward-only flow."""
    session = get_object_or_404(InterviewSession, id=session_id, user=request.user)
    questions = list(session.questions.order_by('id'))

    if question_index >= len(questions):
        return redirect('interview_simulator_result', session_id=session.id)

    question = questions[question_index]

    if request.method == 'POST':
        user_answer = request.POST.get('user_answer', '').strip()
        time_taken = request.POST.get('time_taken', 0)
        question.user_answer = user_answer or '(No answer provided)'
        question.time_taken = int(time_taken) if time_taken else 0
        question.save()

        next_index = question_index + 1
        if next_index >= len(questions):
            return redirect('interview_simulator_result', session_id=session.id)
        return redirect('interview_simulator_question', session_id=session.id, question_index=next_index)

    return render(request, 'competency/interview_simulator.html', {
        'session': session,
        'question': question,
        'question_index': question_index,
        'total_questions': len(questions),
        'progress_pct': round((question_index / len(questions)) * 100),
    })


@login_required
def interview_simulator_result(request, session_id):
    """Evaluate all simulator answers and show hire/no-hire verdict."""
    session = get_object_or_404(InterviewSession, id=session_id, user=request.user)
    questions = list(session.questions.order_by('id'))

    if not session.completed:
        # Build evaluation prompt
        qa_text = ""
        for i, q in enumerate(questions, 1):
            qa_text += f"\nQ{i}: {q.question_text}\nModel Answer: {q.model_answer}\nCandidate Answer: {q.user_answer}\n"

        prompt = f"""You are a senior hiring manager evaluating interview responses for a {session.job_role} position.

{qa_text}

Evaluate EACH answer and provide an overall hiring decision.

Return a JSON object:
{{
  "evaluations": [
    {{
      "score": 0.75,
      "confidence": 0.8,
      "feedback": "Brief feedback on this answer"
    }}
  ],
  "overall_score": 72,
  "hire_decision": "hire|no_hire|maybe",
  "summary": "2-3 sentence overall assessment of the candidate"
}}
Only return valid JSON. No markdown."""

        try:
            result = get_gemini_response(prompt, parse_json=True)
            evaluations = result.get('evaluations', [])

            for i, q in enumerate(questions):
                if i < len(evaluations):
                    ev = evaluations[i]
                    q.score = ev.get('score', 0)
                    q.confidence = ev.get('confidence', q.score)
                    q.feedback = ev.get('feedback', '')
                    q.save()

            session.overall_score = result.get('overall_score', 0)
            session.hire_decision = result.get('hire_decision', 'maybe')
            session.completed = True
            session.save()

            ActivityLog.objects.create(
                user=request.user, action='test_completed',
                detail=f'Interview Simulator: {session.job_role} — {session.hire_decision}'
            )

        except (GeminiError, Exception):
            session.overall_score = 0
            session.hire_decision = 'error'
            session.completed = True
            session.save()

    summary = ''
    try:
        # Try to get summary from last API call result
        prompt2 = f"In 2 sentences, summarize a candidate who scored {session.overall_score}/100 on a {session.job_role} interview with verdict: {session.hire_decision}."
        summary = get_gemini_response(prompt2)
    except GeminiError:
        summary = f"The candidate scored {session.overall_score}/100 for the {session.job_role} position."

    return render(request, 'competency/interview_simulator_result.html', {
        'session': session,
        'questions': questions,
        'summary': summary,
    })


@login_required
def download_interview_report(request, session_id):
    """Generate and download an interview report card PDF."""
    import weasyprint
    from django.template.loader import render_to_string

    session = get_object_or_404(InterviewSession, id=session_id, user=request.user)
    questions = list(session.questions.order_by('id'))

    html_string = render_to_string('competency/interview_report_pdf.html', {
        'session': session,
        'questions': questions,
        'user': request.user,
    })

    pdf = weasyprint.HTML(string=html_string).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Interview_Report_{session.job_role}.pdf"'
    return response
