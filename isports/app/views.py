from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Team, Match, Venue, UserProfile, NewsArticle
from .forms import UserUpdateForm, ProfileUpdateForm
from django.db.models import Q
import urllib.request
import json
import time

# Helper check for superuser
def is_admin(user):
    return user.is_superuser

# Create your views here.
def index(request):
    return render(request, 'index.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            
            if user.is_superuser:
                return redirect('admin_dashboard')
            else:
                return redirect('user_dashboard')
        else:
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'login.html')

def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        dob = request.POST.get('dob')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, 'register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return render(request, 'register.html')

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            UserProfile.objects.create(
                user=user,
                phone=phone,
                dob=dob if dob else None
            )

            login(request, user)
            messages.success(request, "Registration successful! Welcome to iSports.")
            return redirect('user_dashboard')

        except Exception as e:
            messages.error(request, f"An error occurred during registration: {e}")
            return render(request, 'register.html')

    return render(request, 'register.html')

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    total_users = User.objects.count()
    total_teams = Team.objects.count()
    total_matches = Match.objects.count()
    total_sales = 0
    
    recent_teams = Team.objects.all().order_by('-id')[:5]
    
    context = {
        'total_users': total_users,
        'total_teams': total_teams,
        'total_matches': total_matches,
        'total_sales': total_sales,
        'recent_teams': recent_teams
    }
    return render(request, 'admin_dashboard/dashboard.html', context)


# ============================================================
# PREFERENCE ENGINE — Recommendation Algorithm
# ============================================================

@login_required
def user_dashboard(request):
    """
    Dashboard with a 4-tier Recommendation Algorithm:
      1. Primary:   Matches involving the user's favorite teams
      2. League:    Other matches in the same leagues they follow
      3. Discovery: Matches from sports they DON'T follow
      4. Fallback:  Trending upcoming matches (no favorites set)
    """
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    favorite_teams = profile.favorite_teams.all()
    
    recommended_matches = []
    suggested_events = []
    
    if favorite_teams.exists():
        # --- Tier 1: Matches involving favorite teams ---
        recommended_matches = list(
            Match.objects.filter(
                Q(home_team__in=favorite_teams) | Q(away_team__in=favorite_teams),
                status='scheduled'
            ).select_related('home_team', 'away_team', 'venue').order_by('date_time')[:5]
        )
        
        # --- Tier 2: Other matches in followed leagues ---
        fav_leagues = list(favorite_teams.values_list('league', flat=True).distinct())
        already_shown_ids = [m.id for m in recommended_matches]
        
        if fav_leagues:
            league_matches = list(
                Match.objects.filter(
                    league__in=fav_leagues,
                    status='scheduled'
                ).exclude(
                    id__in=already_shown_ids
                ).select_related('home_team', 'away_team', 'venue').order_by('date_time')[:3]
            )
            for m in league_matches:
                m.is_league_recommendation = True
            recommended_matches.extend(league_matches)
                
        # --- Tier 3: Cross-sport discovery ---
        followed_sports = list(favorite_teams.values_list('sport', flat=True).distinct())
        suggested_events = list(
            Match.objects.exclude(
                home_team__sport__in=followed_sports
            ).filter(
                status='scheduled'
            ).select_related('home_team', 'away_team', 'venue').order_by('?')[:2]
        )
    else:
        # --- Tier 4: Trending fallback for new users ---
        recommended_matches = list(
            Match.objects.filter(
                status='scheduled'
            ).select_related('home_team', 'away_team', 'venue').order_by('date_time')[:6]
        )
        for m in recommended_matches:
            m.is_trending = True

    # Compute followed leagues count for sidebar
    followed_leagues_count = favorite_teams.values_list('league', flat=True).distinct().count() if favorite_teams.exists() else 0

    # Fetch news from DB
    news_articles = NewsArticle.objects.all()[:4]

    context = {
        'favorite_teams': favorite_teams,
        'recommended_matches': recommended_matches,
        'suggested_events': suggested_events,
        'has_favorites': favorite_teams.exists(),
        'followed_leagues_count': followed_leagues_count,
        'news_articles': news_articles,
    }
    return render(request, 'user_dashboard.html', context)


@login_required
def events_list(request):
    """View to list all upcoming sports events/matches."""
    query = request.GET.get('q', '')
    league_filter = request.GET.get('league', '')
    
    matches = Match.objects.all().select_related('home_team', 'away_team', 'venue')
    
    if query:
        matches = matches.filter(
            Q(home_team__name__icontains=query) | 
            Q(away_team__name__icontains=query) |
            Q(league__icontains=query)
        )
    
    if league_filter:
        matches = matches.filter(league=league_filter)
        
    matches = matches.order_by('date_time')
    
    leagues = Match.objects.values_list('league', flat=True).distinct().order_by('league')
    
    context = {
        'matches': matches,
        'leagues': leagues,
        'selected_league': league_filter,
        'query': query,
    }
    return render(request, 'events_list.html', context)


@login_required
def match_detail(request, match_id):
    """View details for a specific match/event."""
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team', 'venue'), id=match_id)
    
    # Get recent matches for these teams for 'form' or 'history'
    home_recent = Match.objects.filter(
        Q(home_team=match.home_team) | Q(away_team=match.home_team),
        status='finished',
        date_time__lt=match.date_time
    ).order_by('-date_time')[:5]
    
    away_recent = Match.objects.filter(
        Q(home_team=match.away_team) | Q(away_team=match.away_team),
        status='finished',
        date_time__lt=match.date_time
    ).order_by('-date_time')[:5]

    context = {
        'match': match,
        'home_recent': home_recent,
        'away_recent': away_recent,
        'is_live': match.status == 'live',
    }
    return render(request, 'match_detail.html', context)


@login_required
def news_detail(request, news_id):
    """View details for a specific news article."""
    article = get_object_or_404(NewsArticle, id=news_id)
    recent_news = NewsArticle.objects.exclude(id=news_id)[:3]
    
    context = {
        'article': article,
        'recent_news': recent_news,
    }
    return render(request, 'news_detail.html', context)


# ============================================================
# PROFILE VIEWS
# ============================================================

@login_required
def profile_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    favorite_teams = profile.favorite_teams.all().order_by('sport', 'league', 'name')
    favorites_by_league = {}
    for team in favorite_teams:
        league = team.league if team.league else "Other"
        if league not in favorites_by_league:
            favorites_by_league[league] = []
        favorites_by_league[league].append(team)

    context = {
        'favorites_by_league': favorites_by_league
    }
    return render(request, 'profile.html', context)

@login_required
def profile_edit(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('profile_view')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    return render(request, 'profile_edit.html', context)


# ============================================================
# MANAGE FAVORITES — Select Favorite Teams/Leagues
# ============================================================

@login_required
def manage_favorites(request):
    """
    Sport → League → Team selection flow.
    POST uses add/remove logic so saving one league doesn't wipe
    favorites from other leagues.
    """
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        selected_team_ids = set(map(int, request.POST.getlist('teams')))
        current_sport = request.POST.get('current_sport', '')
        current_league = request.POST.get('current_league', '')
        
        # Get all team IDs belonging to the league on screen
        visible_team_ids = set(
            Team.objects.filter(sport=current_sport, league=current_league).values_list('id', flat=True)
        )
        
        # Teams to add: checked AND visible on screen
        teams_to_add = selected_team_ids & visible_team_ids
        # Teams to remove: unchecked but visible on screen (user deliberately unselected)
        teams_to_remove = visible_team_ids - selected_team_ids
        
        # Apply changes without affecting other leagues
        if teams_to_add:
            profile.favorite_teams.add(*teams_to_add)
        if teams_to_remove:
            profile.favorite_teams.remove(*teams_to_remove)
        
        messages.success(request, 'Your favorite teams have been updated!')
        return redirect(f'/profile/favorites/?sport={current_sport}&league={current_league}')
        
    # GET: Build the Sport → League → Team selection
    all_sports = Team.objects.values_list('sport', flat=True).distinct().order_by('sport')
    
    selected_sport = request.GET.get('sport')
    if not selected_sport:
        selected_sport = 'Football' if Team.objects.filter(sport='Football').exists() else (all_sports[0] if all_sports.exists() else None)

    leagues = Team.objects.filter(sport=selected_sport).values_list('league', flat=True).distinct().order_by('league')
    
    selected_league = request.GET.get('league')
    if not selected_league and leagues.exists():
        selected_league = leagues[0]

    teams = Team.objects.filter(sport=selected_sport, league=selected_league).order_by('name')
    
    # Get ALL favorite team IDs (across all sports) for proper checkbox display
    favorite_team_ids = list(profile.favorite_teams.values_list('id', flat=True))
    
    # Count how many favorites exist across all sports (for summary badge)
    total_favorites = profile.favorite_teams.count()

    context = {
        'all_sports': all_sports,
        'selected_sport': selected_sport,
        'leagues': leagues,
        'selected_league': selected_league,
        'teams': teams,
        'favorite_team_ids': favorite_team_ids,
        'total_favorites': total_favorites,
    }
    return render(request, 'manage_favorites.html', context)


@login_required
def payment_mock_view(request, match_id):
    """View to display mock payment page for a match."""
    match = get_object_or_404(Match, id=match_id)
    context = {
        'match': match,
    }
    return render(request, 'payment_mock.html', context)

import uuid
from .models import Ticket

@login_required
def process_payment(request, match_id):
    if request.method == 'POST':
        match = get_object_or_404(Match, id=match_id)
        
        # Generate a unique ticket ID
        ticket_code = uuid.uuid4().hex[:12].upper()
        
        Ticket.objects.create(
            user=request.user,
            match=match,
            total_price=52.50, # Hardcoded for mock
            ticket_id=ticket_code,
            seat_section='Standard',
            status='active'
        )
        
        messages.success(request, 'Ticket purchased successfully!')
        return redirect('my_tickets')
    return redirect('user_dashboard')

@login_required
def my_tickets(request):
    tickets = Ticket.objects.filter(user=request.user).select_related('match', 'match__home_team', 'match__away_team', 'match__venue').order_by('-purchase_date')
    context = {
        'tickets': tickets
    }
    return render(request, 'my_tickets.html', context)