"""
views.py
--------
Three endpoints Django owns in the voice flow:

  POST /mock-interview/start/
    → Creates InterviewSession, returns session_id + WS URL to browser.
      No JWT — browser passes session_id directly as a query param.

  POST /mock-interview/end/          [internal — called by FastAPI only]
    → Receives transcript, saves it, generates LLM feedback.

  GET  /mock-interview/results/<session_id>/
    → Returns feedback + transcript to the frontend.
"""

import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from groq import Groq

from .models import InterviewSession
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def interview_page(request):
    return render(request, 'mock_interview/interview.html')

# ---------------------------------------------------------------------------
# 1. Start session
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def start_interview(request):
    data       = json.loads(request.body)
    job_role   = data.get("job_role", "Software Engineer")
    difficulty = data.get("difficulty", "medium")

    session = InterviewSession.objects.create(
        user=request.user,
        job_role=job_role,
        difficulty=difficulty,
        status="pending",
    )

    ws_url = (
        f"ws://localhost:8001/interview"
        f"?session_id={session.id}"
        f"&job_role={job_role}"
        f"&difficulty={difficulty}"
    )

    return JsonResponse({
        "session_id": str(session.id),
        "ws_url":     ws_url,
    })


# ---------------------------------------------------------------------------
# 2. End session — internal callback from FastAPI
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def end_interview(request):
    secret = request.headers.get("X-Internal-Secret", "")
    if secret != settings.DJANGO_INTERNAL_SECRET:
        return JsonResponse({"error": "Forbidden"}, status=403)

    data         = json.loads(request.body)
    session_id   = data.get("session_id")
    conversation = data.get("conversation", [])

    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)

    session.transcript = conversation
    session.status     = "completed"
    session.feedback   = _generate_feedback(conversation, session.job_role, session.difficulty)
    session.save()

    return JsonResponse({"status": "saved"})


def _generate_feedback(conversation: list[dict], job_role: str, difficulty: str) -> str:
    client = Groq(api_key=settings.GROQ_API_KEY)

    transcript_text = "\n".join(
        f"{t['role'].capitalize()}: {t['content']}" for t in conversation
    )

    prompt = f"""You are an expert interview coach. Review this mock interview transcript
for a {job_role} role at {difficulty} difficulty.

Transcript:
{transcript_text}

Provide structured feedback covering:
1. Technical accuracy
2. Communication clarity
3. Use of examples and STAR structure
4. Three specific strengths
5. Three specific areas for improvement

Be direct and constructive. No bullet points — write in natural prose."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.5,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# 3. Get results
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["GET"])
def get_results(request, session_id):
    try:
        session = InterviewSession.objects.get(id=session_id, user=request.user)
    except InterviewSession.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if session.status != "completed":
        return JsonResponse({"status": session.status, "ready": False})

    return JsonResponse({
        "status":     "completed",
        "ready":      True,
        "job_role":   session.job_role,
        "difficulty": session.difficulty,
        "feedback":   session.feedback,
        "transcript": session.transcript,
        "created_at": session.created_at.isoformat(),
    })