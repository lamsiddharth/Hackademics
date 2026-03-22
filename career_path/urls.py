from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.generate_career_path_view, name='generate_career_path'),
    path('', views.career_path_view, name='career_path_view'),
]
