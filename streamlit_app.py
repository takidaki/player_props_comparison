import streamlit as st
import os
import json
import glob
from datetime import datetime, timedelta
import re

# Directory where odds data is stored
ODDS_DATA_DIR = 'odds_data'

def main():
    st.set_page_config(page_title="NBA Player Odds Comparison", layout="wide")
    st.title("NBA Player Odds Comparison")
    st.caption("Data refreshes every 5 minutes")
    
    # Get the most recent events file
    events_files = [f for f in os.listdir(ODDS_DATA_DIR) if f.startswith('basketball_nba_events_')]
    if not events_files:
        st.error("No events data found")
        return
    
    # Sort by date (newest first)
    events_files.sort(reverse=True)
    latest_events_file = os.path.join(ODDS_DATA_DIR, events_files[0])
    
    with open(latest_events_file, 'r') as f:
        events = json.load(f)
    
    # Get all odds files
    odds_files = [f for f in os.listdir(ODDS_DATA_DIR) if any(market in f for market in ['player_points', 'player_rebounds', 'player_assists'])]
    
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

# Your existing helper functions
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

def get_odds_changes():
    """Get changes in odds and lines between the two most recent data fetches"""
    # Your existing get_odds_changes function
    # ...

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

if __name__ == "__main__":
    main()