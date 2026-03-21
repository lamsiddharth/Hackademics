from django.urls import path
from . import views


urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/edit/', views.create_or_edit_profile, name='edit_profile'),
    path('profile/', views.view_profile, name='view_profile'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
    path('activity/', views.activity_log_view, name='activity_log'),
]
