from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.generate_test_questions, name='generate_test'),
    path('questions/<str:job_role>/', views.view_questions, name='view_questions'),
    path('test/start/<str:job_role>/', views.start_test, name='start_test'),
    path('test/<int:session_id>/question/<int:question_id>/', views.question_view, name='question'),
    path('test/<int:session_id>/result/', views.test_result, name='test_result'),
    path('test/history/', views.history_test, name='history_test'),
    path('test/historygraph/', views.history_graph, name='history_graph'),
    # Interview Prep
    path('interview-prep/', views.interview_prep_view, name='interview_prep'),
    path('interview-prep/<int:pk>/practice/', views.interview_practice_view, name='interview_practice'),
    path('interview-prep/clear/', views.clear_interview_questions, name='clear_interview_questions'),
]
