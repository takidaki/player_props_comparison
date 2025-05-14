import os
import json
import requests
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variables
API_KEY = os.getenv('API_KEY')
SPORT = 'basketball_nba'
REGIONS = 'us,eu'  # Added 'eu' region
MARKETS = ['player_points', 'player_rebounds', 'player_assists']
ODDS_FORMAT = 'decimal'
DATE_FORMAT = 'iso'

# Create output directory if it doesn't exist
output_dir = 'odds_data'
os.makedirs(output_dir, exist_ok=True)

# Get current date for filename
current_date = datetime.now().strftime('%Y-%m-%d')

# Step 1: Fetch events
print(f"Fetching events for {SPORT}...")
events_response = requests.get(
    f'https://api.the-odds-api.com/v4/sports/{SPORT}/events',
    params={
        'api_key': API_KEY,
    }
)

if events_response.status_code != 200:
    print(f"Error fetching events: {events_response.status_code}")
    print(events_response.text)
    exit()

events = events_response.json()
print(f"Successfully fetched {len(events)} events")

# Save events data
events_file = f"{output_dir}/{SPORT}_events_{current_date}.json"
with open(events_file, 'w') as f:
    json.dump(events, f, indent=2)
print(f"Events data saved to {events_file}")

# Step 2: Fetch odds for each event
for event in events:
    event_id = event['id']
    event_name = event['home_team'] + " vs " + event['away_team']
    # Create safe filename by replacing spaces and special chars
    safe_event_name = event_name.replace(" ", "_").replace("/", "_")
    
    print(f"\nProcessing event: {event_name} (ID: {event_id})")
    
    # Make separate requests for each market
    for market in MARKETS:
        print(f"  Fetching {market} odds...")
        
        odds_response = requests.get(
            f'https://api.the-odds-api.com/v4/sports/{SPORT}/events/{event_id}/odds',
            params={
                'api_key': API_KEY,
                'regions': REGIONS,
                'markets': market,
                'oddsFormat': ODDS_FORMAT,
                'dateFormat': DATE_FORMAT,
            }
        )

        if odds_response.status_code == 200:
            odds_data = odds_response.json()
            print(f"  Successfully fetched {market} data")
            print(f"  Bookmakers available: {len(odds_data.get('bookmakers', []))}")
            
            # Save odds data to JSON file
            odds_file = f"{output_dir}/{safe_event_name}_{market}_{current_date}.json"
            with open(odds_file, 'w') as f:
                json.dump(odds_data, f, indent=2)
            print(f"  Odds data saved to {odds_file}")
        else:
            print(f"  Error fetching {market} odds: {odds_response.status_code}")
            print(f"  {odds_response.text}")

print("\nAll data fetching and saving complete!")


