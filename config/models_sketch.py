from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    is_student = models.BooleanField(default=True)
    # Add any role-based flags if needed later (admin/recruiter/etc.)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)

    skills = models.TextField(help_text="Comma-separated skills")
    education = models.TextField()
    experience = models.TextField()
    projects = models.TextField(blank=True)
    achievements = models.TextField(blank=True)
    resume_template_choice = models.IntegerField(default=1)

    def __str__(self):
        return self.full_name

class CompetencyTest(models.Model):
    job_role = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class TestResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    test = models.ForeignKey(CompetencyTest, on_delete=models.CASCADE)
    score = models.FloatField()
    feedback = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class JobRecommendation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    job_title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=100)
    url = models.URLField()
    match_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    
class LearningPath(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    target_job = models.CharField(max_length=100)
    recommended_courses = models.TextField()
    estimated_duration_weeks = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

