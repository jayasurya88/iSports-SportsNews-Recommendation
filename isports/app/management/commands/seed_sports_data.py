from django.core.management.base import BaseCommand
import urllib.request
import json
import ssl
import socket
from datetime import datetime, timedelta
from app.models import Team, Match, Venue, NewsArticle
from django.core.files.base import ContentFile
import time

# Fix SSL errors
ssl._create_default_https_context = ssl._create_unverified_context
socket.setdefaulttimeout(30)

# ESPN public API (no key needed, no rate limits)
ESPN_BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer'

# Leagues to fetch — real fixture data, real teams
LEAGUES = [
    {'slug': 'eng.1', 'name': 'English Premier League', 'sport': 'Football'},
    {'slug': 'esp.1', 'name': 'Spanish La Liga',        'sport': 'Football'},
    {'slug': 'ger.1', 'name': 'German Bundesliga',       'sport': 'Football'},
    {'slug': 'ita.1', 'name': 'Italian Serie A',          'sport': 'Football'},
    {'slug': 'fra.1', 'name': 'French Ligue 1',           'sport': 'Football'},
    {'slug': 'ind.1', 'name': 'Indian Super League',      'sport': 'Football'},
]

HEADERS = {'User-Agent': 'iSports-Student-Project/1.0'}


class Command(BaseCommand):
    help = 'Seeds database with real teams & fixtures from ESPN free API.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fresh',
            action='store_true',
            help='Wipe database before seeding (resets favorites)',
        )
        parser.add_argument(
            '--no-logos',
            action='store_true',
            help='Skip downloading team logos',
        )

    def _api_get(self, url):
        """Fetch JSON with retries."""
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read())
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  API attempt {attempt+1} failed: {e}'))
                time.sleep(2)
        return None

    def _download_logo(self, team_obj, logo_url):
        """Download and save a team logo."""
        if not logo_url or team_obj.logo:
            return
        try:
            req = urllib.request.Request(logo_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                fname = f"{team_obj.name.replace(' ', '_')}_logo.png"
                team_obj.logo.save(fname, ContentFile(resp.read()), save=True)
            time.sleep(0.2)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Logo download failed for {team_obj.name}: {e}'))

    def handle(self, *args, **options):
        is_fresh = options.get('fresh')
        skip_logos = options.get('no_logos')

        if is_fresh:
            self.stdout.write(self.style.WARNING('Cleaning up existing sports data...'))
            Match.objects.all().delete()
            Team.objects.all().delete()
            Venue.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleanup complete.'))
        else:
            self.stdout.write(self.style.SUCCESS('Running in smart-update mode (preserving teams & favorites).'))

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  iSports — Seeding from ESPN Free API'))
        self.stdout.write(self.style.SUCCESS('  Real teams · Real fixtures · No API key'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # Date range: today → +30 days
        today = datetime.now()
        date_from = today.strftime('%Y%m%d')
        date_to = (today + timedelta(days=30)).strftime('%Y%m%d')

        total_teams = 0
        total_matches = 0

        for league_info in LEAGUES:
            slug = league_info['slug']
            league_name = league_info['name']
            sport_name = league_info['sport']

            self.stdout.write(self.style.SUCCESS(f'\n▶ {league_name} ({slug})'))

            # ---------------------------------------------------------
            # 1. Fetch teams
            # ---------------------------------------------------------
            teams_url = f'{ESPN_BASE}/{slug}/teams'
            data = self._api_get(teams_url)

            if not data:
                self.stdout.write(self.style.WARNING(f'  Could not fetch teams for {league_name}'))
                continue

            # Navigate the ESPN JSON structure
            api_teams = []
            for sport in data.get('sports', []):
                for league in sport.get('leagues', []):
                    for t in league.get('teams', []):
                        api_teams.append(t.get('team', {}))

            if not api_teams:
                self.stdout.write(self.style.WARNING(f'  No teams found for {league_name}'))
                continue

            self.stdout.write(f'  Found {len(api_teams)} teams')
            league_teams = []

            for t in api_teams:
                team_name = t.get('displayName', '') or t.get('name', '')
                if not team_name:
                    continue

                # Get logo URL (first logo)
                logos = t.get('logos', [])
                logo_url = logos[0].get('href', '') if logos else ''

                # Create venue from team location
                location = t.get('location', team_name)
                venue, _ = Venue.objects.get_or_create(
                    name=f'{team_name} Stadium',
                    defaults={
                        'city': location.split(',')[0].strip() if ',' in location else location,
                        'capacity': 0,
                    }
                )

                # Create/update Team
                team, created = Team.objects.update_or_create(
                    name=team_name,
                    defaults={
                        'league': league_name,
                        'sport': sport_name,
                        'venue': venue,
                    }
                )
                league_teams.append(team)

                # Download logo
                if not skip_logos:
                    self._download_logo(team, logo_url)

                if created:
                    self.stdout.write(f'  + {team_name}')

            total_teams += len(league_teams)

            # ---------------------------------------------------------
            # 2. Fetch fixtures for next 30 days
            # ---------------------------------------------------------
            self.stdout.write(f'  Fetching fixtures ({date_from} to {date_to})...')
            fixtures_url = f'{ESPN_BASE}/{slug}/scoreboard?dates={date_from}-{date_to}'
            fixtures_data = self._api_get(fixtures_url)

            matches_created = 0
            events = fixtures_data.get('events', []) if fixtures_data else []

            for event in events:
                event_name = event.get('name', '')
                event_date_str = event.get('date', '')

                # Get competition details
                comps = event.get('competitions', [])
                if not comps:
                    continue
                comp = comps[0]

                # Parse competitors (home & away)
                competitors = comp.get('competitors', [])
                if len(competitors) < 2:
                    continue

                home_data = None
                away_data = None
                for c in competitors:
                    if c.get('homeAway') == 'home':
                        home_data = c
                    elif c.get('homeAway') == 'away':
                        away_data = c

                if not home_data or not away_data:
                    continue

                home_name = home_data.get('team', {}).get('displayName', '')
                away_name = away_data.get('team', {}).get('displayName', '')

                # Find teams in our DB
                home_team = Team.objects.filter(name=home_name).first()
                away_team = Team.objects.filter(name=away_name).first()
                if not home_team or not away_team:
                    continue

                # Parse date
                try:
                    # ESPN dates: "2026-02-21T15:00Z"
                    dt = datetime.strptime(event_date_str[:16], '%Y-%m-%dT%H:%M')
                except (ValueError, TypeError):
                    dt = today + timedelta(days=1)

                # Status mapping
                espn_status = comp.get('status', {}).get('type', {}).get('state', 'pre')
                status_map = {
                    'pre': 'scheduled',
                    'in': 'live',
                    'post': 'finished'
                }
                final_status = status_map.get(espn_status, 'scheduled')

                # Scores
                h_score = int(home_data.get('score', 0))
                a_score = int(away_data.get('score', 0))

                # Get venue
                venue_info = comp.get('venue', {})
                venue_name = venue_info.get('fullName', '')
                venue_city = venue_info.get('address', {}).get('city', '')

                match_venue = None
                if venue_name:
                    match_venue, _ = Venue.objects.get_or_create(
                        name=venue_name,
                        defaults={
                            'city': venue_city or 'Unknown',
                            'capacity': 0,
                        }
                    )
                if not match_venue:
                    match_venue = home_team.venue

                match_obj, created = Match.objects.update_or_create(
                    home_team=home_team,
                    away_team=away_team,
                    date_time=dt,
                    defaults={
                        'venue': match_venue,
                        'league': league_name,
                        'status': final_status,
                        'home_score': h_score,
                        'away_score': a_score,
                    }
                )
                if created:
                    matches_created += 1
                    self.stdout.write(f'  ⚽ {home_name} vs {away_name} — {dt.strftime("%b %d, %H:%M")}')
                elif final_status == 'live':
                    self.stdout.write(f'  🔥 LIVE: {home_name} {h_score}-{a_score} {away_name}')

            total_matches += matches_created
            self.stdout.write(f'  → synced {len(league_teams)} teams, {matches_created} new fixtures')

        # ---------------------------------------------------------
        # 3. Fetch News
        # ---------------------------------------------------------
        self.stdout.write(self.style.SUCCESS('\n▶ Fetching Soccer News...'))
        news_url = "http://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/news?limit=20"
        news_data = self._api_get(news_url)
        
        if news_data:
            articles = news_data.get('articles', [])
            NewsArticle.objects.all().delete() # Start fresh with news
            for art in articles:
                NewsArticle.objects.create(
                    headline=art.get('headline', ''),
                    summary=art.get('description', ''),
                    content=art.get('story', art.get('description', '')),
                    image_url=art.get('images', [{}])[0].get('url') if art.get('images') else '',
                    source_url=art.get('links', {}).get('web', {}).get('href', ''),
                    published_at=art.get('published', '')[:10]
                )
            self.stdout.write(f'  → synced {len(articles)} news articles')

        # Final summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS(f'  DONE! Teams: {Team.objects.count()} | Matches: {Match.objects.count()}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
