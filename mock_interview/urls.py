from django.urls import path
from .views import start_interview, end_interview, get_results,interview_page

urlpatterns = [
    path("start/",                   start_interview),
    path("end/",                     end_interview),
    path("results/<str:session_id>/", get_results),
    path('', interview_page)
]