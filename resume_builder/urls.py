from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.generate_resume, name='generate_resume'),
    path('view-resume/', views.view_resume, name='view'),
    path('resume-details/<int:pk>/', views.resume_details, name='view-resume'),
    path('edit-resume/<int:pk>/', views.edit_resume, name='edit_resume'),
    path('delete-resume/<int:pk>/', views.delete_resume, name='delete_resume'),
    path('download/<int:pk>/', views.download_resume_docx, name='download_resume'),
    path('download/', views.download_resume_docx, name='download_resume_latest'),
]
