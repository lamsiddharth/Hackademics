import logging
from datetime import date

from django.core.cache import cache
from django.db.models import Avg

from config.ai_client import get_gemini_response, GeminiError

logger = logging.getLogger(__name__)


def calculate_career_score(user):
    """
    Calculate a 0-100 Career Score from four weighted components.

    Returns dict: {score, breakdown: {test_score, profile, skills, jobs}, percentile_label}
    """
    from competency.models import CompetencyTestSession
    from recommendations.models import SavedJob
    from users.models import UserProfile

    # 1. Test performance (30%) — avg completed test score scaled to 100
    avg = CompetencyTestSession.objects.filter(
        user=user, completed=True
    ).aggregate(avg=Avg('score'))['avg']
    test_score = min(round(avg, 1), 100) if avg else 0

    # 2. Profile completeness (20%)
    try:
        profile = user.userprofile
        profile_score = profile.completeness  # already 0-100
    except UserProfile.DoesNotExist:
        profile_score = 0

    # 3. Skill coverage (30%) — number of extracted skills, capped at 20 = 100%
    try:
        skills = user.userprofile.extracted_skills or []
        skills_score = min(len(skills) / 20 * 100, 100)
    except UserProfile.DoesNotExist:
        skills_score = 0

    # 4. Job engagement (20%) — saved jobs, capped at 10 = 100%
    saved = SavedJob.objects.filter(user=user).count()
    jobs_score = min(saved / 10 * 100, 100)

    # Weighted total
    score = round(
        test_score * 0.3 +
        profile_score * 0.2 +
        skills_score * 0.3 +
        jobs_score * 0.2
    )
    score = max(0, min(100, score))

    # Percentile label
    if score >= 80:
        percentile = "Top 10%"
    elif score >= 65:
        percentile = "Top 25%"
    elif score >= 50:
        percentile = "Top 40%"
    elif score >= 35:
        percentile = "Top 60%"
    else:
        percentile = "Getting started"

    return {
        'score': score,
        'breakdown': {
            'test_score': round(test_score),
            'profile': round(profile_score),
            'skills': round(skills_score),
            'jobs': round(jobs_score),
        },
        'percentile_label': percentile,
    }


def get_daily_ai_insight(user):
    """Generate and cache a daily AI insight for the user."""
    cache_key = f"daily_insight_{user.id}_{date.today().isoformat()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    career = calculate_career_score(user)
    breakdown = career['breakdown']

    # Find weakest area
    areas = [
        ('test performance', breakdown['test_score'], 'taking a competency assessment'),
        ('profile completeness', breakdown['profile'], 'completing your profile'),
        ('skill coverage', breakdown['skills'], 'extracting skills from your profile'),
        ('job engagement', breakdown['jobs'], 'searching and saving relevant jobs'),
    ]
    weakest = min(areas, key=lambda x: x[1])

    prompt = f"""You are a career coach AI. Generate ONE concise, actionable daily insight (2-3 sentences max) for a user with these stats:
- Career Score: {career['score']}/100
- Test Performance: {breakdown['test_score']}/100
- Profile Completeness: {breakdown['profile']}/100
- Skill Coverage: {breakdown['skills']}/100
- Job Engagement: {breakdown['jobs']}/100
- Weakest area: {weakest[0]} ({weakest[1]}/100)

Focus on their weakest area. Be specific and motivating. Don't use greeting or sign-off. Start directly with the insight."""

    try:
        insight = get_gemini_response(prompt)
        cache.set(cache_key, insight, 86400)  # 24 hours
        return insight
    except GeminiError:
        fallback = f"Your weakest area is {weakest[0]} at {weakest[1]}%. Try {weakest[2]} to boost your Career Score."
        cache.set(cache_key, fallback, 3600)  # 1 hour for fallback
        return fallback


def get_next_best_action(user):
    """Determine the single most impactful next step for the user."""
    from competency.models import CompetencyTestSession
    from resume_builder.models import resume
    from users.models import UserProfile

    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        return {
            'action': 'complete_profile',
            'label': 'Complete Your Profile',
            'url': '/profile/edit/',
            'icon': 'user',
            'description': 'Add your skills, education, and experience to get started.',
        }

    if profile.completeness < 60:
        return {
            'action': 'complete_profile',
            'label': 'Complete Your Profile',
            'url': '/profile/edit/',
            'icon': 'user',
            'description': f'Your profile is {profile.completeness}% complete. Fill in more details for better AI results.',
        }

    if not resume.objects.filter(user=user).exists():
        return {
            'action': 'generate_resume',
            'label': 'Generate Your Resume',
            'url': '/resume/generate/',
            'icon': 'file-text',
            'description': 'Create a professional AI-enhanced resume from your profile.',
        }

    if not CompetencyTestSession.objects.filter(user=user, completed=True).exists():
        return {
            'action': 'take_test',
            'label': 'Take a Competency Test',
            'url': '/competency/generate/',
            'icon': 'clipboard-check',
            'description': 'Assess your skills and get AI-powered feedback.',
        }

    if not profile.extracted_skills:
        return {
            'action': 'extract_skills',
            'label': 'Extract Your Skills',
            'url': '/recommendations/extract-skills/',
            'icon': 'zap',
            'description': 'Let AI identify and catalog your skills for better job matching.',
        }

    # Default: take another test to improve
    career = calculate_career_score(user)
    weakest = min(career['breakdown'].items(), key=lambda x: x[1])
    action_map = {
        'test_score': {'label': 'Take Another Assessment', 'url': '/competency/generate/', 'icon': 'clipboard-check', 'description': 'Practice more to improve your test scores.'},
        'profile': {'label': 'Update Your Profile', 'url': '/profile/edit/', 'icon': 'user', 'description': 'Add more details to strengthen your profile.'},
        'skills': {'label': 'Extract More Skills', 'url': '/recommendations/extract-skills/', 'icon': 'zap', 'description': 'Update your skill inventory for better matching.'},
        'jobs': {'label': 'Explore Job Opportunities', 'url': '/recommendations/job-recommendation/', 'icon': 'briefcase', 'description': 'Search and save jobs that match your profile.'},
    }
    best = action_map.get(weakest[0], action_map['test_score'])
    return {**best, 'action': weakest[0]}
