from django.db import models
from users.models import User

class JobRole(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.title

class Skill(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class CareerPath(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    current_role = models.ForeignKey(JobRole, related_name='current_users', on_delete=models.SET_NULL, null=True, blank=True)
    target_role = models.ForeignKey(JobRole, related_name='target_users', on_delete=models.SET_NULL, null=True, blank=True)
    path = models.JSONField(default=dict)  # To store the graph structure
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Career path for {self.user.username}"

