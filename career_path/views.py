from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from users.models import UserProfile
from .models import CareerPath
from .utils import generate_career_graph
import json

@login_required
def generate_career_path_view(request):
    user_profile = UserProfile.objects.get(user=request.user)
    
    career_graph_json = generate_career_graph(user_profile)
    
    if career_graph_json:
        career_graph = json.loads(career_graph_json)
        
        career_path, created = CareerPath.objects.update_or_create(
            user=request.user,
            defaults={'path': career_graph}
        )
        return redirect('career_path_view')
        
    return render(request, 'career_path/error.html', {'message': 'Could not generate career path.'})

@login_required
def career_path_view(request):
    try:
        career_path = CareerPath.objects.get(user=request.user)
        return render(request, 'career_path/view_career_path.html', {'career_path': career_path})
    except CareerPath.DoesNotExist:
        return render(request, 'career_path/no_career_path.html')

