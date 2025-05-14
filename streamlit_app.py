import streamlit as st
import os
import json
import requests
import time
from datetime import datetime, timedelta
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv('API_KEY')
SPORT = 'basketball_nba'
REGIONS = 'us,eu'
MARKETS = ['player_points', 'player_rebounds', 'player_assists']
ODDS_FORMAT = 'decimal'
DATE_FORMAT = 'iso'
ODDS_DATA_DIR = 'odds_data'

# Create directory if it doesn't exist
os.makedirs(ODDS_DATA_DIR, exist_ok=True)

# Function to fetch odds data
def fetch_odds_data():
    """Fetch odds data from the API and save to files"""
    if not API_KEY:
        st.error("API key not found. Please set the API_KEY environment variable.")
        return False
    
    # Get current date for filename
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Step 1: Fetch events
    st.info(f"Fetching events for {SPORT}...")
    events_response = requests.get(
        f'https://api.the-odds-api.com/v4/sports/{SPORT}/events',
        params={
            'api_key': API_KEY,
        }
    )
    
    if events_response.status_code != 200:
        st.error(f"Error fetching events: {events_response.status_code}")
        st.write(events_response.text)
        return False
    
    events = events_response.json()
    st.success(f"Successfully fetched {len(events)} events")
    
    # Save events data
    events_file = f"{ODDS_DATA_DIR}/{SPORT}_events_{current_date}.json"
    with open(events_file, 'w') as f:
        json.dump(events, f, indent=2)
    
    # Step 2: Fetch odds for each event and market
    for event in events:
        event_id = event['id']
        home_team = event['home_team']
        away_team = event['away_team']
        
        # Create a safe filename
        safe_event_name = f"{home_team}_vs_{away_team}".replace(' ', '_')
        
        for market in MARKETS:
            st.info(f"Fetching {market} odds for {home_team} vs {away_team}...")
            
            odds_response = requests.get(
                f'https://api.the-odds-api.com/v4/sports/{SPORT}/events/{event_id}/odds',
                params={
                    'api_key': API_KEY,
                    'regions': REGIONS,
                    'markets': market,
                    'oddsFormat': ODDS_FORMAT,
                    'dateFormat': DATE_FORMAT
                }
            )
            
            if odds_response.status_code == 200:
                odds_data = odds_response.json()
                st.success(f"Successfully fetched {market} data")
                
                # Save odds data to JSON file
                odds_file = f"{ODDS_DATA_DIR}/{safe_event_name}_{market}_{current_date}.json"
                with open(odds_file, 'w') as f:
                    json.dump(odds_data, f, indent=2)
            else:
                st.error(f"Error fetching {market} odds: {odds_response.status_code}")
                st.write(odds_response.text)
    
    return True

def process_market_data(data_list):
    """Process data from multiple events into a unified player-centric view"""
    players_data = {}
    
    for event_data in data_list:
        event_info = {
            'id': event_data['id'],
            'home_team': event_data['home_team'],
            'away_team': event_data['away_team'],
            'commence_time': event_data['commence_time']
        }
        
        # Extract all bookmakers and their odds for each player
        for bookmaker in event_data.get('bookmakers', []):
            bookmaker_name = bookmaker['title']
            
            for market in bookmaker.get('markets', []):
                for outcome in market.get('outcomes', []):
                    player_name = outcome.get('description', '')
                    if not player_name:
                        continue
                    
                    if player_name not in players_data:
                        players_data[player_name] = {
                            'events': {},
                            'bookmakers': set()
                        }
                    
                    event_id = event_data['id']
                    if event_id not in players_data[player_name]['events']:
                        players_data[player_name]['events'][event_id] = {
                            'info': event_info,
                            'bookmakers': {}
                        }
                    
                    if bookmaker_name not in players_data[player_name]['events'][event_id]['bookmakers']:
                        players_data[player_name]['events'][event_id]['bookmakers'][bookmaker_name] = {
                            'line': None,
                            'over': None,
                            'under': None,
                            'last_update': market['last_update']
                        }
                    
                    players_data[player_name]['bookmakers'].add(bookmaker_name)
                    
                    if outcome['name'] == 'Over':
                        players_data[player_name]['events'][event_id]['bookmakers'][bookmaker_name]['line'] = outcome['point']
                        players_data[player_name]['events'][event_id]['bookmakers'][bookmaker_name]['over'] = outcome['price']
                    elif outcome['name'] == 'Under':
                        players_data[player_name]['events'][event_id]['bookmakers'][bookmaker_name]['under'] = outcome['price']
    
    # Convert bookmakers set to list for each player
    for player in players_data:
        players_data[player]['bookmakers'] = sorted(list(players_data[player]['bookmakers']))
    
    return players_data

def get_all_events(processed_data):
    """Extract all unique events from the processed data"""
    events = set()
    
    # Loop through all markets and players to collect unique events
    for market_data in processed_data.values():
        for player_data in market_data.values():
            for event_id, event_data in player_data['events'].items():
                event_name = f"{event_data['info']['home_team']} vs {event_data['info']['away_team']}"
                events.add((event_id, event_name))
    
    # Convert to list of tuples and sort by event name
    return sorted(list(events), key=lambda x: x[1])

def get_odds_changes():
    """Get changes in odds and lines between the two most recent data fetches"""
    changes = {
        'player_points': [],
        'player_rebounds': [],
        'player_assists': []
    }
    
    # Get all odds files
    for market in MARKETS:
        files = [f for f in os.listdir(ODDS_DATA_DIR) if market in f]
        if len(files) < 2:
            continue
            
        # Group files by event
        events_files = {}
        for file in files:
            match = re.search(r'(.+)_' + market + r'_(.+)\.json', file)
            if match:
                event_name = match.group(1)
                date = match.group(2)
                
                if event_name not in events_files:
                    events_files[event_name] = []
                
                events_files[event_name].append((date, file))
        
        # For each event, compare the two most recent files
        for event_name, event_files in events_files.items():
            if len(event_files) < 2:
                continue
                
            # Sort by date (newest first)
            event_files.sort(reverse=True)
            
            newest_file = os.path.join(ODDS_DATA_DIR, event_files[0][1])
            second_newest_file = os.path.join(ODDS_DATA_DIR, event_files[1][1])
            
            with open(newest_file, 'r') as f1, open(second_newest_file, 'r') as f2:
                newest_data = json.load(f1)
                older_data = json.load(f2)
                
                # Extract event info
                event_info = {
                    'id': newest_data['id'],
                    'home_team': newest_data['home_team'],
                    'away_team': newest_data['away_team']
                }
                
                # Compare bookmakers data
                for bookmaker in newest_data.get('bookmakers', []):
                    bookmaker_name = bookmaker['title']
                    
                    # Find the same bookmaker in the older data
                    older_bookmaker = None
                    for bm in older_data.get('bookmakers', []):
                        if bm['title'] == bookmaker_name:
                            older_bookmaker = bm
                            break
                    
                    if not older_bookmaker:
                        continue
                    
                    # Compare markets
                    for market_data in bookmaker.get('markets', []):
                        market_key = market_data['key']
                        
                        # Find the same market in the older data
                        older_market = None
                        for m in older_bookmaker.get('markets', []):
                            if m['key'] == market_key:
                                older_market = m
                                break
                        
                        if not older_market:
                            continue
                        
                        # Compare outcomes
                        for outcome in market_data.get('outcomes', []):
                            player_name = outcome.get('description', '')
                            if not player_name:
                                continue
                                
                            # Find the same outcome in the older data
                            older_outcome = None
                            for o in older_market.get('outcomes', []):
                                if o.get('description') == player_name and o.get('name') == outcome.get('name'):
                                    older_outcome = o
                                    break
                            
                            if not older_outcome:
                                continue
                            
                            # Check if there's a change in point or price
                            changes_detected = []
                            
                            # Check point (line) change
                            if 'point' in outcome and 'point' in older_outcome:
                                new_point = outcome['point']
                                old_point = older_outcome['point']
                                
                                if new_point != old_point:
                                    changes_detected.append({
                                        'type': 'line',
                                        'previous': old_point,
                                        'current': new_point,
                                        'difference': new_point - old_point
                                    })
                            
                            # Check price (odds) change
                            if 'price' in outcome and 'price' in older_outcome:
                                new_price = outcome['price']
                                old_price = older_outcome['price']
                                
                                if new_price != old_price:
                                    changes_detected.append({
                                        'type': 'odds',
                                        'previous': old_price,
                                        'current': new_price,
                                        'difference': new_price - old_price
                                    })
                            
                            # If changes were detected, add to the changes list
                            if changes_detected:
                                changes[market_key].append({
                                    'player': player_name,
                                    'bookmaker': bookmaker_name,
                                    'bet_type': outcome.get('name', ''),
                                    'event': event_info,
                                    'latest_update': market_data.get('last_update'),
                                    'changes': changes_detected
                                })
    
    return changes

def display_market_data(market_data, selected_event):
    for player_name, player_data in market_data.items():
        for event_id, event_data in player_data['events'].items():
            if not selected_event or selected_event == event_id:
                with st.expander(f"{player_name} - {event_data['info']['home_team']} vs {event_data['info']['away_team']}"):
                    st.write(f"Game Time: {format_date(event_data['info']['commence_time'])}")
                    
                    # Create a table for the odds
                    data = []
                    for bookmaker_name, odds in event_data['bookmakers'].items():
                        data.append([
                            bookmaker_name,
                            odds.get('line', 'N/A'),
                            odds.get('over', 'N/A'),
                            odds.get('under', 'N/A')
                        ])
                    
                    st.table({
                        "Bookmaker": [row[0] for row in data],
                        "Line": [row[1] for row in data],
                        "Over": [row[2] for row in data],
                        "Under": [row[3] for row in data]
                    })

def display_changes(changes, selected_event):
    if not changes:
        st.write("No recent changes")
        return
    
    for change in changes:
        if not selected_event or selected_event == change.get('event', {}).get('id'):
            with st.expander(f"{change.get('player')} - {change.get('event', {}).get('home_team')} vs {change.get('event', {}).get('away_team')}"):
                st.write(f"Bookmaker: {change.get('bookmaker')}")
                st.write(f"Bet Type: {change.get('bet_type')}")
                st.write(f"Updated: {format_date(change.get('latest_update'))}")
                
                for item in change.get('changes', []):
                    if item.get('type') == 'line':
                        st.write(f"Line changed from {item.get('previous')} to {item.get('current')} ({format_change(item.get('difference'))})")
                    else:
                        st.write(f"Odds changed from {item.get('previous')} to {item.get('current')} ({format_change(item.get('difference'))})")

def format_date(date_str):
    if not date_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return date_str

def format_change(value):
    if value > 0:
        return f"+{value:.2f}"
    return f"{value:.2f}"

def main():
    st.set_page_config(page_title="NBA Player Odds Comparison", layout="wide")
    st.title("NBA Player Odds Comparison")
    
    # Add a refresh button
    col1, col2 = st.columns([4, 1])
    with col1:
        st.caption("Data refreshes every 5 minutes via GitHub Actions, or you can refresh manually")
    with col2:
        if st.button("Refresh Data Now"):
            with st.spinner("Fetching latest odds data..."):
                success = fetch_odds_data()
                if success:
                    st.success("Data refreshed successfully!")
                    time.sleep(1)  # Give user time to see the success message
                    st.experimental_rerun()  # Rerun the app to show new data
    
    # Create directory if it doesn't exist
    os.makedirs(ODDS_DATA_DIR, exist_ok=True)
    
    # Get the most recent events file
    events_files = [f for f in os.listdir(ODDS_DATA_DIR) if f.startswith('basketball_nba_events_')]
    if not events_files:
        st.warning("No events data found. Please click 'Refresh Data Now' to fetch the latest odds.")
        return
    
    # Sort by date (newest first)
    events_files.sort(reverse=True)
    latest_events_file = os.path.join(ODDS_DATA_DIR, events_files[0])
    
    with open(latest_events_file, 'r') as f:
        events = json.load(f)
    
    # Get all odds files
    odds_files = [f for f in os.listdir(ODDS_DATA_DIR) if any(market in f for market in MARKETS)]
    
    # Group files by market
    markets_data = {
        'player_points': [],
        'player_rebounds': [],
        'player_assists': []
    }
    
    # Load all odds data
    for file in odds_files:
        for market in markets_data.keys():
            if market in file:
                with open(os.path.join(ODDS_DATA_DIR, file), 'r') as f:
                    data = json.load(f)
                    markets_data[market].append(data)
    
    # Process data for each market to create a unified view
    processed_data = {}
    
    for market, data_list in markets_data.items():
        processed_data[market] = process_market_data(data_list)
    
    # Get odds changes
    changes_data = get_odds_changes()
    
    # Get all unique events for the filter dropdown
    all_events = get_all_events(processed_data)
    
    # Event filter
    event_options = ["All Events"] + [event_name for _, event_name in all_events]
    selected_event_name = st.selectbox("Filter by Event:", event_options)
    
    # Convert selected event name to event_id
    selected_event = ""
    if selected_event_name != "All Events":
        for event_id, event_name in all_events:
            if event_name == selected_event_name:
                selected_event = event_id
                break
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Points", "Rebounds", "Assists", "Recent Changes"])
    
    with tab1:
        st.header("Player Points")
        if processed_data.get('player_points'):
            display_market_data(processed_data['player_points'], selected_event)
        else:
            st.write("No player points data available")
    
    with tab2:
        st.header("Player Rebounds")
        if processed_data.get('player_rebounds'):
            display_market_data(processed_data['player_rebounds'], selected_event)
        else:
            st.write("No player rebounds data available")
    
    with tab3:
        st.header("Player Assists")
        if processed_data.get('player_assists'):
            display_market_data(processed_data['player_assists'], selected_event)
        else:
            st.write("No player assists data available")
    
    with tab4:
        st.header("Recent Odds Changes")
        changes_tab1, changes_tab2, changes_tab3 = st.tabs(["Points Changes", "Rebounds Changes", "Assists Changes"])
        
        with changes_tab1:
            display_changes(changes_data.get('player_points', []), selected_event)
        
        with changes_tab2:
            display_changes(changes_data.get('player_rebounds', []), selected_event)
        
        with changes_tab3:
            display_changes(changes_data.get('player_assists', []), selected_event)

if __name__ == "__main__":
    main()

