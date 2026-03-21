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
    data          = json.loads(request.body)
    prep_mode     = data.get("prep_mode", "subjective")
    target_role   = data.get("target_role")
    target_company = data.get("target_company")
    tech_stack    = data.get("tech_stack")
    current_profile = data.get("current_profile")
    if prep_mode not in {"subjective", "interactive"}:
        prep_mode = "subjective"

    job_role      = data.get("job_role") or target_role or "Software Engineer"
    difficulty    = data.get("difficulty", "medium")

    session = InterviewSession.objects.create(
        user=request.user,
        job_role=job_role,
        difficulty=difficulty,
        prep_mode=prep_mode,
        target_role=target_role,
        target_company=target_company,
        tech_stack=tech_stack,
        current_profile=current_profile,
        status="pending",
    )

    params = {
        "session_id": str(session.id),
        "job_role": job_role,
        "difficulty": difficulty,
        "prep_mode": prep_mode,
    }
    if target_role:
        params["target_role"] = target_role
    if target_company:
        params["target_company"] = target_company
    if tech_stack:
        params["tech_stack"] = tech_stack
    if current_profile:
        params["current_profile"] = current_profile

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
    prep_mode    = data.get("prep_mode")
    profile      = data.get("profile", {}) or {}

    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        return JsonResponse({"error": "Session not found"}, status=404)

    if prep_mode and prep_mode in {"subjective", "interactive"}:
        session.prep_mode = prep_mode

    target_role = profile.get("target_role")
    target_company = profile.get("target_company")
    tech_stack = profile.get("tech_stack")
    current_profile = profile.get("current_profile")

    if target_role:
        session.target_role = target_role
    if target_company:
        session.target_company = target_company
    if tech_stack:
        session.tech_stack = tech_stack
    if current_profile:
        session.current_profile = current_profile

    # Always save transcript first — even if feedback generation fails
    session.transcript = conversation
    session.status     = "completed"
    session.save()

    # Generate feedback separately so a Groq failure doesn't lose the transcript
    try:
        session.feedback = _generate_feedback(
            conversation,
            session.job_role,
            session.difficulty,
            session.prep_mode,
            {
                "target_role": session.target_role,
                "target_company": session.target_company,
                "tech_stack": session.tech_stack,
                "current_profile": session.current_profile,
            },
        )
        session.save(update_fields=["feedback"])
    except Exception as e:
        print(f"[mock_interview] feedback generation failed for {session.id}: {e}")

    return JsonResponse({"status": "saved"})


# ---------------------------------------------------------------------------
# 3a. Generate / regenerate report for a session
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def generate_report(request, session_id):
    try:
        session = InterviewSession.objects.get(id=session_id, user=request.user)
    except InterviewSession.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if session.status != "completed":
        return JsonResponse({"error": "Interview not completed yet"}, status=400)

    if not session.transcript:
        return JsonResponse({"error": "No transcript available"}, status=400)

    try:
        session.feedback = _generate_feedback(
            session.transcript,
            session.job_role,
            session.difficulty,
            session.prep_mode,
            {
                "target_role": session.target_role,
                "target_company": session.target_company,
                "tech_stack": session.tech_stack,
                "current_profile": session.current_profile,
            },
        )
        session.save(update_fields=["feedback"])
        return JsonResponse({"status": "ok", "feedback": session.feedback})
    except Exception as e:
        return JsonResponse({"error": f"Feedback generation failed: {e}"}, status=500)


# ---------------------------------------------------------------------------
# 3b. Interview history
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["GET"])
def interview_history(request):
    sessions = InterviewSession.objects.filter(
        user=request.user,
        status="completed",
    ).order_by("-created_at")[:20]

    return JsonResponse({
        "sessions": [
            {
                "id": str(s.id),
                "job_role": s.job_role,
                "difficulty": s.difficulty,
                "prep_mode": s.prep_mode,
                "target_role": s.target_role,
                "target_company": s.target_company,
                "has_feedback": bool(s.feedback),
                "created_at": s.created_at.isoformat(),
            }
            for s in sessions
        ]
    })


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

    if prep_mode == "interactive":
        profile_block = "\n".join([
            f"Target role: {profile.get('target_role') or 'N/A'}",
            f"Target company: {profile.get('target_company') or 'N/A'}",
            f"Tech stack: {profile.get('tech_stack') or 'N/A'}",
            f"Current profile: {profile.get('current_profile') or 'N/A'}",
        ])

        prompt = f"""You are a senior interview coach with 15+ years of experience at top tech companies.
Review this live mock interview transcript for a {job_role} role at {difficulty} difficulty.

Candidate profile:
{profile_block}

Full transcript:
{transcript_text}

Write a detailed performance report in exactly this format:

OVERALL SUMMARY
A 3-4 sentence overview of how the candidate performed overall.

TECHNICAL DEPTH (score: X/10)
Evaluate accuracy, depth of knowledge, and ability to explain concepts clearly. Reference specific answers.

COMMUNICATION & STRUCTURE (score: X/10)
Assess clarity, use of STAR method for behavioral questions, and ability to structure responses logically.

KEY STRENGTHS
List 3-4 specific strengths with evidence from the transcript.

AREAS FOR IMPROVEMENT
List 3-4 specific areas to work on with actionable advice.

COMPANY FIT ASSESSMENT
How well the candidate's profile aligns with the target role and company.

PREPARATION ROADMAP
3-5 concrete next steps the candidate should take before their real interview.

OVERALL SCORE: X/10

Be specific, reference actual answers from the transcript, and give actionable feedback."""
    else:
        prompt = f"""You are a senior interview coach with 15+ years of experience at top tech companies.
Review this mock interview transcript for a {job_role} role at {difficulty} difficulty.

Full transcript:
{transcript_text}

Write a detailed performance report in exactly this format:

OVERALL SUMMARY
A 3-4 sentence overview of how the candidate performed.

TECHNICAL ACCURACY (score: X/10)
Evaluate correctness and depth of technical answers. Reference specific responses.

COMMUNICATION CLARITY (score: X/10)
Assess how well the candidate articulated ideas, used examples, and structured responses (STAR method).

KEY STRENGTHS
List 3-4 specific strengths with evidence from the transcript.

AREAS FOR IMPROVEMENT
List 3-4 specific areas to work on with actionable recommendations.

PREPARATION ROADMAP
3-5 concrete next steps to improve before a real interview.

OVERALL SCORE: X/10

Be specific, reference actual answers, and provide actionable feedback."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.4,
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
        "has_feedback": bool(session.feedback),
        "job_role":   session.job_role,
        "difficulty": session.difficulty,
        "prep_mode":  session.prep_mode,
        "target_role": session.target_role,
        "target_company": session.target_company,
        "tech_stack": session.tech_stack,
        "current_profile": session.current_profile,
        "feedback":   session.feedback or "",
        "transcript": session.transcript,
        "created_at": session.created_at.isoformat(),
    })