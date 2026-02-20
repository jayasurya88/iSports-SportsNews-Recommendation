import urllib.request
import json
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

url = "https://www.thesportsdb.com/api/v1/json/3/search_all_teams.php?l=English%20Premier%20League"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        teams = data.get('teams', [])
        for team in teams:
            if team.get('strTeam') == 'Arsenal':
                print(f"Arsenal Badge from API: {team.get('strTeamBadge')}")
                break
except Exception as e:
    print(f"Error: {e}")
