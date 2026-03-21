# recommendations/views.py
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.conf import settings
import requests
import json
import http.client
import google.generativeai as genai

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
    
import json
import google.generativeai as genai
from django.conf import settings

def parse_roadmap_with_gemini(roadmap_text: str):
    genai.configure(api_key=settings.GEMINI_API_KEY)

    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    # Prompt to extract checklist-style JSON from the roadmap
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
        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Try to parse as JSON
        steps = json.loads(raw_text)
        return steps

    except Exception as e:
        # Fallback with error handling
        return [{"step": f"Error parsing roadmap: {str(e)}", "completed": False}]
    
@login_required
def create_roadmap(request, job_title):
    latest_resume = resume.objects.filter(user=request.user).order_by('-created_at').first()

    if not latest_resume:
        return render(request, 'recommendations/roadmap.html', {
            'steps': [],
            'response': 'No resume found. Please generate a resume first.',
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
            friendly = f'An unexpected error occurred while generating your roadmap. Please try again later.'
        return render(request, 'recommendations/roadmap.html', {
            'steps': [],
            'response': '',
            'error': friendly
        })

    context = {
        'steps': steps,
        'response': response
    }

    return render(request, 'recommendations/roadmap.html', context)


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
    """Save/bookmark a job via AJAX POST."""
    if request.method == 'POST':
        from .models import SavedJob
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
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
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

            response = model.generate_content(prompt)
            raw_text = response.text.strip()
            if raw_text.startswith('```'):
                raw_text = raw_text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
            result = json.loads(raw_text)

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