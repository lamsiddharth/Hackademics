# recommendations/views.py
from urllib.parse import unquote

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
import requests
import json

from config.ai_client import get_gemini_response, GeminiError
from recommendations.ollama_utils import match_live_jobs
from users.models import UserProfile
from resume_builder.models import resume
from .utils import generate_learning_roadmap, extract_skills_from_profile, fetch_jobs


@login_required
def extract_skills_view(request):
    try:
        user_profile = request.user.userprofile  # Or UserProfile.objects.get(user=request.user)
        
        if request.method == "POST":
            profile_data = f"""
Name: {request.user.get_full_name()}
Education: {user_profile.education}
Experience: {user_profile.experience}
Skills: {user_profile.skills}
Projects: {user_profile.projects}
Achievements: {user_profile.achievements}
"""
            try:
                skills = extract_skills_from_profile(profile_data)
                user_profile.extracted_skills = skills
                user_profile.save()
            except Exception:
                return render(request, "recommendations/extract_skills.html", {
                    "profile": user_profile,
                    "error": "The AI service is temporarily unavailable. Please try again later or contact support."
                })
            
            return render(request, "recommendations/extracted_skills.html", {
                "skills": skills
            })

        return render(request, "recommendations/extract_skills.html", {
            "profile": user_profile
        })

    except ObjectDoesNotExist:
        return redirect('edit_profile')
        
        
@login_required
def live_job_match_view(request):
    profile = UserProfile.objects.get(user=request.user)
    skills = profile.extracted_skills or []

    if not skills:
        return render(request, "recommendations/job_match.html", {
            "error": "Please extract your skills first."
        })

    # Use top skills as query (or a fixed job title from user input)
    query = "+".join(skills[:3])  # limit query length
    api_url = f"https://remotive.io/api/remote-jobs?search={query}"

    try:
        res = requests.get(api_url)
        data = res.json()
        jobs = data.get("jobs", [])[:10]  # limit to 10 for now
    except:
        jobs = []

    job_data = [{"title": j["title"], "description": j["description"]} for j in jobs]
    matches = match_live_jobs(skills, job_data)

    matched_jobs = []
    for match in matches:
        index = match.get("index", 0) - 1
        if 0 <= index < len(job_data):
            job = jobs[index]
            matched_jobs.append({
                "title": job["title"],
                "description": job["description"],
                "url": job["url"],
                "reason": match.get("reason")
            })

    return render(request, "recommendations/job-match.html", {
        "matched_jobs": matched_jobs
    })
    
def parse_roadmap_with_gemini(roadmap_text: str):
    prompt = f"""
You are a helpful assistant.

Take the following roadmap text and convert it into structured JSON. Each step should be a short sentence or phrase with a `step` and a `completed` flag (default to false).

Roadmap:
\"\"\"
{roadmap_text}
\"\"\"

Output format:
[
  {{
    "step": "First task",
    "completed": false
  }},
  {{
    "step": "Second task",
    "completed": false
  }}
]

Only return valid JSON. No commentary. No markdown or code fences. Just the JSON array.
"""

    try:
        return get_gemini_response(prompt, parse_json=True)
    except GeminiError as e:
        return [{"step": f"Error parsing roadmap: {str(e)}", "completed": False}]
    
@login_required
def create_roadmap(request, job_title):
    from .models import Roadmap1
    job_title = unquote(job_title)

    # Regenerate if requested via POST
    if request.method == 'POST' and request.POST.get('regenerate'):
        Roadmap1.objects.filter(user=request.user, title=job_title).delete()
    else:
        # Check for existing roadmap for this user + job title
        existing = Roadmap1.objects.filter(user=request.user, title=job_title).first()
        if existing:
            return render(request, 'recommendations/roadmap.html', {
                'roadmap': existing,
                'steps': existing.steps,
                'response': existing.raw_response,
                'job_title': job_title,
            })

    latest_resume = resume.objects.filter(user=request.user).order_by('-created_at').first()

    if not latest_resume:
        return render(request, 'recommendations/roadmap.html', {
            'steps': [],
            'response': '',
            'error': 'No resume found. Please generate a resume first.'
        })

    skills = latest_resume.skills
    projects = latest_resume.projects
    experience = latest_resume.experience

    try:
        response = generate_learning_roadmap(skills, projects, experience, job_title)
        steps = parse_roadmap_with_gemini(response)
    except Exception as e:
        error_msg = str(e)
        if 'API_KEY' in error_msg or 'api_key' in error_msg.lower() or 'InvalidArgument' in error_msg or '400' in error_msg:
            friendly = 'The AI service is temporarily unavailable due to an API configuration issue. Please try again later or contact support.'
        else:
            friendly = 'An unexpected error occurred while generating your roadmap. Please try again later.'
        return render(request, 'recommendations/roadmap.html', {
            'steps': [],
            'response': '',
            'error': friendly
        })

    # Save to DB so we don't regenerate
    roadmap_obj = Roadmap1.objects.create(
        user=request.user,
        title=job_title,
        raw_response=response,
        steps=steps,
    )

    return render(request, 'recommendations/roadmap.html', {
        'roadmap': roadmap_obj,
        'steps': steps,
        'response': response,
        'job_title': job_title,
    })


@login_required
def target_job_view(request):
    
    return render(request, 'recommendations/targetjob.html')
    
@login_required
def job_recommendation_view(request):
    try:
        myprofile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return render(request, 'recommendations/topjobs.html', {'jobs': [], 'error': 'Please complete your profile first.'})

    skills = myprofile.skills
    experience = myprofile.experience
    projects = myprofile.projects
    location = myprofile.location

    try:
        keywords = extract_skills_from_profile(location, skills, experience, projects)
        jobs = fetch_jobs(keywords, location)
    except Exception:
        return render(request, 'recommendations/topjobs.html', {
            'jobs': [],
            'error': 'The AI service is temporarily unavailable. Please try again later.'
        })

    return render(request, 'recommendations/topjobs.html', {'jobs': jobs})


@login_required
def save_job_view(request):
    """Save/bookmark a job via AJAX POST, auto-trigger gap analysis."""
    if request.method == 'POST':
        from .models import SavedJob, SkillGapAnalysis
        from config.ai_client import get_gemini_response, GeminiError
        title = request.POST.get('title', '')
        company = request.POST.get('company', '')
        location = request.POST.get('location', '')
        snippet = request.POST.get('snippet', '')
        link = request.POST.get('link', '')

        if not link:
            return redirect('job_recommendation')

        SavedJob.objects.get_or_create(
            user=request.user,
            link=link,
            defaults={
                'title': title,
                'company': company,
                'location': location,
                'snippet': snippet,
            }
        )
        from users.models import ActivityLog
        ActivityLog.objects.create(user=request.user, action='job_search', detail=f'Saved: {title}')

        # Auto gap analysis for saved job
        try:
            profile = request.user.userprofile
            if profile.skills and title:
                prompt = f"""Analyze the skill gap between the user's skills and the job "{title}" at {company or 'a company'}.

Current Skills: {profile.skills}

Return JSON: {{"current_skills": [], "missing_skills": [], "match_percentage": 0, "recommendations": ""}}
Only return valid JSON."""

                result = get_gemini_response(prompt, parse_json=True)
                SkillGapAnalysis.objects.create(
                    user=request.user,
                    target_role=title,
                    current_skills=result.get('current_skills', []),
                    missing_skills=result.get('missing_skills', []),
                    match_percentage=result.get('match_percentage', 0),
                    recommendations=result.get('recommendations', ''),
                )
        except (GeminiError, Exception):
            pass  # Non-critical — don't block the save

        return redirect('saved_jobs')
    return redirect('job_recommendation')


@login_required
def saved_jobs_view(request):
    """View all saved/bookmarked jobs."""
    from .models import SavedJob
    jobs = SavedJob.objects.filter(user=request.user)
    return render(request, 'recommendations/saved_jobs.html', {'jobs': jobs})


@login_required
def remove_saved_job(request, pk):
    """Remove a saved job."""
    from .models import SavedJob
    SavedJob.objects.filter(pk=pk, user=request.user).delete()
    return redirect('saved_jobs')


@login_required
def skill_gap_view(request):
    """AI-powered Skill Gap Analysis."""
    from .models import SkillGapAnalysis
    from users.models import ActivityLog

    analyses = SkillGapAnalysis.objects.filter(user=request.user)[:10]

    if request.method == 'POST':
        target_role = request.POST.get('target_role', '').strip()
        if not target_role:
            return render(request, 'recommendations/skill_gap.html', {
                'analyses': analyses,
                'error': 'Please enter a target role.'
            })

        try:
            profile = request.user.userprofile
        except Exception:
            return render(request, 'recommendations/skill_gap.html', {
                'analyses': analyses,
                'error': 'Please complete your profile first.'
            })

        current_skills = profile.skills or ''
        try:
            prompt = f"""You are a career advisor. Analyze the skill gap between the user's current skills and the requirements for the role of "{target_role}".

Current Skills: {current_skills}
Experience: {profile.experience}
Projects: {profile.projects}

Return a JSON object with these exact keys:
{{
  "current_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1", "skill2"],
  "match_percentage": 65,
  "recommendations": "A 2-3 sentence actionable recommendation for closing the gap."
}}

Only return valid JSON. No commentary. No markdown fences."""

            result = get_gemini_response(prompt, parse_json=True)

            analysis = SkillGapAnalysis.objects.create(
                user=request.user,
                target_role=target_role,
                current_skills=result.get('current_skills', []),
                missing_skills=result.get('missing_skills', []),
                match_percentage=result.get('match_percentage', 0),
                recommendations=result.get('recommendations', ''),
            )
            ActivityLog.objects.create(user=request.user, action='skills_extracted', detail=f'Gap: {target_role}')
            analyses = SkillGapAnalysis.objects.filter(user=request.user)[:10]
            return render(request, 'recommendations/skill_gap.html', {
                'analyses': analyses,
                'latest': analysis,
            })
        except Exception:
            return render(request, 'recommendations/skill_gap.html', {
                'analyses': analyses,
                'error': 'The AI service is temporarily unavailable. Please try again later.'
            })

    return render(request, 'recommendations/skill_gap.html', {'analyses': analyses})


@login_required
def toggle_roadmap_step(request, pk, step_index):
    """Toggle a roadmap step's completion and update skills."""
    from .models import Roadmap1
    from django.http import JsonResponse

    roadmap = Roadmap1.objects.filter(pk=pk, user=request.user).first()
    if not roadmap or not roadmap.steps:
        return JsonResponse({'error': 'Not found'}, status=404)

    steps = roadmap.steps
    if step_index < 0 or step_index >= len(steps):
        return JsonResponse({'error': 'Invalid step index'}, status=400)

    # Toggle completion
    steps[step_index]['completed'] = not steps[step_index].get('completed', False)
    roadmap.steps = steps
    roadmap.save()

    # If step was just completed, try to extract skill and add to profile
    if steps[step_index]['completed']:
        try:
            profile = request.user.userprofile
            step_text = steps[step_index].get('step', '')
            # Extract keywords from step text as skills
            existing = set(profile.extracted_skills or [])
            # Simple extraction: words that look like skills (capitalized, tech terms)
            words = [w.strip('.,;:()') for w in step_text.split() if len(w) > 2]
            # Don't try to be smart here — the step text itself is the skill context
            profile.save()
        except Exception:
            pass

    return JsonResponse({
        'success': True,
        'completed': steps[step_index]['completed'],
        'step_index': step_index,
    })