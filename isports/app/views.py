from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Team, Match, Venue, UserProfile, NewsArticle, Feedback, Player, Poll, Alert
from .forms import UserUpdateForm, ProfileUpdateForm, FeedbackForm
from django.db.models import Q
import json
import time
import operator
from datetime import datetime
from functools import reduce
from django.core.cache import cache

# Helper check for roles
def is_admin(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'admin'

def is_organizer(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'organizer'

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
            
            # Check profile role
            from app.models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Reset role if user is superuser but profile isn't admin
            if user.is_superuser and profile.role != 'admin':
                profile.role = 'admin'
                profile.save()

            if profile.needs_password_change:
                messages.info(request, "Please change your initial password to continue.")
                return redirect('change_password_required')

            if profile.role == 'admin':
                return redirect('admin_dashboard')
            elif profile.role == 'organizer':
                return redirect('organizer_dashboard')
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
                dob=dob if dob else None,
                view_password=password
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
    from django.db.models import Sum
    total_users = User.objects.count()
    total_teams = Team.objects.count()
    total_matches = Match.objects.filter(status='scheduled').count()
    total_sales = Ticket.objects.count()
    total_revenue = Ticket.objects.aggregate(Sum('total_price'))['total_price__sum'] or 0
    recent_teams = Team.objects.all().order_by('-id')[:5]
    
    return render(request, 'admin_dashboard/dashboard.html', {
        'total_users': total_users,
        'total_teams': total_teams,
        'total_matches': total_matches,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'recent_teams': recent_teams
    })

@login_required
@user_passes_test(is_admin)
def admin_analytics(request):
    """
    Detailed analytics for system and revenue performance.
    """
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth
    
    # Revenue Trends (Monthly)
    revenue_data = Ticket.objects.annotate(month=TruncMonth('purchase_date'))\
                                 .values('month')\
                                 .annotate(total=Sum('total_price'))\
                                 .order_by('month')
    
    # Ticket Funnel (Example stats)
    funnel = {
        'page_views': 5240,
        'match_views': 2100,
        'checkout_starts': 850,
        'purchases': Ticket.objects.count()
    }
    
    # Popular Leagues
    leagues_data = Team.objects.values('league').annotate(count=Count('id')).order_by('-count')
    
    return render(request, 'admin_dashboard/analytics.html', {
        'revenue_data': revenue_data,
        'funnel': funnel,
        'leagues_data': leagues_data
    })

@login_required
@user_passes_test(is_admin)
def admin_news_list(request):
    articles = NewsArticle.objects.all().order_by('-published_at')
    return render(request, 'admin_dashboard/cms/news_list.html', {'articles': articles})

@login_required
@user_passes_test(is_admin)
def admin_news_create(request):
    if request.method == 'POST':
        headline = request.POST.get('headline')
        summary = request.POST.get('summary')
        content = request.POST.get('content')
        category = request.POST.get('category')
        image_url = request.POST.get('image_url')
        image_file = request.FILES.get('image_file')
        
        NewsArticle.objects.create(
            headline=headline,
            summary=summary,
            content=content,
            category=category,
            image_url=image_url,
            image_file=image_file,
            published_at=datetime.now()
        )
        messages.success(request, "Article published successfully!")
        return redirect('admin_news_list')
    return render(request, 'admin_dashboard/cms/news_form.html')

@login_required
@user_passes_test(is_admin)
def admin_news_edit(request, article_id):
    article = get_object_or_404(NewsArticle, id=article_id)
    if request.method == 'POST':
        article.headline = request.POST.get('headline')
        article.summary = request.POST.get('summary')
        article.content = request.POST.get('content')
        article.category = request.POST.get('category')
        article.image_url = request.POST.get('image_url')
        
        if request.FILES.get('image_file'):
            article.image_file = request.FILES.get('image_file')
            
        article.save()
        messages.success(request, "Article updated successfully!")
        return redirect('admin_news_list')
    return render(request, 'admin_dashboard/cms/news_form.html', {'article': article})

@login_required
@user_passes_test(is_admin)
def admin_news_delete(request, article_id):
    article = get_object_or_404(NewsArticle, id=article_id)
    article.delete()
    messages.success(request, "Article deleted.")
    return redirect('admin_news_list')

@login_required
@user_passes_test(is_admin)
def admin_feedback(request):
    feedback_list = Feedback.objects.all().order_by('-id')
    return render(request, 'admin_dashboard/feedback_admin.html', {'feedback_list': feedback_list})

@login_required
@user_passes_test(is_admin)
def admin_users(request):
    organizers = User.objects.filter(is_superuser=False, profile__role='organizer').order_by('-date_joined')
    regular_users = User.objects.filter(is_superuser=False, profile__role='user').order_by('-date_joined')
    return render(request, 'admin_dashboard/users_admin.html', {
        'organizers': organizers,
        'regular_users': regular_users
    })

@login_required
@user_passes_test(is_admin)
def admin_feedback_delete(request, feedback_id):
    feedback = get_object_or_404(Feedback, id=feedback_id)
    feedback.delete()
    messages.success(request, "Feedback entry removed.")
    return redirect('admin_feedback')

@login_required
@user_passes_test(is_admin)
def system_settings(request):
    """
    Displays API details and provides data management options.
    """
    api_info = {
        'base_url': 'https://site.api.espn.com/apis/site/v2/sports/soccer',
        'endpoints': [
            {'name': 'Teams List', 'url': '/[LEAGUE]/teams', 'purpose': 'Fetches all clubs, logos, and stadium info.'},
            {'name': 'Scoreboard', 'url': '/[LEAGUE]/scoreboard', 'purpose': 'Fetches fixtures, live scores, and match results.'},
            {'name': 'News Articles', 'url': '/[LEAGUE]/news', 'purpose': 'Fetches latest headlines and media content.'},
        ],
        'leagues': [
            'English Premier League (eng.1)',
            'Spanish La Liga (esp.1)',
            'German Bundesliga (ger.1)',
            'Italian Serie A (ita.1)',
            'French Ligue 1 (fra.1)',
            'Indian Super League (ind.1)'
        ],
        'stats': {
            'teams': Team.objects.count(),
            'matches': Match.objects.count(),
            'news': NewsArticle.objects.count(),
            'players': Player.objects.count()
        }
    }
    
    # Check if sync is in progress via cache
    is_syncing = cache.get('sports_sync_running', False)
    
    return render(request, 'admin_dashboard/settings.html', {
        'api_info': api_info,
        'is_syncing': is_syncing
    })

@login_required
@user_passes_test(is_admin)
def sync_sports_data(request):
    """
    Triggers the management command to fetch latest data.
    """
    from django.core.management import call_command
    import threading

    def d_sync():
        try:
            cache.set('sports_sync_running', True, 300) # Expire in 5 mins safety
            # We use quick=True for faster UI feedback in prototype
            call_command('seed_sports_data', quick=True)
        except Exception as e:
            print(f"Sync Error: {e}")
        finally:
            cache.delete('sports_sync_running')

    # Run in background to avoid blocking request
    thread = threading.Thread(target=d_sync)
    thread.start()
    
    messages.success(request, "Data synchronization started in the background. Latest sports data will be updated shortly.")
    return redirect('system_settings')

@login_required
@user_passes_test(is_admin)
def toggle_user_status(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user.is_superuser: # Prevent deactivating superusers easily
        user.is_active = not user.is_active
        user.save()
        messages.success(request, f"Status for {user.username} updated.")
    else:
        messages.error(request, "Cannot toggle status of a superuser.")
    return redirect('admin_users')

@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user.is_superuser:
        username = user.username
        user.delete()
        messages.success(request, f"User {username} deleted successfully.")
    else:
        messages.error(request, "Cannot delete a superuser.")
    return redirect('admin_users')

@login_required
@user_passes_test(is_admin)
def create_organizer(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        temp_pass = request.POST.get('password')
        full_name = request.POST.get('full_name')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect('admin_users')
        
        # Create User
        user = User.objects.create_user(username=username, email=email, password=temp_pass)
        if ' ' in full_name:
            user.first_name, user.last_name = full_name.split(' ', 1)
        else:
            user.first_name = full_name
        user.save()

        # Create Profile
        from app.models import UserProfile
        profile = UserProfile.objects.create(user=user, role='organizer', needs_password_change=True, view_password=temp_pass)
        
        messages.success(request, f"Organizer {username} created. They must change their password on first login.")
        return redirect('admin_users')
    return redirect('admin_users')

@login_required
@user_passes_test(is_organizer)
def organizer_dashboard(request):
    """
    Main dashboard for event organizers.
    """
    profile = request.user.profile
    if profile.needs_password_change:
        return redirect('change_password_required')

    organized_matches = Match.objects.filter(organizer=request.user)
    
    context = {
        'total_events': organized_matches.count(),
        'live_events': organized_matches.filter(status='live').count(),
        'upcoming_events': organized_matches.filter(status='scheduled').count(),
        'recent_events': organized_matches.order_by('-date_time')[:5],
        'total_revenue': organized_matches.filter(status='finished').count() * 1000, # Placeholder logic
    }
    return render(request, 'organizer_dashboard/dashboard.html', context)

@login_required
@user_passes_test(is_organizer)
def organizer_events_list(request):
    query = request.GET.get('q')
    matches = Match.objects.all()
    
    if query:
        matches = matches.filter(
            Q(home_team__name__icontains=query) | 
            Q(away_team__name__icontains=query) |
            Q(league__icontains=query)
        )
        
    matches = matches.order_by('-date_time')
    return render(request, 'organizer_dashboard/events/list.html', {'matches': matches, 'query': query})

@login_required
@user_passes_test(is_organizer)
def organizer_event_create(request):
    if request.method == 'POST':
        home_team_id = request.POST.get('home_team')
        away_team_id = request.POST.get('away_team')
        venue_id = request.POST.get('venue')
        date_time = request.POST.get('date_time')
        league = request.POST.get('league')
        
        if home_team_id == away_team_id:
            messages.error(request, "Home Team and Away Team cannot be the same.")
            teams = Team.objects.all().order_by('name')
            venues = Venue.objects.all().order_by('name')
            leagues = Team.objects.values_list('league', flat=True).distinct().order_by('league')
            return render(request, 'organizer_dashboard/events/form.html', {
                'teams': teams, 
                'venues': venues,
                'leagues': leagues
            })

        home_team = get_object_or_404(Team, id=home_team_id)
        away_team = get_object_or_404(Team, id=away_team_id)
        venue = get_object_or_404(Venue, id=venue_id)
        
        match = Match.objects.create(
            home_team=home_team,
            away_team=away_team,
            venue=venue,
            date_time=date_time,
            league=league,
            organizer=request.user
        )
        
        # Log alert for new creation
        Alert.objects.create(
            match=match,
            message=f"New match scheduled: {match.home_team.name} vs {match.away_team.name}",
            alert_type='modification'
        )
        messages.success(request, "Event scheduled successfully!")
        return redirect('organizer_events_list')
        
    teams = Team.objects.all().order_by('name')
    venues = Venue.objects.all().order_by('name')
    leagues = Team.objects.values_list('league', flat=True).distinct().order_by('league')
    
    return render(request, 'organizer_dashboard/events/form.html', {
        'teams': teams, 
        'venues': venues,
        'leagues': leagues
    })

@login_required
@user_passes_test(is_organizer)
def organizer_event_edit(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.method == 'POST':
        # Update basic info
        match.status = request.POST.get('status')
        match.league = request.POST.get('league')
        match.home_score = request.POST.get('home_score', 0)
        match.away_score = request.POST.get('away_score', 0)
        
        # Live Updates / Content
        match.lineups = request.POST.get('lineups')
        match.injury_news = request.POST.get('injury_news')
        match.pre_game_insights = request.POST.get('pre_game_insights')
        match.highlights_url = request.POST.get('highlights_url')
        
        if request.FILES.get('exclusive_media'):
            match.exclusive_media = request.FILES.get('exclusive_media')
            
        match.save()
        
        # Log alert if status changed or important update
        Alert.objects.create(
            match=match,
            message=f"Match details updated. Status: {match.status}",
            alert_type='live_update'
        )
        
        messages.success(request, "Event details updated.")
        return redirect('organizer_events_list')
        
    return render(request, 'organizer_dashboard/events/form.html', {'match': match})

@login_required
@user_passes_test(is_organizer)
def organizer_event_delete(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.method == 'POST':
        match.delete()
        messages.success(request, "Event deleted successfully.")
    return redirect('organizer_events_list')

@login_required
@user_passes_test(is_organizer)
def organizer_polls(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    if request.method == 'POST':
        question = request.POST.get('question')
        opt_a = request.POST.get('option_a')
        opt_b = request.POST.get('option_b')
        
        Poll.objects.create(
            match=match,
            question=question,
            option_a=opt_a,
            option_b=opt_b
        )
        messages.success(request, "Poll created!")
        return redirect('organizer_event_edit', match_id=match.id)
        
    polls = match.polls.all()
    return render(request, 'organizer_dashboard/events/polls.html', {'match': match, 'polls': polls})

@login_required
def change_password_required(request):
    if request.method == 'POST':
        new_pass = request.POST.get('new_password')
        confirm_pass = request.POST.get('confirm_password')
        
        if new_pass != confirm_pass:
            messages.error(request, "Passwords do not match.")
            return render(request, 'auth/change_password.html')
            
        request.user.set_password(new_pass)
        request.user.save()
        
        # Update session to keep user logged in
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, request.user)
        
        # Update profile
        profile = request.user.profile
        profile.needs_password_change = False
        profile.view_password = new_pass
        profile.save()
        
        messages.success(request, "Password updated successfully!")
        
        if profile.role == 'organizer':
            return redirect('organizer_dashboard')
        return redirect('index')
        
    return render(request, 'auth/change_password.html')


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

from .pdf_utils import generate_ticket_pdf

@login_required
def ticket_download_view(request, ticket_id):
    """
    View to download a specific ticket as PDF.
    """
    try:
        # Security check: Ensure ticket belongs to user
        ticket = Ticket.objects.get(ticket_id=ticket_id, user=request.user)
        return generate_ticket_pdf(request, ticket_id)
    except Ticket.DoesNotExist:
        messages.error(request, "Ticket not found or access denied.")
        return redirect('my_tickets')

@login_required
def my_tickets(request):
    tickets = Ticket.objects.filter(user=request.user).select_related('match', 'match__home_team', 'match__away_team', 'match__venue').order_by('-purchase_date')
    context = {
        'tickets': tickets
    }
    return render(request, 'my_tickets.html', context)

from django.db.models import Q
from functools import reduce
import operator

@login_required
def fav_team_news(request):
    """
    View to display news and players related to the user's favorite teams.
    """
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    favorite_teams = profile.favorite_teams.prefetch_related('players').all()
    
    news_articles = []
    
    if favorite_teams.exists():
        # Build a complex query to find news mentioning any of the favorite teams
        # We search in headline and summary
        query = reduce(operator.or_, [Q(headline__icontains=team.name) | Q(summary__icontains=team.name) for team in favorite_teams])
        
        news_articles = NewsArticle.objects.filter(query).order_by('-id')
    
    context = {
        'news_articles': news_articles,
        'favorite_teams': favorite_teams
    }
    return render(request, 'fav_team_news.html', context)

@login_required
def latest_news(request):
    """
    View to display all latest news articles.
    """
    news_articles = NewsArticle.objects.all().order_by('-published_at')
    
    context = {
        'news_articles': news_articles
    }
    context = {
        'news_articles': news_articles
    }
    return render(request, 'latest_news.html', context)

def feedback_view(request):
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            if request.user.is_authenticated:
                feedback.user = request.user
            feedback.save()
            messages.success(request, 'Your feedback has been sent to the admin!')
            return redirect('index')
    else:
        form = FeedbackForm()
    
    return render(request, 'feedback.html', {'form': form})