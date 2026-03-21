from django.urls import path
from .views import (
    start_interview, end_interview, get_results, interview_page,
    generate_report, interview_history,
)

urlpatterns = [
    path("start/",                          start_interview),
    path("end/",                            end_interview),
    path("results/<str:session_id>/",       get_results),
    path("report/<str:session_id>/",        generate_report),
    path("history/",                        interview_history),
    path("",                                interview_page),
]