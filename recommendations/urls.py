from django.urls import path
from .views import *

urlpatterns = [
     path('extract-skills/', extract_skills_view, name='extract_skills'),
     path('match-live-jobs/', live_job_match_view, name='match_live_jobs'),
     path('roadmap/<str:job_title>/', create_roadmap, name='create_roadmap'),
     path('targetjob/', target_job_view, name='target_job'),
     path('job-recommendation/', job_recommendation_view, name='job_recommendation'),
     path('save-job/', save_job_view, name='save_job'),
     path('saved-jobs/', saved_jobs_view, name='saved_jobs'),
     path('saved-jobs/remove/<int:pk>/', remove_saved_job, name='remove_saved_job'),
     path('skill-gap/', skill_gap_view, name='skill_gap'),
]

