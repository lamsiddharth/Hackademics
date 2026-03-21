from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User
from .models import UserProfile
from django import forms

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'full_name',
            'phone_number',
            'location',
            'skills',
            'education',
            'experience',
            'projects',
            'achievements',
            'resume_template_choice'
        ]
        widgets = {
            'skills': forms.Textarea(attrs={'rows': 2}),
            'education': forms.Textarea(attrs={'rows': 2}),
            'experience': forms.Textarea(attrs={'rows': 2}),
            'projects': forms.Textarea(attrs={'rows': 2}),
            'achievements': forms.Textarea(attrs={'rows': 2}),
        }
        def __init__(self, *args, **kwargs):
            super(UserProfileForm, self).__init__(*args, **kwargs)
            for field_name, field in self.fields.items():
                # Apply consistent Tailwind classes to all input/textarea/select fields
                existing_classes = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = (
                    existing_classes +
                    ' w-full px-4 py-2 border border-gray-300 rounded-md '
                    'focus:outline-none focus:ring-2 focus:ring-blue-500'
                )
                field.widget.attrs.update({
                    'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
                })

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='Username')
    password = forms.CharField(label='Password', widget=forms.PasswordInput)
