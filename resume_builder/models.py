from django.db import models
from users.models import User


class resume(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    location = models.CharField(max_length=255, blank=True)

    summary = models.TextField(blank=True)
    achievements = models.TextField(blank=True)
    projects = models.TextField(blank=True)
    skills = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    education = models.TextField(blank=True)
    template_used = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} — Resume #{self.pk}"

    class Meta:
        ordering = ['-created_at']