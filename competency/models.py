from django.db import models
from users.models import User

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
    
class Question(models.Model):
    job_role = models.CharField(max_length=100)
    text = models.TextField()
    difficulty = models.CharField(max_length=20, choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')])
    correct_answer = models.TextField(blank=True, null=True)  # Optional if MCQs
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.job_role} - {self.text[:50]}"


class CompetencyTestSession(models.Model):
    SENIORITY_CHOICES = [
        ('junior', 'Junior'),
        ('mid', 'Mid-Level'),
        ('senior', 'Senior'),
        ('staff', 'Staff/Lead'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    job_role = models.CharField(max_length=100)
    seniority = models.CharField(max_length=20, choices=SENIORITY_CHOICES, default='mid')
    company_type = models.CharField(max_length=100, blank=True)
    score = models.FloatField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.job_role} Test"

class Answer(models.Model):
    session = models.ForeignKey(CompetencyTestSession, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    score = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    gaps = models.JSONField(default=list, blank=True)
    skill_tags = models.JSONField(default=list, blank=True)
    model_answer = models.TextField(blank=True)
    answered_at = models.DateTimeField(auto_now_add=True)


class InterviewSession(models.Model):
    """A timed interview simulation session."""
    MODE_CHOICES = [
        ('practice', 'Practice'),
        ('simulator', 'Simulator'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interview_sessions')
    job_role = models.CharField(max_length=100)
    category = models.CharField(max_length=20, default='technical')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='practice')
    overall_score = models.FloatField(null=True, blank=True)
    hire_decision = models.CharField(max_length=20, blank=True)
    confidence_scores = models.JSONField(default=list, blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.job_role} Interview ({self.mode})"


class InterviewQuestion(models.Model):
    """AI-generated interview prep questions with model answers."""
    CATEGORY_CHOICES = [
        ('behavioral', 'Behavioral'),
        ('technical', 'Technical'),
        ('situational', 'Situational'),
        ('system_design', 'System Design'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interview_questions')
    session = models.ForeignKey(InterviewSession, null=True, blank=True, on_delete=models.SET_NULL, related_name='questions')
    job_role = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    question_text = models.TextField()
    model_answer = models.TextField(blank=True)
    user_answer = models.TextField(blank=True)
    feedback = models.TextField(blank=True)
    score = models.FloatField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    time_taken = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.job_role} — {self.question_text[:50]}"
