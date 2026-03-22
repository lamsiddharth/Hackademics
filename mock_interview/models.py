from django.db import models
from django.conf import settings


class InterviewSession(models.Model):
    DIFFICULTY_CHOICES = [
        ("easy",   "Easy"),
        ("medium", "Medium"),
        ("hard",   "Hard"),
    ]
    PREP_MODE_CHOICES = [
        ("subjective", "Subjective"),
        ("interactive", "Interactive"),
    ]
    STATUS_CHOICES = [
        ("pending",   "Pending"),     # created, not started
        ("active",    "Active"),      # WS open
        ("completed", "Completed"),   # transcript received from FastAPI
        ("failed",    "Failed"),
    ]

    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interview_sessions")
    job_role    = models.CharField(max_length=200)
    difficulty  = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default="medium")
    prep_mode   = models.CharField(max_length=20, choices=PREP_MODE_CHOICES, default="subjective")
    target_role = models.CharField(max_length=200, null=True, blank=True)
    target_company = models.CharField(max_length=200, null=True, blank=True)
    tech_stack  = models.CharField(max_length=300, null=True, blank=True)
    current_profile = models.TextField(null=True, blank=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Full conversation — written by FastAPI callback on session end
    # Format: [{"role": "user"|"assistant", "content": "..."}]
    transcript  = models.JSONField(null=True, blank=True)

    # LLM-generated feedback — written by views.py after transcript arrives
    feedback    = models.TextField(null=True, blank=True)

    # Client-side MediaPipe body language metrics (eye contact, expressions, head pose)
    body_language_metrics = models.JSONField(null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} | {self.job_role} | {self.status}"
