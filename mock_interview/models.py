from django.db import models
from django.conf import settings


class InterviewSession(models.Model):
    DIFFICULTY_CHOICES = [
        ("easy",   "Easy"),
        ("medium", "Medium"),
        ("hard",   "Hard"),
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
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Full conversation — written by FastAPI callback on session end
    # Format: [{"role": "user"|"assistant", "content": "..."}]
    transcript  = models.JSONField(null=True, blank=True)

    # LLM-generated feedback — written by views.py after transcript arrives
    feedback    = models.TextField(null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} | {self.job_role} | {self.status}"
