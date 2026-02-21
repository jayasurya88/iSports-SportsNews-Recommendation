import json
import os

# Known Logo URLs (Wikimedia/TheSportsDB/Other reliable stable URLs)
LOGOS = {
    # EPL
    'Arsenal': 'https://upload.wikimedia.org/wikipedia/en/5/53/Arsenal_FC.svg',
    'Aston Villa': 'https://upload.wikimedia.org/wikipedia/en/9/9f/Aston_Villa_FC_crest_%282016%29.svg',
    'Bournemouth': 'https://upload.wikimedia.org/wikipedia/en/e/e5/AFC_Bournemouth_%282013%29.svg',
    'Brentford': 'https://upload.wikimedia.org/wikipedia/en/2/2a/Brentford_FC_crest.svg',
    'Brighton': 'https://upload.wikimedia.org/wikipedia/en/f/fd/Brighton_%26_Hove_Albion_logo.svg',
    'Burnley': 'https://upload.wikimedia.org/wikipedia/en/6/62/Burnley_F.C._Logo.svg',
    'Chelsea': 'https://upload.wikimedia.org/wikipedia/en/c/cc/Chelsea_FC.svg',
    'Crystal Palace': 'https://upload.wikimedia.org/wikipedia/en/a/a2/Crystal_Palace_FC_logo_%282022%29.svg',
    'Everton': 'https://upload.wikimedia.org/wikipedia/en/7/7c/Everton_FC_logo.svg',
    'Fulham': 'https://upload.wikimedia.org/wikipedia/en/e/eb/Fulham_FC_%28shield%29.svg',
    'Liverpool': 'https://upload.wikimedia.org/wikipedia/en/0/0c/Liverpool_FC.svg',
    'Luton Town': 'https://upload.wikimedia.org/wikipedia/en/9/9d/Luton_Town_logo.svg',
    'Manchester City': 'https://upload.wikimedia.org/wikipedia/en/e/eb/Manchester_City_FC_badge.svg',
    'Manchester United': 'https://upload.wikimedia.org/wikipedia/en/7/7a/Manchester_United_FC_crest.svg',
    'Newcastle United': 'https://upload.wikimedia.org/wikipedia/en/5/56/Newcastle_United_Logo.svg',
    'Nottingham Forest': 'https://upload.wikimedia.org/wikipedia/en/e/e5/Nottingham_Forest_F.C._logo.svg',
    'Sheffield United': 'https://upload.wikimedia.org/wikipedia/en/9/9c/Sheffield_United_FC_logo.svg',
    'Tottenham Hotspur': 'https://upload.wikimedia.org/wikipedia/en/b/b4/Tottenham_Hotspur.svg',
    'West Ham United': 'https://upload.wikimedia.org/wikipedia/en/c/c2/West_Ham_United_FC_logo.svg',
    'Wolverhampton Wanderers': 'https://upload.wikimedia.org/wikipedia/en/f/fc/Wolverhampton_Wanderers.svg',
    
    # La Liga
    'Real Madrid': 'https://upload.wikimedia.org/wikipedia/en/5/56/Real_Madrid_CF.svg',
    'Barcelona': 'https://upload.wikimedia.org/wikipedia/en/4/47/FC_Barcelona_%28crest%29.svg',
    'Atletico Madrid': 'https://upload.wikimedia.org/wikipedia/en/f/f4/Atletico_Madrid_2017_logo.svg',
    'Girona': 'https://upload.wikimedia.org/wikipedia/en/9/90/Girona_FC_Logo.svg',
    'Athletic Bilbao': 'https://upload.wikimedia.org/wikipedia/en/9/98/Club_Athletic_Bilbao_logo.svg',
    'Real Sociedad': 'https://upload.wikimedia.org/wikipedia/en/f/f1/Real_Sociedad_logo.svg',
    'Real Betis': 'https://upload.wikimedia.org/wikipedia/en/1/13/Real_betis_logo.svg',
    'Valencia': 'https://upload.wikimedia.org/wikipedia/en/c/ce/Valenciacf.svg',
    'Villarreal': 'https://upload.wikimedia.org/wikipedia/en/7/70/Villarreal_CF_logo.svg',
    'Getafe': 'https://upload.wikimedia.org/wikipedia/en/4/4c/Getafe_CF_logo_%282023%29.svg',
    'Osasuna': 'https://upload.wikimedia.org/wikipedia/en/d/db/Osasuna_logo.svg',
    'Sevilla': 'https://upload.wikimedia.org/wikipedia/en/3/3b/Sevilla_FC_logo.svg',
    'Las Palmas': 'https://upload.wikimedia.org/wikipedia/en/b/b2/UD_Las_Palmas_logo.svg',
    'Alaves': 'https://upload.wikimedia.org/wikipedia/en/2/2e/Deportivo_Alaves_logo.svg',
    'Rayo Vallecano': 'https://upload.wikimedia.org/wikipedia/en/1/19/Rayo_Vallecano_logo.svg',
    'Mallorca': 'https://upload.wikimedia.org/wikipedia/en/e/e0/RCD_Mallorca_logo.svg',
    'Celta Vigo': 'https://upload.wikimedia.org/wikipedia/en/1/12/RC_Celta_de_Vigo_logo.svg',
    'Cadiz': 'https://upload.wikimedia.org/wikipedia/en/5/58/C%C3%A1diz_CF_logo.svg',
    'Granada': 'https://upload.wikimedia.org/wikipedia/en/d/d5/Granada_CF_logo.svg',
    'Almeria': 'https://upload.wikimedia.org/wikipedia/en/e/e0/UD_Almer%C3%ADa_logo.svg',

    # Bundesliga
    'Bayer Leverkusen': 'https://upload.wikimedia.org/wikipedia/en/5/59/Bayer_04_Leverkusen_logo.svg',
    'Bayern Munich': 'https://upload.wikimedia.org/wikipedia/commons/1/1b/FC_Bayern_M%C3%BCnchen_logo_%282017%29.svg',
    'VfB Stuttgart': 'https://upload.wikimedia.org/wikipedia/commons/e/eb/VfB_Stuttgart_1893_Logo.svg',
    'RB Leipzig': 'https://upload.wikimedia.org/wikipedia/en/0/04/RB_Leipzig_2014_logo.svg',
    'Borussia Dortmund': 'https://upload.wikimedia.org/wikipedia/commons/6/67/Borussia_Dortmund_logo.svg',
    'Eintracht Frankfurt': 'https://upload.wikimedia.org/wikipedia/commons/0/04/Eintracht_Frankfurt_Logo.svg',
    'SC Freiburg': 'https://upload.wikimedia.org/wikipedia/en/6/6d/SC_Freiburg_logo.svg',
    'Hoffenheim': 'https://upload.wikimedia.org/wikipedia/commons/e/e7/Logo_TSG_Hoffenheim.svg',
    'Heidenheim': 'https://upload.wikimedia.org/wikipedia/commons/9/9d/1._FC_Heidenheim_1846.svg',
    'Werder Bremen': 'https://upload.wikimedia.org/wikipedia/commons/b/be/SV-Werder-Bremen-Logo.svg',
    'Augsburg': 'https://upload.wikimedia.org/wikipedia/en/5/59/FC_Augsburg_logo.svg',
    'Wolfsburg': 'https://upload.wikimedia.org/wikipedia/commons/c/ce/VfL_Wolfsburg_Logo.svg',
    'Borussia Monchengladbach': 'https://upload.wikimedia.org/wikipedia/commons/8/81/Borussia_M%C3%B6nchengladbach_logo.svg',
    'Bochum': 'https://upload.wikimedia.org/wikipedia/commons/7/72/VfL_Bochum_logo.svg',
    'Union Berlin': 'https://upload.wikimedia.org/wikipedia/commons/4/44/1._FC_Union_Berlin_Logo.svg',
    'Mainz 05': 'https://upload.wikimedia.org/wikipedia/commons/9/9e/FSV_Mainz_05_Logo.svg',
    'FC Koln': 'https://upload.wikimedia.org/wikipedia/en/5/53/FC_Cologne_logo.svg',
    'Darmstadt': 'https://upload.wikimedia.org/wikipedia/en/8/87/SV_Darmstadt_98_Logo.svg',

    # Serie A
    'Inter Milan': 'https://upload.wikimedia.org/wikipedia/commons/0/05/FC_Internazionale_Milano_2021.svg',
    'AC Milan': 'https://upload.wikimedia.org/wikipedia/commons/d/d0/Logo_of_AC_Milan.svg',
    'Juventus': 'https://upload.wikimedia.org/wikipedia/commons/b/bc/Juventus_FC_2017_icon_%28black%29.svg',
    'Bologna': 'https://upload.wikimedia.org/wikipedia/en/5/5b/Bologna_F.C._1909_logo.svg',
    'AS Roma': 'https://upload.wikimedia.org/wikipedia/en/f/f7/AS_Roma_logo_%282017%29.svg',
    'Atalanta': 'https://upload.wikimedia.org/wikipedia/en/6/66/AtalantaBC.svg',
    'Lazio': 'https://upload.wikimedia.org/wikipedia/en/c/ce/S.S._Lazio_badge.svg',
    'Fiorentina': 'https://upload.wikimedia.org/wikipedia/en/b/ba/ACF_Fiorentina_2_logo.svg',
    'Torino': 'https://upload.wikimedia.org/wikipedia/en/2/2e/Torino_FC_Logo.svg',
    'Napoli': 'https://upload.wikimedia.org/wikipedia/commons/2/2d/SSC_Napoli_End_of_Season_Logo.svg',
    
    # Ligue 1
    'Paris Saint-Germain': 'https://upload.wikimedia.org/wikipedia/en/a/a7/Paris_Saint-Germain_F.C..svg',
    'Monaco': 'https://upload.wikimedia.org/wikipedia/en/b/ba/AS_Monaco_FC.svg',
    'Brest': 'https://upload.wikimedia.org/wikipedia/en/0/05/Stade_Brestois_29_logo.svg',
    'Lille': 'https://upload.wikimedia.org/wikipedia/en/6/6f/LOSC_Lille_Logo.svg',
    'Nice': 'https://upload.wikimedia.org/wikipedia/en/2/28/OGC_Nice_logo.svg',
    'Lens': 'https://upload.wikimedia.org/wikipedia/en/c/cc/RC_Lens_logo.svg',
    'Marseille': 'https://upload.wikimedia.org/wikipedia/commons/d/d8/Olympique_Marseille_logo.svg',
    'Rennes': 'https://upload.wikimedia.org/wikipedia/en/9/9e/Stade_Rennais_FC.svg',
    'Reims': 'https://upload.wikimedia.org/wikipedia/en/c/cb/Stade_de_Reims_Logo.svg',
    'Lyon': 'https://upload.wikimedia.org/wikipedia/en/c/c6/Olympique_Lyonnais.svg',

    # IPL (Cricket)
    'Chennai Super Kings': 'https://upload.wikimedia.org/wikipedia/en/thumb/2/2b/Chennai_Super_Kings_Logo.svg/1200px-Chennai_Super_Kings_Logo.svg.png',
    'Mumbai Indians': 'https://upload.wikimedia.org/wikipedia/en/thumb/c/cd/Mumbai_Indians_Logo.svg/1200px-Mumbai_Indians_Logo.svg.png',
    'Royal Challengers Bengaluru': 'https://upload.wikimedia.org/wikipedia/en/thumb/2/2a/Royal_Challengers_Bangalore_2020.svg/1200px-Royal_Challengers_Bangalore_2020.svg.png',
    'Kolkata Knight Riders': 'https://upload.wikimedia.org/wikipedia/en/thumb/4/4c/Kolkata_Knight_Riders_Logo.svg/1200px-Kolkata_Knight_Riders_Logo.svg.png',
    'Sunrisers Hyderabad': 'https://upload.wikimedia.org/wikipedia/en/thumb/8/81/Sunrisers_Hyderabad.svg/1200px-Sunrisers_Hyderabad.svg.png',
    'Rajasthan Royals': 'https://upload.wikimedia.org/wikipedia/en/thumb/6/60/Rajasthan_Royals_Logo.svg/1200px-Rajasthan_Royals_Logo.svg.png',
    'Gujarat Titans': 'https://upload.wikimedia.org/wikipedia/en/thumb/0/09/Gujarat_Titans_Logo.svg/1200px-Gujarat_Titans_Logo.svg.png',
    'Lucknow Super Giants': 'https://upload.wikimedia.org/wikipedia/en/thumb/a/a9/Lucknow_Super_Giants_IPL_Logo.svg/1200px-Lucknow_Super_Giants_IPL_Logo.svg.png',
    'Delhi Capitals': 'https://upload.wikimedia.org/wikipedia/en/thumb/2/2f/Delhi_Capitals_Logo.svg/1200px-Delhi_Capitals_Logo.svg.png',
    'Punjab Kings': 'https://upload.wikimedia.org/wikipedia/en/thumb/d/d4/Punjab_Kings_Logo.svg/1200px-Punjab_Kings_Logo.svg.png'
}

DATA = {
    "leagues": [
        {
            "name": "English Premier League",
            "sport": "Football",
            "teams": [
                {"name": "Arsenal", "city": "London", "venue": "Emirates Stadium"},
                {"name": "Aston Villa", "city": "Birmingham", "venue": "Villa Park"},
                {"name": "Bournemouth", "city": "Bournemouth", "venue": "Vitality Stadium"},
                {"name": "Brentford", "city": "London", "venue": "Gtech Community Stadium"},
                {"name": "Brighton", "city": "Brighton", "venue": "Amex Stadium"},
                {"name": "Burnley", "city": "Burnley", "venue": "Turf Moor"},
                {"name": "Chelsea", "city": "London", "venue": "Stamford Bridge"},
                {"name": "Crystal Palace", "city": "London", "venue": "Selhurst Park"},
                {"name": "Everton", "city": "Liverpool", "venue": "Goodison Park"},
                {"name": "Fulham", "city": "London", "venue": "Craven Cottage"},
                {"name": "Liverpool", "city": "Liverpool", "venue": "Anfield"},
                {"name": "Luton Town", "city": "Luton", "venue": "Kenilworth Road"},
                {"name": "Manchester City", "city": "Manchester", "venue": "Etihad Stadium"},
                {"name": "Manchester United", "city": "Manchester", "venue": "Old Trafford"},
                {"name": "Newcastle United", "city": "Newcastle", "venue": "St James' Park"},
                {"name": "Nottingham Forest", "city": "Nottingham", "venue": "City Ground"},
                {"name": "Sheffield United", "city": "Sheffield", "venue": "Bramall Lane"},
                {"name": "Tottenham Hotspur", "city": "London", "venue": "Tottenham Hotspur Stadium"},
                {"name": "West Ham United", "city": "London", "venue": "London Stadium"},
                {"name": "Wolverhampton Wanderers", "city": "Wolverhampton", "venue": "Molineux Stadium"}
            ]
        },
        {
            "name": "Spanish La Liga",
            "sport": "Football",
            "teams": [
                {"name": "Real Madrid", "city": "Madrid", "venue": "Santiago Bernabéu"},
                {"name": "Barcelona", "city": "Barcelona", "venue": "Camp Nou"},
                {"name": "Atletico Madrid", "city": "Madrid", "venue": "Wanda Metropolitano"},
                {"name": "Girona", "city": "Girona", "venue": "Montilivi"},
                {"name": "Athletic Bilbao", "city": "Bilbao", "venue": "San Mamés"},
                {"name": "Real Sociedad", "city": "San Sebastián", "venue": "Reale Arena"},
                {"name": "Real Betis", "city": "Seville", "venue": "Benito Villamarín"},
                {"name": "Valencia", "city": "Valencia", "venue": "Mestalla"},
                {"name": "Villarreal", "city": "Villarreal", "venue": "Estadio de la Cerámica"},
                {"name": "Getafe", "city": "Getafe", "venue": "Coliseum Alfonso Pérez"},
                {"name": "Osasuna", "city": "Pamplona", "venue": "El Sadar"},
                {"name": "Sevilla", "city": "Seville", "venue": "Ramón Sánchez Pizjuán"},
                {"name": "Las Palmas", "city": "Las Palmas", "venue": "Estadio Gran Canaria"},
                {"name": "Alaves", "city": "Vitoria-Gasteiz", "venue": "Mendizorrotza"},
                {"name": "Rayo Vallecano", "city": "Madrid", "venue": "Vallecas"},
                {"name": "Mallorca", "city": "Palma", "venue": "Son Moix"},
                {"name": "Celta Vigo", "city": "Vigo", "venue": "Balaídos"},
                {"name": "Cadiz", "city": "Cádiz", "venue": "Nuevo Mirandilla"},
                {"name": "Granada", "city": "Granada", "venue": "Nuevo Los Cármenes"},
                {"name": "Almeria", "city": "Almería", "venue": "Power Horse Stadium"}
            ]
        },
        {
            "name": "German Bundesliga",
            "sport": "Football",
            "teams": [
                {"name": "Bayer Leverkusen", "city": "Leverkusen", "venue": "BayArena"},
                {"name": "Bayern Munich", "city": "Munich", "venue": "Allianz Arena"},
                {"name": "VfB Stuttgart", "city": "Stuttgart", "venue": "MHPArena"},
                {"name": "RB Leipzig", "city": "Leipzig", "venue": "Red Bull Arena"},
                {"name": "Borussia Dortmund", "city": "Dortmund", "venue": "Signal Iduna Park"},
                {"name": "Eintracht Frankfurt", "city": "Frankfurt", "venue": "Deutsche Bank Park"},
                {"name": "SC Freiburg", "city": "Freiburg", "venue": "Europa-Park Stadion"},
                {"name": "Hoffenheim", "city": "Sinsheim", "venue": "PreZero Arena"},
                {"name": "Heidenheim", "city": "Heidenheim", "venue": "Voith-Arena"},
                {"name": "Werder Bremen", "city": "Bremen", "venue": "Weserstadion"},
                {"name": "Augsburg", "city": "Augsburg", "venue": "WWK Arena"},
                {"name": "Wolfsburg", "city": "Wolfsburg", "venue": "Volkswagen Arena"},
                {"name": "Borussia Monchengladbach", "city": "Monchengladbach", "venue": "Borussia-Park"},
                {"name": "Bochum", "city": "Bochum", "venue": "Vonovia Ruhrstadion"},
                {"name": "Union Berlin", "city": "Berlin", "venue": "Stadion An der Alten Försterei"},
                {"name": "Mainz 05", "city": "Mainz", "venue": "Mewa Arena"},
                {"name": "FC Koln", "city": "Cologne", "venue": "RheinEnergieStadion"},
                {"name": "Darmstadt", "city": "Darmstadt", "venue": "Merck-Stadion am Böllenfalltor"}
            ]
        },
        {
            "name": "Italian Serie A",
            "sport": "Football",
            "teams": [
                {"name": "Inter Milan", "city": "Milan", "venue": "San Siro"},
                {"name": "AC Milan", "city": "Milan", "venue": "San Siro"},
                {"name": "Juventus", "city": "Turin", "venue": "Allianz Stadium"},
                {"name": "Bologna", "city": "Bologna", "venue": "Stadio Renato Dall'Ara"},
                {"name": "AS Roma", "city": "Rome", "venue": "Stadio Olimpico"},
                {"name": "Atalanta", "city": "Bergamo", "venue": "Gewiss Stadium"},
                {"name": "Lazio", "city": "Rome", "venue": "Stadio Olimpico"},
                {"name": "Fiorentina", "city": "Florence", "venue": "Stadio Artemio Franchi"},
                {"name": "Torino", "city": "Turin", "venue": "Stadio Olimpico Grande Torino"},
                {"name": "Napoli", "city": "Naples", "venue": "Stadio Diego Armando Maradona"}
            ]
        },
        {
            "name": "French Ligue 1",
            "sport": "Football",
            "teams": [
                {"name": "Paris Saint-Germain", "city": "Paris", "venue": "Parc des Princes"},
                {"name": "Monaco", "city": "Monaco", "venue": "Stade Louis II"},
                {"name": "Brest", "city": "Brest", "venue": "Stade Francis-Le Blé"},
                {"name": "Lille", "city": "Lille", "venue": "Stade Pierre-Mauroy"},
                {"name": "Nice", "city": "Nice", "venue": "Allianz Riviera"},
                {"name": "Lens", "city": "Lens", "venue": "Stade Bollaert-Delelis"},
                {"name": "Marseille", "city": "Marseille", "venue": "Stade Vélodrome"},
                {"name": "Rennes", "city": "Rennes", "venue": "Roazhon Park"},
                {"name": "Reims", "city": "Reims", "venue": "Stade Auguste-Delaune"},
                {"name": "Lyon", "city": "Lyon", "venue": "Groupama Stadium"}
            ]
        },
    ]
}

# Inject logos
for league in DATA['leagues']:
    for team in league['teams']:
        team['logo_url'] = LOGOS.get(team['name'], '')
        # Add capacity randomizer just for structure
        team['capacity'] = 30000 

final_path = os.path.join(os.path.dirname(__file__), 'app', 'management', 'commands', 'data', 'football_data.json')
os.makedirs(os.path.dirname(final_path), exist_ok=True)

with open(final_path, 'w', encoding='utf-8') as f:
    json.dump(DATA, f, indent=2)

print(f"Generated {final_path}")
