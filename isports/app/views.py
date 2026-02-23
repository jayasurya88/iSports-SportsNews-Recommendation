from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Team, Match, Venue, UserProfile, NewsArticle, Feedback, Player, Poll, PollVote, Alert, CommunityGroup, CommunityMessage, Ticket
from .forms import UserUpdateForm, ProfileUpdateForm, FeedbackForm, CommunityGroupForm
from django.db.models import Q, Sum
import json
import time
import operator
import urllib.request
from datetime import datetime, timedelta
from django.utils import timezone
from functools import reduce
from django.core.cache import cache

# Helper check for roles
def is_admin(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'admin'

def is_organizer(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'organizer'

# Helper for News Syncing
def sync_news_for_leagues(leagues_list):
    """
    Optional live sync for news articles from ESPN public API.
    leagues_list: list of league names or slugs
    """
    # Map common league names to ESPN slugs
    LEAGUE_MAP = {
        'English Premier League': 'eng.1',
        'Spanish La Liga': 'esp.1',
        'German Bundesliga': 'ger.1',
        'Italian Serie A': 'ita.1',
        'French Ligue 1': 'fra.1',
        'Indian Super League': 'ind.1'
    }
    
    headers = {'User-Agent': 'iSports/1.0'}
    
    for league_name in leagues_list:
        slug = LEAGUE_MAP.get(league_name)
        if not slug: continue
        
        # Don't sync more than once an hour per league
        cache_key = f'news_sync_{slug}'
        if cache.get(cache_key): continue
        
        try:
            url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/news'
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                articles = data.get('articles', [])
                for art in articles:
                    headline = art.get('headline', '')
                    if not headline: continue
                    
                    published_str = art.get('published', '')
                    published_dt = None
                    if published_str:
                        from django.utils.dateparse import parse_datetime
                        published_dt = parse_datetime(published_str)

                    NewsArticle.objects.update_or_create(
                        headline=headline[:500],
                        defaults={
                            'summary': art.get('description', ''),
                            'content': art.get('story', ''),
                            'image_url': art.get('images', [{}])[0].get('url', '') if art.get('images') else '',
                            'source_url': art.get('links', {}).get('web', {}).get('href', ''),
                            'published_at': published_dt,
                            'category': league_name
                        }
                    )
            # Set cache to avoid spamming API
            cache.set(cache_key, True, 3600)
        except Exception as e:
            print(f"Error syncing news: {e}")

# Create your views here.
from django.db.models import Case, When, Value, IntegerField

def index(request):
    upcoming_matches = Match.objects.filter(
        Q(status='live') | Q(status='scheduled', date_time__gte=timezone.now())
    ).annotate(
        status_priority=Case(
            When(status='live', then=Value(1)),
            When(status='scheduled', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('status_priority', 'date_time')[:6]
    context = {
        'upcoming_matches': upcoming_matches,
    }
    return render(request, 'index.html', context)

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            
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
                if not profile.onboarding_completed:
                    return redirect('user_onboarding')
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
            
        if phone and (not phone.isdigit() or len(phone) != 10):
            messages.error(request, "Phone number must be exactly 10 digits.")
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
            return redirect('user_onboarding')

        except Exception as e:
            messages.error(request, f"An error occurred during registration: {e}")
            return render(request, 'register.html')

    return render(request, 'register.html')

@login_required
def user_onboarding(request):
    profile = request.user.profile
    
    if profile.onboarding_completed:
        return redirect('user_dashboard')
        
    if request.method == 'POST':
        selected_sports = request.POST.getlist('sports')
        selected_teams = request.POST.getlist('favorite_teams')
        
        profile.interests = ",".join(selected_sports)
        profile.onboarding_completed = True
        profile.save()
        
        # Add favorite teams
        profile.favorite_teams.set(selected_teams)
        
        messages.success(request, "Setup complete! Enjoy your personalized experience.")
        return redirect('user_dashboard')
        
    # GET: Fetch sports, leagues, and teams
    all_sports = Team.objects.exclude(sport__isnull=True).exclude(sport='').values_list('sport', flat=True).distinct().order_by('sport')
    all_teams = Team.objects.all().order_by('name')
    
    # Map leagues to sports for filtering
    leagues_by_sport = {}
    for sport in all_sports:
        leagues = Team.objects.filter(sport=sport).values_list('league', flat=True).distinct().order_by('league')
        leagues_by_sport[sport] = list(leagues)
    
    return render(request, 'onboarding.html', {
        'all_sports': all_sports,
        'all_teams': all_teams,
        'leagues_by_sport': leagues_by_sport
    })

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
    total_premium = UserProfile.objects.filter(is_premium=True).count()
    recent_teams = Team.objects.all().order_by('-id')[:5]
    
    return render(request, 'admin_dashboard/dashboard.html', {
        'total_users': total_users,
        'total_premium': total_premium,
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
    premium_users = User.objects.filter(is_superuser=False, profile__is_premium=True).order_by('-date_joined')
    return render(request, 'admin_dashboard/users_admin.html', {
        'organizers': organizers,
        'regular_users': regular_users,
        'premium_users': premium_users
    })

@login_required
@user_passes_test(is_admin)
def admin_transactions(request):
    """
    View for admin to see all transactions (ticket purchases).
    """
    transactions = Ticket.objects.all().select_related('user', 'match', 'match__home_team', 'match__away_team', 'match__venue').order_by('-purchase_date')
    return render(request, 'admin_dashboard/transactions.html', {'transactions': transactions})

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
        'base_url': 'https://site.api.espn.com/apis/site/v2/sports',
        'endpoints': [
            {'name': 'Teams List', 'url': '/[SPORT]/[LEAGUE]/teams', 'purpose': 'Fetches all clubs, logos, and stadium info.'},
            {'name': 'Scoreboard', 'url': '/[SPORT]/[LEAGUE]/scoreboard', 'purpose': 'Fetches fixtures, live scores, and match results.'},
            {'name': 'News Articles', 'url': '/[SPORT]/[LEAGUE]/news', 'purpose': 'Fetches latest headlines and media content.'},
        ],
        'leagues': [
            'English Premier League (Football)',
            'Spanish La Liga (Football)',
            'NBA (Basketball)',
            'NFL (American Football)'
        ],
        'api_limits': {
            'rate_limit': 'Unlimited (Public Access)',
            'request_quota': 'No Quota Restrictions',
            'auth_method': 'Standard HTTP (No Key Required)',
            'data_residency': 'Daily Sync (Local Cache)',
            'usage_percent': 12 # Mock percentage for UI richness
        },
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
            # Seed all configured leagues
            call_command('seed_sports_data')
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
def sync_sports_rosters(request):
    """
    Triggers the management command to fetch latest roster data separately.
    """
    from django.core.management import call_command
    import threading

    def d_sync():
        try:
            cache.set('sports_sync_running', True, 300)
            call_command('seed_sports_data', rosters_only=True)
        except Exception as e:
            print(f"Sync Roster Error: {e}")
        finally:
            cache.delete('sports_sync_running')

    thread = threading.Thread(target=d_sync)
    thread.start()
    
    messages.success(request, "Roster synchronization started. Teams' squads will be updated shortly.")
    return redirect('system_settings')

@login_required
@user_passes_test(is_admin)
def sync_sports_news(request):
    """
    Triggers the management command to fetch latest news data separately.
    """
    from django.core.management import call_command
    import threading

    def d_sync():
        try:
            cache.set('sports_sync_running', True, 300)
            call_command('seed_sports_data', news_only=True)
        except Exception as e:
            print(f"Sync News Error: {e}")
        finally:
            cache.delete('sports_sync_running')

    thread = threading.Thread(target=d_sync)
    thread.start()
    
    messages.success(request, "News synchronization started. Latest articles will be available shortly.")
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
        'total_revenue': Ticket.objects.filter(match__organizer=request.user).aggregate(Sum('total_price'))['total_price__sum'] or 0,
    }
    return render(request, 'organizer_dashboard/dashboard.html', context)

@login_required
@user_passes_test(is_organizer)
def organizer_events_list(request):
    query = request.GET.get('q')
    # Filter for future/current matches only
    matches = Match.objects.filter(date_time__gte=timezone.now())
    
    if query:
        matches = matches.filter(
            Q(home_team__name__icontains=query) | 
            Q(away_team__name__icontains=query) |
            Q(league__icontains=query)
        ).distinct()
        
    matches = matches.order_by('date_time')
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
        ticket_price = request.POST.get('ticket_price', 50.00)
        
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
            ticket_price=ticket_price,
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
        match.ticket_price = request.POST.get('ticket_price', 50.00)
        match.match_events = request.POST.get('match_events', '')
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
@user_passes_test(is_organizer)
def organizer_profile(request):
    """
    Dedicated profile page for organizers inside the dashboard.
    """
    profile = request.user.profile
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('organizer_profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    # Stats for profile overview
    organized_matches = Match.objects.filter(organizer=request.user)
    stats = {
        'total_events': organized_matches.count(),
        'active_events': organized_matches.filter(status__in=['scheduled', 'live']).count(),
        'completed_events': organized_matches.filter(status='finished').count(),
    }

    return render(request, 'organizer_dashboard/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'stats': stats
    })


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
    
    if profile.role == 'user' and not profile.onboarding_completed:
        return redirect('user_onboarding')
        
    favorite_teams = profile.favorite_teams.all()
    
    recommended_matches = []
    suggested_events = []
    
    if favorite_teams.exists():
        # --- Tier 1: Matches involving favorite teams ---
        recommended_matches = list(
            Match.objects.filter(
                Q(home_team__in=favorite_teams) | Q(away_team__in=favorite_teams),
                Q(status='live') | Q(status='scheduled', date_time__gte=timezone.now())
            ).select_related('home_team', 'away_team', 'venue').annotate(
                status_priority=Case(
                    When(status='live', then=Value(1)),
                    When(status='scheduled', then=Value(2)),
                    default=Value(3),
                    output_field=IntegerField(),
                )
            ).order_by('status_priority', 'date_time')[:5]
        )
        
        # --- Tier 2: Other matches in followed leagues ---
        fav_leagues = list(favorite_teams.values_list('league', flat=True).distinct())
        already_shown_ids = [m.id for m in recommended_matches]
        
        if fav_leagues:
            league_matches = list(
                Match.objects.filter(
                    league__in=fav_leagues,
                    status__in=['scheduled', 'live']
                ).filter(
                    Q(status='live') | Q(status='scheduled', date_time__gte=timezone.now())
                ).exclude(
                    id__in=already_shown_ids
                ).select_related('home_team', 'away_team', 'venue').annotate(
                    status_priority=Case(
                        When(status='live', then=Value(1)),
                        When(status='scheduled', then=Value(2)),
                        default=Value(3),
                        output_field=IntegerField(),
                    )
                ).order_by('status_priority', 'date_time')[:3]
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
               Q(status='live') | Q(status='scheduled', date_time__gte=timezone.now())
            ).select_related('home_team', 'away_team', 'venue').order_by('?')[:2]
        )
    else:
        # --- Tier 4: Trending fallback for new users ---
        recommended_matches = list(
            Match.objects.filter(
                Q(status='live') | Q(status='scheduled', date_time__gte=timezone.now())
            ).select_related('home_team', 'away_team', 'venue').annotate(
                status_priority=Case(
                    When(status='live', then=Value(1)),
                    When(status='scheduled', then=Value(2)),
                    default=Value(3),
                    output_field=IntegerField(),
                )
            ).order_by('status_priority', 'date_time')[:6]
        )
        for m in recommended_matches:
            m.is_trending = True

    # Compute followed leagues count for sidebar
    followed_leagues_count = favorite_teams.values_list('league', flat=True).distinct().count() if favorite_teams.exists() else 0

    # Fetch news from DB - Ordered by latest, prioritized by favorite leagues
    if favorite_teams.exists():
        fav_leagues = favorite_teams.values_list('league', flat=True).distinct()
        news_articles = NewsArticle.objects.filter(category__in=fav_leagues).order_by('-published_at')[:4]
        # Fallback if no specific league news found
        if not news_articles.exists():
            news_articles = NewsArticle.objects.all().order_by('-published_at')[:4]
    else:
        news_articles = NewsArticle.objects.all().order_by('-published_at')[:4]

    # Trending Discussions & Community
    trending_polls = Poll.objects.all().order_by('-created_at')[:1]
    
    # Mark polls the user has already voted on
    for poll in trending_polls:
        user_vote = PollVote.objects.filter(poll=poll, user=request.user).first()
        if user_vote:
            poll.user_has_voted = True
            poll.user_choice = user_vote.choice
        else:
            poll.user_has_voted = False

    trending_communities = CommunityGroup.objects.all().order_by('-created_at')[:2]

    context = {
        'favorite_teams': favorite_teams,
        'recommended_matches': recommended_matches,
        'suggested_events': suggested_events,
        'has_favorites': favorite_teams.exists(),
        'followed_leagues_count': followed_leagues_count,
        'news_articles': news_articles,
        'trending_polls': trending_polls,
        'trending_communities': trending_communities,
    }
    return render(request, 'user_dashboard.html', context)


def events_list(request):
    """View to list all upcoming sports events/matches."""
    query = request.GET.get('q', '')
    league_filter = request.GET.get('league', '')
    
    matches = Match.objects.filter(
        Q(status='live') | Q(status='scheduled', date_time__gte=timezone.now())
    ).select_related('home_team', 'away_team', 'venue')
    
    if query:
        matches = matches.filter(
            Q(home_team__name__icontains=query) | 
            Q(away_team__name__icontains=query) |
            Q(league__icontains=query)
        )
    
    if league_filter:
        matches = matches.filter(league=league_filter)
        
    matches = matches.annotate(
        status_priority=Case(
            When(status='live', then=Value(1)),
            When(status='scheduled', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('status_priority', 'date_time')
    
    leagues = Match.objects.filter(
        Q(status='live') | Q(status='scheduled', date_time__gte=timezone.now())
    ).values_list('league', flat=True).distinct().order_by('league')
    
    context = {
        'matches': matches,
        'leagues': leagues,
        'selected_league': league_filter,
        'query': query,
    }
    return render(request, 'events_list.html', context)


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

    polls = match.polls.all()
    
    context = {
        'match': match,
        'home_recent': home_recent,
        'away_recent': away_recent,
        'is_live': match.status == 'live',
        'polls': polls,
    }
    return render(request, 'match_detail.html', context)


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

@login_required
def public_organizer_profile(request, username):
    """
    Publicly accessible profile page for organizers.
    Shows their bio and all events they are managing.
    """
    organizer = get_object_or_404(User, username=username)
    
    # Check if they are actually an organizer
    if not hasattr(organizer, 'profile') or organizer.profile.role != 'organizer':
        messages.error(request, "This user is not an organizer.")
        return redirect('index')

    organized_matches = Match.objects.filter(organizer=organizer).order_by('-date_time')
    
    context = {
        'organizer': organizer,
        'matches': organized_matches,
        'total_events': organized_matches.count()
    }
    return render(request, 'organizer_public.html', context)



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
    ticket_price = match.ticket_price
    booking_fee = float(ticket_price) * 0.05
    total_price = float(ticket_price) + booking_fee
    context = {
        'match': match,
        'booking_fee': booking_fee,
        'total_price': total_price
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
        
        total_price = float(match.ticket_price) * 1.05 # Price + 5% fee
        
        Ticket.objects.create(
            user=request.user,
            match=match,
            total_price=total_price,
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

@login_required
def premium_payment_view(request):
    """View to display mock payment page for premium membership."""
    context = {
        'payment_type': 'premium',
        'total_price': 999.00,
        'booking_fee': 0.00,
    }
    return render(request, 'payment_mock.html', context)

@login_required
def process_premium_payment(request):
    """Processes the mock payment for premium and upgrades the user."""
    if request.method == 'POST':
        profile = request.user.profile
        profile.is_premium = True
        profile.save()
        messages.success(request, "Congratulations! You are now a Premium Member.")
    return redirect('user_dashboard')

from django.db.models import Q
from functools import reduce
import operator

@login_required
def fav_team_news(request):
    # GET: Fetch news and players related to the user's favorite teams.
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    favorite_teams = profile.favorite_teams.prefetch_related('players').all()
    
    # Track if we are showing fallback news
    is_fallback = False
    news_articles = []
    
    if favorite_teams.exists():
        leagues = list(favorite_teams.values_list('league', flat=True).distinct())
        # Live Sync
        sync_news_for_leagues(leagues)
        
        # 1. Try specific team news with flexible keywords
        team_keywords = []
        for team in favorite_teams:
            name = team.name
            team_keywords.append(name)
            
            # Common abbreviations and specific specific fixes
            name_lower = name.lower()
            if "manchester city" in name_lower:
                team_keywords.append("Man City")
            elif "manchester united" in name_lower:
                team_keywords.append("Man Utd")
            elif "arsenal" in name_lower:
                team_keywords.append("Gunners")
            elif "barcelona" in name_lower:
                team_keywords.append("Barca")
            elif "real madrid" in name_lower:
                team_keywords.append("Los Blancos")
            
            # Add short names if they're likely to be specific
            if ' ' in name:
                parts = name.split(' ')
                # E.g. "FC Barcelona" -> "Barcelona"
                if parts[0].lower() in ['fc', 'rc', 'as', 'ssc', 'real', 'atletico', 'borussia']:
                    team_keywords.append(' '.join(parts[1:]))
                
                # E.g. "Arsenal FC" -> "Arsenal"
                if parts[-1].lower() in ['fc', 'united', 'city', 'town', 'rovers', 'hotspur', 'wanderers', 'albion', 'athletic']:
                    short_name = ' '.join(parts[:-1])
                    # Avoid generic standalone city names that multiple teams share
                    if short_name.lower() not in ['manchester', 'real', 'atletico', 'madrid', 'milan']:
                        team_keywords.append(short_name)
        
        # Unique keywords, minimum length 4
        team_keywords = list(set(k for k in team_keywords if len(k) > 3))
        
        # Final filter to ensure no generic words slipped through as standalone
        BANNED_STANDALONE = {'manchester', 'united', 'city', 'real', 'madrid', 'milan', 'atletico'}
        team_keywords = [k for k in team_keywords if k.lower() not in BANNED_STANDALONE]
        
        if team_keywords:
            team_query = reduce(operator.or_, [Q(headline__icontains=kw) | Q(summary__icontains=kw) for kw in team_keywords])
            news_articles = list(NewsArticle.objects.filter(team_query).order_by('-published_at'))
        else:
            news_articles = []
        
        # 2. Fallback to League News if specific team news is sparse
        if len(news_articles) < 5:
            already_shown_ids = [a.id for a in news_articles]
            league_news = NewsArticle.objects.filter(category__in=leagues).exclude(id__in=already_shown_ids).order_by('-published_at')[:10]
            
            # Mark these as league news for the template
            for art in league_news:
                art.is_league_fallback = True
            
            news_articles.extend(list(league_news))
            if news_articles:
                is_fallback = True

    context = {
        'news_articles': news_articles,
        'favorite_teams': favorite_teams,
        'is_fallback': is_fallback
    }
    return render(request, 'fav_team_news.html', context)

def latest_news(request):
    """
    Publicly accessible view for all latest news.
    If logged in, prioritise favorite league news.
    """
    if request.user.is_authenticated:
        favorite_teams = request.user.profile.favorite_teams.all()
        if favorite_teams.exists():
            favorite_leagues = favorite_teams.values_list('league', flat=True).distinct()
            news_articles = NewsArticle.objects.filter(category__in=favorite_leagues).order_by('-published_at')
            if not news_articles.exists():
                news_articles = NewsArticle.objects.all().order_by('-published_at')
        else:
            news_articles = NewsArticle.objects.all().order_by('-published_at')
    else:
        news_articles = NewsArticle.objects.all().order_by('-published_at')

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

# Event Management Module Views

def search_results(request):
    """
    Robust search for events, teams, and news content.
    """
    query = request.GET.get('q', '')
    matches = []
    teams = []
    news = []
    
    if query:
        matches = Match.objects.filter(
            Q(home_team__name__icontains=query) | 
            Q(away_team__name__icontains=query) |
            Q(league__icontains=query) |
            Q(venue__name__icontains=query)
        ).distinct()
        
        teams = Team.objects.filter(
            Q(name__icontains=query) |
            Q(league__icontains=query) |
            Q(description__icontains=query)
        ).distinct()
        
        news = NewsArticle.objects.filter(
            Q(headline__icontains=query) |
            Q(summary__icontains=query) |
            Q(content__icontains=query)
        ).distinct()
        
    context = {
        'query': query,
        'matches': matches,
        'teams': teams,
        'news': news,
    }
    return render(request, 'search_results.html', context)

@login_required
def community_list(request):
    """
    List all fan groups and forums.
    """
    groups = CommunityGroup.objects.all().order_by('-created_at')
    return render(request, 'community_list.html', {'groups': groups})

@login_required
def community_detail(request, group_id):
    """
    Detailed view of a community group with forum messages.
    """
    group = get_object_or_404(CommunityGroup, id=group_id)
    is_member = request.user in group.members.all()
    is_creator = (request.user == group.creator)
    
    # Check join request status
    from .models import CommunityJoinRequest
    join_request = CommunityJoinRequest.objects.filter(group=group, user=request.user, status='pending').first()
    
    # Visibility logic: if not public and not member, hide messages
    messages_list = []
    if group.is_public or is_member:
        messages_list = group.messages.all().order_by('created_at')
    
    # Pending requests for creator/owner
    pending_requests = []
    group_members = []
    if is_creator:
        pending_requests = group.join_requests.filter(status='pending')
        group_members = group.members.exclude(id=group.creator.id)
    
    if request.method == 'POST':
        if 'join' in request.POST:
            if group.require_approval:
                CommunityJoinRequest.objects.get_or_create(group=group, user=request.user, defaults={'status': 'pending'})
                messages.info(request, "Your join request has been sent to the community moderator.")
            else:
                group.members.add(request.user)
                messages.success(request, f"Welcome to the {group.name} community!")
            return redirect('community_detail', group_id=group.id)
        
        elif 'send_message' in request.POST and is_member:
            content = request.POST.get('content')
            if content:
                CommunityMessage.objects.create(
                    group=group,
                    user=request.user,
                    content=content
                )
                return redirect('community_detail', group_id=group.id)
        
    return render(request, 'community_detail.html', {
        'group': group,
        'is_member': is_member,
        'is_creator': is_creator,
        'forum_messages': messages_list,
        'join_request': join_request,
        'pending_requests': pending_requests,
        'group_members': group_members
    })

@login_required
def process_join_request(request, request_id, action):
    from .models import CommunityJoinRequest
    join_req = get_object_or_404(CommunityJoinRequest, id=request_id)
    
    # Only creator can approve/reject
    if join_req.group.creator != request.user:
        messages.error(request, "Permission denied.")
        return redirect('community_detail', group_id=join_req.group.id)
        
    if action == 'approve':
        join_req.status = 'approved'
        join_req.group.members.add(join_req.user)
        join_req.save()
        messages.success(request, f"Approved {join_req.user.username}'s request.")
    elif action == 'reject':
        join_req.status = 'rejected'
        join_req.save()
        messages.info(request, f"Rejected {join_req.user.username}'s request.")
        
    return redirect('community_detail', group_id=join_req.group.id)

@login_required
def remove_member(request, group_id, user_id):
    group = get_object_or_404(CommunityGroup, id=group_id)
    if group.creator != request.user:
        messages.error(request, "Permission denied.")
        return redirect('community_detail', group_id=group.id)
    
    target_user = get_object_or_404(User, id=user_id)
    if target_user != group.creator:
        group.members.remove(target_user)
        messages.success(request, f"Successfully removed {target_user.username} from the community.")
    
    return redirect('community_detail', group_id=group.id)

@login_required
def toggle_community_setting(request, group_id, setting):
    group = get_object_or_404(CommunityGroup, id=group_id)
    if group.creator != request.user:
        messages.error(request, "Permission denied.")
        return redirect('community_detail', group_id=group.id)
    
    if setting == 'public':
        group.is_public = not group.is_public
        status = "Public" if group.is_public else "Private"
        messages.success(request, f"Community visibility updated: Now {status}.")
    elif setting == 'approval':
        group.require_approval = not group.require_approval
        status = "ON" if group.require_approval else "OFF"
        messages.success(request, f"Manual approval is now {status}.")
    
    group.save()
    return redirect('community_detail', group_id=group.id)

def team_detail(request, team_id):
    """
    Comprehensive team profile with stats and roster.
    """
    team = get_object_or_404(Team.objects.prefetch_related('players'), id=team_id)
    recent_matches = Match.objects.filter(Q(home_team=team) | Q(away_team=team)).order_by('-date_time')[:5]
    
    is_following = False
    if request.user.is_authenticated:
        is_following = request.user.profile.favorite_teams.filter(id=team.id).exists()
        
        if request.method == 'POST' and 'toggle_follow' in request.POST:
            if is_following:
                request.user.profile.favorite_teams.remove(team)
                messages.info(request, f"You are no longer following {team.name}")
            else:
                request.user.profile.favorite_teams.add(team)
                messages.success(request, f"Success! You are now following {team.name}")
            return redirect('team_detail', team_id=team.id)

    return render(request, 'team_detail.html', {
        'team': team,
        'recent_matches': recent_matches,
        'is_following': is_following
    })

def player_detail(request, player_id):
    """
    Detailed player profile.
    """
    player = get_object_or_404(Player.objects.select_related('team'), id=player_id)
    return render(request, 'player_detail.html', {'player': player})

@login_required
def vote_poll(request, poll_id):
    """
    Allows users to vote on match outcomes/performance.
    """
    poll = get_object_or_404(Poll, id=poll_id)
    if request.method == 'POST':
        # Check if user has already voted
        if PollVote.objects.filter(poll=poll, user=request.user).exists():
            messages.warning(request, "You have already voted on this poll.")
            return redirect(request.META.get('HTTP_REFERER', 'index'))

        choice = request.POST.get('option') # Changed from 'choice' to 'option' to match template
        if choice == 'a':
            poll.votes_a += 1
            PollVote.objects.create(poll=poll, user=request.user, choice='a')
        elif choice == 'b':
            poll.votes_b += 1
            PollVote.objects.create(poll=poll, user=request.user, choice='b')
        
        poll.save()
        messages.success(request, "Vote recorded! Thanks for participating.")
    
    return redirect(request.META.get('HTTP_REFERER', 'index'))

@login_required
def create_community(request):
    """
    View to create a new fan group or community.
    """
    if request.method == 'POST':
        form = CommunityGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.creator = request.user
            group.save()
            group.members.add(request.user)
            messages.success(request, f"Community group '{group.name}' created successfully!")
            return redirect('community_detail', group_id=group.id)
    else:
        form = CommunityGroupForm()
    
    return render(request, 'create_community.html', {'form': form})

def load_teams(request):
    league = request.GET.get('league')
    from .models import Team
    teams = Team.objects.filter(league=league).order_by('name')
    return render(request, 'team_dropdown_list_options.html', {'teams': teams})


# ─────────────────────────────────────────────────────────────────────────────
# TEAM & PLAYER MANAGEMENT  (Admin + Organizer)
# ─────────────────────────────────────────────────────────────────────────────

def is_admin_or_organizer(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role in ('admin', 'organizer')


@login_required
@user_passes_test(is_admin_or_organizer)
def admin_teams(request):
    """List all teams with search/filter."""
    qs = Team.objects.select_related('venue').prefetch_related('players').order_by('league', 'name')
    q = request.GET.get('q', '').strip()
    sport = request.GET.get('sport', '').strip()
    league = request.GET.get('league', '').strip()

    if q:
        qs = qs.filter(name__icontains=q)
    if sport:
        qs = qs.filter(sport=sport)
    if league:
        qs = qs.filter(league=league)

    sports = Team.objects.values_list('sport', flat=True).distinct().order_by('sport')
    leagues = Team.objects.values_list('league', flat=True).distinct().order_by('league')

    return render(request, 'admin_dashboard/teams_list.html', {
        'teams': qs,
        'sports': sports,
        'leagues': leagues,
    })


@login_required
@user_passes_test(is_admin_or_organizer)
def admin_team_edit(request, team_id):
    """Edit a team's details and logo."""
    team = get_object_or_404(Team, id=team_id)
    venues = Venue.objects.all().order_by('name')

    if request.method == 'POST':
        team.name = request.POST.get('name', team.name).strip()
        team.sport = request.POST.get('sport', team.sport).strip()
        team.league = request.POST.get('league', team.league).strip()
        team.description = request.POST.get('description', '').strip()
        est = request.POST.get('established_year', '').strip()
        team.established_year = int(est) if est.isdigit() else None
        venue_id = request.POST.get('venue')
        team.venue = Venue.objects.filter(id=venue_id).first() if venue_id else None

        if 'logo' in request.FILES:
            team.logo = request.FILES['logo']

        team.save()
        messages.success(request, f'✅ {team.name} updated successfully.')
        return redirect('admin_team_edit', team_id=team.id)

    return render(request, 'admin_dashboard/team_edit.html', {
        'team': team,
        'venues': venues,
    })


@login_required
@user_passes_test(is_admin_or_organizer)
def admin_team_players(request, team_id):
    """View all players for a team."""
    team = get_object_or_404(Team, id=team_id)
    players = team.players.all().order_by('name')
    return render(request, 'admin_dashboard/team_players.html', {
        'team': team,
        'players': players,
    })


@login_required
@user_passes_test(is_admin_or_organizer)
def admin_player_add(request, team_id):
    """Add a player to a team."""
    team = get_object_or_404(Team, id=team_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        position = request.POST.get('position', '').strip()
        nationality = request.POST.get('nationality', '').strip()
        if name:
            Player.objects.create(team=team, name=name, position=position, nationality=nationality)
            messages.success(request, f'✅ Player "{name}" added to {team.name}.')
        else:
            messages.error(request, 'Player name is required.')
    return redirect('admin_team_players', team_id=team.id)


@login_required
@user_passes_test(is_admin_or_organizer)
def admin_player_edit(request, player_id):
    """Edit a player's details."""
    player = get_object_or_404(Player, id=player_id)
    if request.method == 'POST':
        player.name = request.POST.get('name', player.name).strip()
        player.position = request.POST.get('position', '').strip()
        player.nationality = request.POST.get('nationality', '').strip()
        player.photo_url = request.POST.get('photo_url', '').strip()
        dob = request.POST.get('dob', '').strip()
        if dob:
            from datetime import date
            try:
                player.dob = datetime.strptime(dob, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            player.dob = None
        player.save()
        messages.success(request, f'✅ Player "{player.name}" updated.')
    return redirect('admin_team_players', team_id=player.team.id)


@login_required
@user_passes_test(is_admin_or_organizer)
def admin_player_delete(request, player_id):
    """Delete a player."""
    player = get_object_or_404(Player, id=player_id)
    team_id = player.team.id
    name = player.name
    player.delete()
    messages.success(request, f'🗑️ Player "{name}" removed.')
    return redirect('admin_team_players', team_id=team_id)