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
from urllib.parse import urlencode
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from groq import Groq

from .models import InterviewSession


# ---------------------------------------------------------------------------
# 1. Start session
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def start_interview(request):
    data       = json.loads(request.body)
    job_role   = data.get("job_role") or data.get("target_role") or "Software Engineer"
    difficulty = data.get("difficulty", "medium")
    prep_mode  = data.get("prep_mode", "subjective")
    target_role = data.get("target_role", "")
    target_company = data.get("target_company", "")
    tech_stack = data.get("tech_stack", "")
    current_profile = data.get("current_profile", "")

    session = InterviewSession.objects.create(
        user=request.user,
        job_role=job_role,
        difficulty=difficulty,
        status="pending",
    )

    params = {
        "session_id": str(session.id),
        "job_role": job_role,
        "difficulty": difficulty,
        "prep_mode": prep_mode,
        "target_role": target_role,
        "target_company": target_company,
        "tech_stack": tech_stack,
        "current_profile": current_profile,
    }

    ws_url = f"ws://localhost:8001/interview?{urlencode(params)}"

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
    prep_mode    = data.get("prep_mode", "subjective")
    profile      = data.get("profile", {})

    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)

    session.transcript = conversation
    session.status     = "completed"
    session.feedback   = _generate_feedback(
        conversation,
        session.job_role,
        session.difficulty,
        prep_mode,
        profile,
    )
    session.save()

    return JsonResponse({"status": "saved"})


def _format_profile_summary(profile: dict) -> str:
    lines = []
    target_role = profile.get("target_role") or ""
    target_company = profile.get("target_company") or ""
    tech_stack = profile.get("tech_stack") or ""
    current_profile = profile.get("current_profile") or ""

    if target_role:
        lines.append(f"Target role: {target_role}")
    if target_company:
        lines.append(f"Target company: {target_company}")
    if tech_stack:
        lines.append(f"Tech stack: {tech_stack}")
    if current_profile:
        lines.append(f"Current profile: {current_profile}")

    if not lines:
        return "Not provided."

    return "\n".join(lines)


def _generate_feedback(
    conversation: list[dict],
    job_role: str,
    difficulty: str,
    prep_mode: str,
    profile: dict,
) -> str:
    client = Groq(api_key=settings.GROQ_API_KEY)

    transcript_text = "\n".join(
        f"{t['role'].capitalize()}: {t['content']}" for t in conversation
    )

    profile_summary = _format_profile_summary(profile)

    prompt = f"""You are an expert interview coach. Review this mock interview transcript
for a {job_role} role at {difficulty} difficulty.

Prep mode: {prep_mode}
Candidate profile:
{profile_summary}

Transcript:
{transcript_text}

Write a final performance report with the following sections, each in 2-4 sentences:
1. Summary
2. Strengths
3. Gaps and risks
4. STAR/structure usage
5. Next-step recommendations

Also include a single overall score from 1 to 10 in the format "Score: X/10" on its own line.
Be direct and constructive. Use short paragraphs. No bullet points."""

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
