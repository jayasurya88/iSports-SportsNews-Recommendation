from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Feedback

class UserUpdateForm(forms.ModelForm):
    # Explicitly defining email to make it required, but adding the widget with class
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'dob', 'profile_picture', 'email_notifications', 'sms_notifications']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['subject', 'message', 'rating']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'What is this about?'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Tell us your thoughts...'}),
            'rating': forms.HiddenInput(attrs={'id': 'rating-value', 'value': '5'}),
        }

from .models import CommunityGroup

class CommunityGroupForm(forms.ModelForm):
    league = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control', 
            'id': 'id_league_select'
        })
    )

    class Meta:
        model = CommunityGroup
        fields = ['name', 'description', 'league', 'team', 'is_public', 'require_approval']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Red Devils Manchester Fan Club'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'What is this group about?'}),
            'team': forms.Select(attrs={'class': 'form-control', 'id': 'id_team_select'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Team
        
        # Get distinct leagues for dropdown
        leagues = list(Team.objects.values_list('league', flat=True).distinct().order_by('league'))
        league_choices = [('', '-- Select a League --')] + [(lg, lg) for lg in leagues if lg]
        
        self.fields['league'].choices = league_choices
        self.fields['team'].empty_label = "-- Select an Associated Team --"
        self.fields['team'].required = False

        if 'league' in self.data:
            try:
                league = self.data.get('league')
                self.fields['team'].queryset = Team.objects.filter(league=league).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.league:
            self.fields['team'].queryset = Team.objects.filter(league=self.instance.league).order_by('name')
        else:
            self.fields['team'].queryset = Team.objects.none()
