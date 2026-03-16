import pandas as pd
import datetime
from dateutil.parser import parse
import re

import json
import os

# --- Configuration ---
CONNECTIONS_FILE = "Linkedin Data/Connections.csv"
MESSAGES_FILE = "Linkedin Data/messages.csv"
OUTPUT_FILE = "LEAD_GEN_REPORT.md"
CONFIG_FILE = "skills/lead_generator/config/products.json"

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)['segments']
    except FileNotFoundError:
        print(f"Config file not found at {CONFIG_FILE}. Using empty segments.")
        return {}
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

SEGMENTS = load_config()

def load_csv(filepath, skip_check=True):
    try:
        if skip_check:
             # Try determining header row for Connections.csv
             with open(filepath, 'r') as f:
                 lines = f.readlines()
                 for i, line in enumerate(lines[:10]):
                     if "First Name" in line:
                         return pd.read_csv(filepath, skiprows=i)
        return pd.read_csv(filepath)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return pd.DataFrame()

def load_data():
    print("Loading data...")
    connections = load_csv(CONNECTIONS_FILE)
    messages = load_csv(MESSAGES_FILE, skip_check=False)
    
    # Standardize column names
    connections.columns = [c.strip() for c in connections.columns]
    if not messages.empty:
        messages.columns = [c.strip() for c in messages.columns]
    
    return connections, messages

def calculate_warmth(name, messages_df):
    """
    Determines warmth score based on message history.
    Score: 
    3 (High/Hot): Interacted < 3 months ago
    2 (Medium/Warm): Interacted < 12 months ago
    1 (Low/Lukewarm): Interacted > 12 months ago
    0 (Cold): No interaction
    """
    if messages_df.empty:
        return 0, None

    # Filter messages involving this person
    # Message export uses "FROM" and "TO" which helps.
    # Connections usually match by Name (First Last)
    user_msgs = messages_df[
        (messages_df['FROM'].astype(str).str.contains(name, case=False, na=False)) | 
        (messages_df['TO'].astype(str).str.contains(name, case=False, na=False))
    ]
    
    if user_msgs.empty:
        return 0, None
        
    # Get latest date
    try:
        user_msgs['DATE_OBJ'] = user_msgs['DATE'].apply(lambda x: parse(str(x)) if pd.notna(x) else None)
        latest_date = user_msgs['DATE_OBJ'].max()
    except:
        return 0, None
        
    if not latest_date:
        return 0, None
        
    days_diff = (datetime.datetime.now(datetime.timezone.utc) - latest_date).days
    
    formatted_date = latest_date.strftime('%Y-%m-%d')
    
    if days_diff < 90:
        return 3, formatted_date # High
    elif days_diff < 365:
        return 2, formatted_date # Med
    else:
        return 1, formatted_date # Low

def get_segment(position):
    if pd.isna(position):
        return []
    
    pos_lower = str(position).lower()
    matched_segments = []
    
    for seg_name, criteria in SEGMENTS.items():
        # Check negative keywords first
        if any(neg.lower() in pos_lower for neg in criteria['negative_keywords']):
            continue
            
        # Check positive keywords
        if any(key.lower() in pos_lower for key in criteria['keywords']):
            matched_segments.append(seg_name)
            
    return matched_segments

def generate_report():
    conns, msgs = load_data()
    
    if conns.empty:
        print("No connections found.")
        return

    analysis_results = []
    
    print(f"Analyzing {len(conns)} connections against {len(msgs)} messages...")
    
    for i, row in conns.iterrows():
        first = str(row.get('First Name', ''))
        last = str(row.get('Last Name', ''))
        full_name = f"{first} {last}".strip()
        position = row.get('Position', '')
        company = row.get('Company', '')
        
        warmth_score, last_interaction = calculate_warmth(full_name, msgs)
        target_segments = get_segment(position)
        
        if target_segments:
            for segment in target_segments:
                analysis_results.append({
                    "name": full_name,
                    "first_name": first,
                    "position": position,
                    "company": company,
                    "segment": segment,
                    "warmth_score": warmth_score,
                    "last_interaction": last_interaction,
                    "connected_on": row.get('Connected On', '')
                })

    # Sort: Segment -> Warmth (Desc) -> Name
    analysis_results.sort(key=lambda x: (x['segment'], -x['warmth_score'], x['name']))
    
    with open(OUTPUT_FILE, 'w') as f:
        f.write("# Segmented Connection & Outreach Report\n\n")
        f.write(f"**Generated:** {datetime.date.today()}\n")
        f.write(f"**Total Leads Identified:** {len(analysis_results)}\n")
        f.write("\n---\n")
        
        current_segment = None
        current_warmth = None
        
        warmth_labels = {3: "🔥 High (Recent Interaction)", 2: "☀️ Medium (< 1 Year)", 1: "❄️ Low (> 1 Year)", 0: "🧊 Cold (No History)"}
        
        for lead in analysis_results:
            # Segment Header
            if lead['segment'] != current_segment:
                current_segment = lead['segment']
                seg_data = SEGMENTS[current_segment]
                f.write(f"\n# 🎯 Solution: {current_segment}\n")
                f.write(f"**Value Prop**: {seg_data['value_prop']}\n")
                f.write(f"**Ideal for**: {', '.join(seg_data['keywords'][:5])}...\n")
                f.write("---\n")
                current_warmth = None # Reset warmth for new segment
            
            # Warmth Sub-Header
            if lead['warmth_score'] != current_warmth:
                current_warmth = lead['warmth_score']
                f.write(f"\n### {warmth_labels[current_warmth]}\n")
            
            # Lead Details
            last_int_str = f"(Last: {lead['last_interaction']})" if lead['last_interaction'] else ""
            f.write(f"**{lead['name']}** | {lead['position']} @ {lead['company']} {last_int_str}\n")
            
            # Drafted Message
            pitch = SEGMENTS[lead['segment']]['pitch_hook'].format(company=lead['company'])
            
            if lead['warmth_score'] >= 2:
                # Warm Opening
                f.write(f"> **Draft (Warm)**: \"Hey {lead['first_name']}, good to reconnect. {pitch} Worth a look?\"\n")
            else:
                # Cold Opening (7-Step style)
                f.write(f"> **Draft (Cold)**: \"Hey {lead['first_name']}, noticed your role at {lead['company']}. {pitch} Open to a quick insight on this?\"\n")
            f.write("\n")

    print(f"Report Generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_report()
