from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    is_student = models.BooleanField(default=True)

class UserProfile(models.Model):
    
    TEMPLATE_CHOICES = [
        (1, 'Professional'),
        (2, 'Creative'),
        (3, 'Minimalistic'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    skills = models.TextField(help_text="Comma-separated skills")
    education = models.TextField()
    experience = models.TextField()
    projects = models.TextField(blank=True)
    achievements = models.TextField(blank=True)
    resume_template_choice = models.IntegerField(choices=TEMPLATE_CHOICES, default=1)
    extracted_skills = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.full_name

    @property
    def completeness(self):
        """Returns profile completeness as a percentage (0-100)."""
        fields = ['full_name', 'phone_number', 'location', 'skills',
                  'education', 'experience', 'projects', 'achievements']
        filled = sum(1 for f in fields if getattr(self, f, None))
        return int((filled / len(fields)) * 100)


class ActivityLog(models.Model):
    """Tracks user actions across the platform for analytics."""
    ACTION_CHOICES = [
        ('login', 'Logged In'),
        ('resume_generated', 'Resume Generated'),
        ('test_completed', 'Competency Test Completed'),
        ('roadmap_created', 'Roadmap Created'),
        ('skills_extracted', 'Skills Extracted'),
        ('job_search', 'Job Search Performed'),
        ('profile_updated', 'Profile Updated'),
        ('interview_prep', 'Interview Prep Started'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.get_action_display()}"
