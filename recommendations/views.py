# recommendations/views.py
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.conf import settings
from urllib.parse import unquote_plus
from django.urls import reverse
import requests
import json
import http.client
import google.generativeai as genai

from recommendations.ollama_utils import match_live_jobs
from users.models import UserProfile
from resume_builder.models import resume
from .utils import generate_learning_roadmap, extract_skills_from_profile, fetch_jobs, fetch_jobs_remotive


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

    # Use fixed job title 'data-scientist'
    query = "data-scientist"
    api_url = f"https://remotive.com/api/remote-jobs?search={query}"

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(api_url, headers=headers)
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
    prompt = f"You are a helpful assistant.\n\nTake the following roadmap text and convert it into structured JSON. Each step should be a short sentence or phrase with a `step` and a `completed` flag (default to false).\n\nRoadmap:\n\"\"\"\n{roadmap_text}\n\"\"\"\n\nOutput format:\n[\n  {{\n    \"step\": \"First task\",\n    \"completed\": false\n  }}\n]\n\nOnly return valid JSON. No commentary. No markdown or code fences. Just the JSON array."
    try:
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        if raw_text.startswith('```json'): raw_text = raw_text[7:]
        if raw_text.startswith('```'): raw_text = raw_text[3:]
        if raw_text.endswith('```'): raw_text = raw_text[:-3]
        return json.loads(raw_text.strip())
    except Exception as e:
        return [{"step": f"Error parsing roadmap: {str(e)}", "completed": False}]


def _normalize_roadmap_title(title: str) -> str:
    if not title:
        return ''
    return unquote_plus(title).strip()


@login_required
def delete_roadmap(request, pk):
    from .models import Roadmap1
    if request.method != 'POST':
        return redirect('target_job')
    Roadmap1.objects.filter(user=request.user, pk=pk).delete()
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('target_job')
    return redirect(next_url)

@login_required
def create_roadmap(request, job_title=None, pk=None):
    from .models import Roadmap1
    from django.utils.safestring import mark_safe
    import re
    
    recent_roadmaps = Roadmap1.objects.filter(user=request.user).order_by('-created_at')[:8]
    
    roadmap_obj = None
    normalized_title = _normalize_roadmap_title(job_title) if job_title else ''
    if pk:
        roadmap_obj = Roadmap1.objects.filter(user=request.user, pk=pk).first()
        if roadmap_obj:
            decoded_title = _normalize_roadmap_title(roadmap_obj.title)
            if decoded_title and decoded_title != roadmap_obj.title:
                roadmap_obj.title = decoded_title
                roadmap_obj.save(update_fields=['title'])
            normalized_title = roadmap_obj.title
    if not roadmap_obj and normalized_title:
        roadmap_obj = Roadmap1.objects.filter(user=request.user, title__iexact=normalized_title).order_by('-created_at').first()

    if request.method == 'POST':
        if not roadmap_obj:
            return redirect('target_job')
            
        from competency.utils import extract_skills_from_text
        try: profile = request.user.userprofile
        except Exception: profile = None
            
        steps = roadmap_obj.steps
        for i, step in enumerate(steps, 1):
            checkbox_name = f'step_{i}'
            was_completed = step.get('completed', False)
            is_completed = request.POST.get(checkbox_name) == 'on'
            
            if not was_completed and is_completed:
                step['completed'] = True
                if profile:
                    extracted_skills = extract_skills_from_text(step['step'])
                    current_skills = [s.strip() for s in profile.skills.split(',') if s.strip()] if profile.skills else []
                    for skill in extracted_skills:
                        if skill.lower() not in [s.lower() for s in current_skills]:
                            current_skills.append(skill)
                        if isinstance(profile.extracted_skills, list):
                            if skill.lower() not in [s.lower() for s in profile.extracted_skills]:
                                profile.extracted_skills.append(skill)
                    profile.skills = ', '.join(current_skills)
                    profile.save()
            elif was_completed and not is_completed:
                step['completed'] = False
                
        roadmap_obj.steps = steps
        roadmap_obj.save()
        if pk:
            return redirect('create_roadmap_by_id', pk=pk)
        return redirect('create_roadmap', job_title=normalized_title)

    if not roadmap_obj:
        latest_resume = resume.objects.filter(user=request.user).order_by('-created_at').first()
        if not latest_resume:
            return render(request, 'recommendations/roadmap.html', {
                'steps': [],
                'response': 'No resume found. Please generate a resume first.',
                'error': 'No resume found.',
                'roadmaps': recent_roadmaps,
                'current_title': job_title,
            })

        skills = latest_resume.skills
        projects = latest_resume.projects
        experience = latest_resume.experience

        try:
            from .utils import generate_learning_roadmap
            response = generate_learning_roadmap(skills, projects, experience, normalized_title)
            steps = parse_roadmap_with_gemini(response)
            roadmap_obj = Roadmap1.objects.create(user=request.user, title=normalized_title, raw_response=response, steps=steps)
        except Exception as e:
            return render(request, 'recommendations/roadmap.html', {
                'steps': [],
                'response': '',
                'error': f'An unexpected error occurred: {str(e)}',
                'roadmaps': recent_roadmaps,
                'current_title': job_title,
            })

    def md2html(text):
        text = str(text).replace('\n', '<br>')
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'#+ (.*)', r'<h3>\1</h3><br>', text)
        return text
        
    return render(request, 'recommendations/roadmap.html', {
        'steps': roadmap_obj.steps,
        'response': mark_safe(md2html(roadmap_obj.raw_response)),
        'roadmaps': recent_roadmaps,
        'current_title': normalized_title,
    })


@login_required
def target_job_view(request):
    from .models import Roadmap1
    recent_roadmaps = Roadmap1.objects.filter(user=request.user).order_by('-created_at')[:8]
    for rm in recent_roadmaps:
        rm.display_title = _normalize_roadmap_title(rm.title) or rm.title
    return render(request, 'recommendations/targetjob.html', {'roadmaps': recent_roadmaps})
    
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

    # hardcoded 'data-scientist' as per the request
    keywords = "technology, data analysis, machine learning, programming"  # This could be improved by using actual skills from the profile
    jobs = []

    try:
        if settings.JOOBLE_API_KEY:
            jobs = fetch_jobs(keywords, location)
        if not jobs:
            jobs = fetch_jobs_remotive(keywords, limit=10)
    except Exception:
        return render(request, 'recommendations/topjobs.html', {
            'jobs': [],
            'error': 'Job services are temporarily unavailable. Please try again later.'
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