from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from django.contrib.auth.decorators import login_required
from .models import UserProfile, ActivityLog
from .forms import UserProfileForm
from competency.models import CompetencyTestSession, Answer
from recommendations.models import SavedJob, SkillGapAnalysis
from resume_builder.models import resume
from django.db.models import Avg, Count, Case, When, FloatField
from django.db.models.functions import Cast


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(request,
                                username=form.cleaned_data['username'],
                                password=form.cleaned_data['password'])
            if user:
                login(request, user)
                ActivityLog.objects.create(user=user, action='login')
                return redirect('dashboard')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('landing')


def landing_view(request):
    """Public landing page — redirects authenticated users to dashboard."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'users/landing.html')


@login_required
def dashboard_view(request):
    """Enhanced dashboard with live stats and recent activity."""
    profile = None
    profile_completeness = 0
    try:
        profile = request.user.userprofile
        profile_completeness = profile.completeness
    except UserProfile.DoesNotExist:
        return redirect('edit_profile')

    # Stats
    resume_count = resume.objects.filter(user=request.user).count()
    test_count = CompetencyTestSession.objects.filter(user=request.user, completed=True).count()
    saved_jobs_count = SavedJob.objects.filter(user=request.user).count()

    # Average test score
    avg_score = CompetencyTestSession.objects.filter(
        user=request.user, completed=True
    ).aggregate(avg=Avg('score'))['avg']
    avg_score = round(avg_score, 1) if avg_score else 0

    # Recent activity
    recent_activity = ActivityLog.objects.filter(user=request.user)[:5]

    # Skills count
    skills_count = 0
    if profile and profile.extracted_skills:
        skills_count = len(profile.extracted_skills)

    context = {
        'profile': profile,
        'profile_completeness': profile_completeness,
        'resume_count': resume_count,
        'test_count': test_count,
        'saved_jobs_count': saved_jobs_count,
        'avg_score': avg_score,
        'recent_activity': recent_activity,
        'skills_count': skills_count,
    }
    return render(request, 'users/dashboard.html', context)


@login_required
def create_or_edit_profile(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        profile = None

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            user_profile = form.save(commit=False)
            user_profile.user = request.user
            user_profile.save()
            ActivityLog.objects.create(user=request.user, action='profile_updated')
            return redirect('view_profile')
    else:
        form = UserProfileForm(instance=profile)

    return render(request, 'users/edit_profile.html', {'form': form})


@login_required
def view_profile(request):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        return redirect('edit_profile')

    return render(request, 'users/view_profile.html', {'profile': profile})


@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            return redirect('view_profile')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'users/change_password.html', {'form': form})


@login_required
def activity_log_view(request):
    activities = ActivityLog.objects.filter(user=request.user)[:50]
    return render(request, 'users/activity_log.html', {'activities': activities})
