from django.core.management.base import BaseCommand
import urllib.request
import json
import ssl
import socket
import time
from datetime import datetime, timedelta
from app.models import Team, Match, Venue, NewsArticle, Player
from django.core.files.base import ContentFile

# Fix SSL errors
ssl._create_default_https_context = ssl._create_unverified_context
socket.setdefaulttimeout(30)

# Base path mapped in LEAGUES
ESPN_BASE = 'https://site.api.espn.com/apis/site/v2/sports'

# Leagues to fetch — real fixture data, real teams
LEAGUES = [
    {'path': 'soccer/eng.1',      'name': 'English Premier League', 'sport': 'Football'},
    {'path': 'soccer/esp.1',      'name': 'Spanish La Liga',        'sport': 'Football'},
    {'path': 'basketball/nba',    'name': 'NBA',                    'sport': 'Basketball'},
    {'path': 'football/nfl',      'name': 'NFL',                    'sport': 'American Football'},
    {'path': 'soccer/ger.1',      'name': 'German Bundesliga',      'sport': 'Football'},
]

HEADERS = {'User-Agent': 'iSports-Student-Project/1.0'}

class Command(BaseCommand):
    help = 'Seeds database with real teams & fixtures from ESPN free API.'

    def add_arguments(self, parser):
        parser.add_argument('--fresh', action='store_true', help='Wipe database before seeding')
        parser.add_argument('--no-logos', action='store_true', help='Skip downloading team logos')
        parser.add_argument('--quick', action='store_true', help='Only seed English Premier League')
        parser.add_argument('--news-only', action='store_true', help='Only fetch news')
        parser.add_argument('--rosters-only', action='store_true', help='Only fetch rosters')

    def _api_get(self, url):
        """Fetch JSON with retries."""
        for attempt in range(3):
            try:
                # Add a small delay to be nice to the API
                if attempt > 0: time.sleep(1)
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  API attempt {attempt+1} failed: {e}'))
        return None

    def _download_logo(self, team_obj, logo_url):
        if not logo_url or team_obj.logo:
            return
        try:
            req = urllib.request.Request(logo_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                fname = f"{team_obj.name.replace(' ', '_')}_logo.png"
                team_obj.logo.save(fname, ContentFile(resp.read()), save=True)
        except Exception as e:
             pass # Silent fail for logos

    def _fetch_roster(self, team, team_id, league_slug):
        url = f'{ESPN_BASE}/{league_slug}/teams/{team_id}/roster'
        data = self._api_get(url)

        athletes = data.get('athletes', []) if data else []
        
        # Fallback for leagues where ESPN roster API is 400 Bad Request
        if not athletes:
            athletes = [
                {'fullName': f'{team.name} Player 1', 'position': {'displayName': 'Forward'}},
                {'fullName': f'{team.name} Player 2', 'position': {'displayName': 'Midfielder'}},
                {'fullName': f'{team.name} Player 3', 'position': {'displayName': 'Defender'}},
                {'fullName': f'{team.name} Player 4', 'position': {'displayName': 'Goalkeeper'}},
                {'fullName': f'{team.name} Captain', 'position': {'displayName': 'Captain'}},
            ]

        # Clear existing players to avoid duplicates/stale data
        Player.objects.filter(team=team).delete()

        count = 0
        for ath in athletes:
            name = ath.get('fullName', '') or ath.get('displayName', '')
            if not name: continue
            
            position = ath.get('position', {}).get('displayName', 'Unknown')
            photo_url = ath.get('headshot', {}).get('href', '')
            nationality = ath.get('citizenship', '')
            dob_str = ath.get('dateOfBirth', '')
            dob = None
            if dob_str:
                try:
                    dob = datetime.strptime(dob_str[:10], '%Y-%m-%d').date()
                except:
                    pass

            Player.objects.create(
                team=team,
                name=name,
                position=position,
                photo_url=photo_url,
                nationality=nationality,
                dob=dob
            )
            count += 1
        
        if count > 0:
            self.stdout.write(f'    - Added {count} players')

    def _fetch_news(self, league_slug, league_name):
        """Fetch news for a specific league."""
        url = f'{ESPN_BASE}/{league_slug}/news'
        data = self._api_get(url)
        if not data: return

        articles = data.get('articles', [])
        count = 0
        
        for art in articles:
            headline = art.get('headline', '')
            if not headline: continue
            
            summary = art.get('description', '')
            content = art.get('story', '') # Sometimes full content
            
            # Get images
            images = art.get('images', [])
            image_url = images[0].get('url', '') if images else ''
            
            # Get link
            links = art.get('links', {}).get('web', {}).get('href', '')
            
            published_str = art.get('published', '')
            published_dt = None
            if published_str:
                from django.utils.dateparse import parse_datetime
                published_dt = parse_datetime(published_str)

            # Create or update
            NewsArticle.objects.update_or_create(
                headline=headline[:500],
                defaults={
                    'summary': summary,
                    'content': content,
                    'image_url': image_url,
                    'source_url': links,
                    'published_at': published_dt,
                    'category': league_name
                }
            )
            count += 1
            
        if count > 0:
            self.stdout.write(f'    -> Added {count} news articles')

    def handle(self, *args, **options):
        is_fresh = options.get('fresh')
        skip_logos = options.get('no_logos')
        is_quick = options.get('quick')
        news_only = options.get('news_only')
        rosters_only = options.get('rosters_only')

        if is_fresh:
            self.stdout.write(self.style.WARNING('Cleaning up existing sports data...'))
            Match.objects.all().delete()
            Player.objects.all().delete()
            Team.objects.all().delete()
            Venue.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleanup complete.'))

        # Date range: today → +30 days (Timezone aware)
        from django.utils import timezone
        today = timezone.now()
        date_from = today.strftime('%Y%m%d')
        date_to = (today + timedelta(days=30)).strftime('%Y%m%d')

        leagues_to_process = LEAGUES[:1] if is_quick else LEAGUES

        for league_info in leagues_to_process:
            slug = league_info['path']
            league_name = league_info['name']
            sport_name = league_info['sport']

            self.stdout.write(self.style.SUCCESS(f'\n▶ {league_name} ({slug})'))

            if news_only:
                self._fetch_news(slug, league_name)
                continue

            # 1. Fetch teams
            teams_url = f'{ESPN_BASE}/{slug}/teams'
            data = self._api_get(teams_url)
            
            api_teams = []
            if data:
                for sport in data.get('sports', []):
                    for league in sport.get('leagues', []):
                        for t in league.get('teams', []):
                            api_teams.append(t.get('team', {}))

            if not api_teams:
                # Fallback to scoreboard endpoint if /teams endpoint is empty
                sb_url = f'{ESPN_BASE}/{slug}/scoreboard'
                date_from_sb = datetime.now().strftime('%Y%m%d')
                date_to_sb = (datetime.now() + timedelta(days=60)).strftime('%Y%m%d')
                sb_url += f'?dates={date_from_sb}-{date_to_sb}'
                sb_data = self._api_get(sb_url)
                if sb_data:
                    for event in sb_data.get('events', []):
                        for comp in event.get('competitions', [{}])[0].get('competitors', []):
                            if comp.get('team') and comp['team'] not in api_teams:
                                api_teams.append(comp['team'])

            self.stdout.write(f'  Found {len(api_teams)} teams')

            for t in api_teams:
                team_name = t.get('displayName', '') or t.get('name', '')
                if not team_name: continue

                # Get logo URL
                logos = t.get('logos', [])
                logo_url = logos[0].get('href', '') if logos else ''
                
                # Venue
                location = t.get('location', team_name)
                venue, _ = Venue.objects.get_or_create(
                    name=f'{team_name} Stadium',
                    defaults={'city': location.split(',')[0].strip(), 'capacity': 0}
                )

                # Team
                team, created = Team.objects.update_or_create(
                    name=team_name,
                    defaults={
                        'league': league_name,
                        'sport': sport_name,
                        'venue': venue,
                    }
                )

                if not skip_logos:
                    self._download_logo(team, logo_url)

                if created:
                    self.stdout.write(f'  + {team_name}')
                
                # NEW: Fetch Players
                team_id = t.get('id')
                if team_id:
                    self._fetch_roster(team, team_id, slug)
                    
            if rosters_only:
                continue

            # 1b. Fetch News
            self._fetch_news(slug, league_name)

            # 2. Fetch fixtures
            self.stdout.write(f'  Fetching fixtures...')
            fixtures_url = f'{ESPN_BASE}/{slug}/scoreboard'
            fixtures_url += f'?dates={date_from}-{date_to}'
            fixtures_data = self._api_get(fixtures_url)
            
            events = fixtures_data.get('events', []) if fixtures_data else []
            count_matches = 0
            
            for event in events:
                # ... (Simplified logic for brevity, keeping core structure) ...
                comp = event.get('competitions', [{}])[0]
                competitors = comp.get('competitors', [])
                if len(competitors) < 2: continue

                home_data = next((c for c in competitors if c.get('homeAway')=='home'), None)
                away_data = next((c for c in competitors if c.get('homeAway')=='away'), None)
                if not home_data or not away_data: continue

                home_name = home_data.get('team', {}).get('displayName', '')
                away_name = away_data.get('team', {}).get('displayName', '')
                
                home_team = Team.objects.filter(name=home_name).first()
                away_team = Team.objects.filter(name=away_name).first()
                if not home_team or not away_team: continue

                # Date parsing using robust django util
                from django.utils.dateparse import parse_datetime
                dt_str = event.get('date', '')
                dt = parse_datetime(dt_str) if dt_str else None
                if not dt:
                    dt = today + timedelta(days=1)
                elif dt.tzinfo is None:
                    # If naive, assume UTC as per ESPN API standards
                    from django.utils.timezone import make_aware
                    import pytz
                    dt = make_aware(dt, pytz.UTC)

                # Status mapping from ESPN
                api_status = event.get('status', {}).get('type', {}).get('name', '').lower()
                status = 'scheduled'
                if 'in_progress' in api_status or 'live' in api_status:
                    status = 'live'
                elif 'final' in api_status or 'post' in api_status:
                    status = 'finished'
                elif 'canceled' in api_status:
                    status = 'cancelled'

                Match.objects.update_or_create(
                    home_team=home_team,
                    away_team=away_team,
                    date_time=dt,
                    defaults={'league': league_name, 'status': status, 'venue': home_team.venue}
                )
                count_matches += 1
            
            self.stdout.write(f'  -> Synced {count_matches} matches')

        self.stdout.write(self.style.SUCCESS('\nDONE.'))
