import pandas as pd
import datetime
from dateutil.parser import parse
import json
import os
import re

# --- Configuration & Weights ---
CONNECTIONS_FILE = "Linkedin Data/Connections.csv"
MESSAGES_FILE = "Linkedin Data/messages.csv"
ENDORSEMENTS_FILE = "Linkedin Data/Endorsement_Received_Info.csv"
RECOMMENDATIONS_FILE = "Linkedin Data/Recommendations_Received.csv"
OUTPUT_FILE = "ADVANCED_LEAD_REPORT.md"
CLAY_EXPORT_FILE = "high_intent_leads_for_clay.csv"
# Config path relative to this script
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '../lead_generator/config/products.json')

# Intent Scoring Weights
WEIGHTS = {
    'role_fit': 50,
    'advocacy_endorsement': 20,
    'advocacy_recommendation': 30,
    'warmth_recent': 15,
    'context_intent': 15
}

INTENT_KEYWORDS = [
    'price', 'pricing', 'cost', 'quote', 'help', 'consulting', 'audit', 
    'strategy', 'call', 'talk', 'services', 'rate', 'proposal', 'budget'
]

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
        if not os.path.exists(filepath):
            print(f"Warning: {filepath} not found. Skipping.")
            return pd.DataFrame()

        if skip_check:
             # Try determining header row for Connections.csv (e.g. usually on line 3 or 4)
             with open(filepath, 'r') as f:
                 lines = f.readlines()
                 for i, line in enumerate(lines[:10]):
                     if "First Name" in line:
                         return pd.read_csv(filepath, skiprows=i)
        return pd.read_csv(filepath)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return pd.DataFrame()

def normalize_name(first, last):
    if pd.isna(first) or pd.isna(last):
        return ""
    return f"{str(first).strip()} {str(last).strip()}".lower()

def get_advocacy_score(full_name_lower, endorsements_df, recommendations_df):
    score = 0
    badges = []
    
    # Check Endorsements
    if not endorsements_df.empty:
        # Endorsements file: Endorser First Name, Endorser Last Name, Endorsement Status
        matches = endorsements_df[
            (endorsements_df['Endorsement Status'] == 'ACCEPTED') &
            (endorsements_df['Endorser First Name'].fillna('').astype(str).str.strip().str.lower() + " " + 
             endorsements_df['Endorser Last Name'].fillna('').astype(str).str.strip().str.lower() == full_name_lower)
        ]
        if not matches.empty:
            score += WEIGHTS['advocacy_endorsement']
            badges.append("🏆 Endorser")

    # Check Recommendations
    if not recommendations_df.empty:
        # Recommendations file: First Name, Last Name, Status
        matches = recommendations_df[
            (recommendations_df['Status'] == 'VISIBLE') &
            (recommendations_df['First Name'].fillna('').astype(str).str.strip().str.lower() + " " + 
             recommendations_df['Last Name'].fillna('').astype(str).str.strip().str.lower() == full_name_lower)
        ]
        if not matches.empty:
            # Overwrite endorsement score if recommendation exists (usually implies endorsement too) 
            # or add cumulative? Strategy says +20 pts. Let's make Super Fan worth more.
            # If they did both, they get both points.
            score += WEIGHTS['advocacy_recommendation']
            badges.append("❤️ Super Fan")
            
    return score, badges

def analyze_interaction(full_name_lower, messages_df):
    score = 0
    badges = []
    last_interaction = None
    
    if messages_df.empty:
        return 0, [], None

    # Filter messages for this user (FROM or TO)
    # Using simple substring match on name might have false positives but is best heuristic without IDs
    # Normalizing full name for check is tricky in text fields. 
    # We will search for the name in FROM/TO columns.
    
    user_msgs = messages_df[
        (messages_df['FROM'].astype(str).str.lower().str.contains(full_name_lower, regex=False)) | 
        (messages_df['TO'].astype(str).str.lower().str.contains(full_name_lower, regex=False))
    ]
    
    if user_msgs.empty:
        return 0, [], None
        
    # 1. Recency
    try:
        user_msgs['DATE_OBJ'] = user_msgs['DATE'].apply(lambda x: parse(str(x)) if pd.notna(x) else None)
        latest_date = user_msgs['DATE_OBJ'].max()
        last_interaction = latest_date.strftime('%Y-%m-%d')
        
        days_diff = (datetime.datetime.now(datetime.timezone.utc) - latest_date).days
        if days_diff < 90:
            score += WEIGHTS['warmth_recent']
            badges.append("🔥 Recent (<90d)")
    except Exception as e:
        print(f"Date parse error: {e}")

    # 2. Context / Intent
    # Concatenate all content to search keywords
    all_text = " ".join(user_msgs['CONTENT'].fillna('').astype(str).tolist()).lower()
    
    found_keywords = [k for k in INTENT_KEYWORDS if k in all_text]
    if found_keywords:
        score += WEIGHTS['context_intent']
        badges.append(f"💬 Intent ({found_keywords[0]})")
        
    return score, badges, last_interaction

def get_segment(position):
    if pd.isna(position):
        return None, []
    
    pos_lower = str(position).lower()
    
    for seg_name, criteria in SEGMENTS.items():
        if any(neg.lower() in pos_lower for neg in criteria['negative_keywords']):
            continue
        if any(key.lower() in pos_lower for key in criteria['keywords']):
            return seg_name, criteria
            
    return None, []

def export_to_clay(leads):
    print("Generating Clay Export...")
    clay_data = []
    
    for lead in leads:
        # Construct Clay-friendly row
        # Split full name back if needed or use existing first_name
        # LinkedIn URL is crucial for Clay enrichment
        
        row = {
            'First Name': lead['first_name'],
            'Last Name': lead['name'].replace(lead['first_name'], '', 1).strip(),
            'Title': lead['position'],
            'Company': lead['company'],
            'LinkedIn Profile': lead.get('url', ''),
            'Obsidian Score': lead['score'],
            'Segment': lead['segment'],
            'Badges': ", ".join(lead['badges'])
        }
        clay_data.append(row)
        
    if not clay_data:
        print("No leads to export.")
        return

    df = pd.DataFrame(clay_data)
    # Reorder columns for usability
    target_cols = ['First Name', 'Last Name', 'Title', 'Company', 'LinkedIn Profile', 'Obsidian Score', 'Segment', 'Badges']
    # Ensure cols exist
    df = df.reindex(columns=target_cols)
    
    df.to_csv(CLAY_EXPORT_FILE, index=False)
    print(f"Clay Export saved to: {CLAY_EXPORT_FILE}")

def process_leads():
    print("Loading datasets...")
    conns = load_csv(CONNECTIONS_FILE, skip_check=True)
    msgs = load_csv(MESSAGES_FILE, skip_check=False)
    endorsements = load_csv(ENDORSEMENTS_FILE, skip_check=False)
    recommendations = load_csv(RECOMMENDATIONS_FILE, skip_check=False)
    
    if conns.empty:
        print("No connections found. Exiting.")
        return

    # Standardize Message Columns
    if not msgs.empty:
        msgs.columns = [c.strip() for c in msgs.columns]

    leads = []
    print(f"Scanning {len(conns)} connections against {len(msgs)} messages, {len(endorsements)} endorsements...")

    for i, row in conns.iterrows():
        first = str(row.get('First Name', ''))
        last = str(row.get('Last Name', ''))
        # Capture URL for Clay
        url = str(row.get('URL', ''))
        
        full_name_lower = normalize_name(first, last)
        full_name_display = f"{first} {last}".strip()
        position = row.get('Position', '')
        company = row.get('Company', '')
        
        # 1. Role Fit (Base filter)
        segment_name, segment_data = get_segment(position)
        if not segment_name:
            continue # Skip non-prospects to keep report clean
            
        base_score = WEIGHTS['role_fit']
        
        # 2. Advocacy
        advocacy_score, advocacy_badges = get_advocacy_score(full_name_lower, endorsements, recommendations)
        
        # 3. Interaction
        interaction_score, interaction_badges, last_date = analyze_interaction(full_name_lower, msgs)
        
        total_score = base_score + advocacy_score + interaction_score
        all_badges = advocacy_badges + interaction_badges
        
        leads.append({
            'name': full_name_display,
            'first_name': first,
            'position': position,
            'company': company,
            'url': url,
            'segment': segment_name,
            'pitch_hook': segment_data['pitch_hook'],
            'score': total_score,
            'badges': all_badges,
            'last_interaction': last_date
        })

    # Sort by Score (Desc) -> Then Segment
    leads.sort(key=lambda x: (-x['score'], x['segment']))
    
    # Generate Markdown Report
    with open(OUTPUT_FILE, 'w') as f:
        f.write("# 🚀 Advanced Lead Gen Report: The Obsidian Intent Score\n")
        f.write(f"**Date:** {datetime.date.today()} | **Leads Scored:** {len(leads)}\n\n")
        
        f.write("> **Scoring Model:**\n")
        f.write("> * **Role Fit:** 50pts\n")
        f.write("> * **Super Fan:** +30pts (Recommended) / +20pts (Endorsed)\n")
        f.write("> * **High Intent:** +15pts (Keywords in chat)\n")
        f.write("> * **Active:** +15pts (Chat < 90 days)\n\n")
        f.write("---\n")
        
        current_segment = None
        
        for lead in leads:
            if lead['segment'] != current_segment:
                current_segment = lead['segment']
                f.write(f"\n## 🎯 {current_segment}\n")
                f.write("---\n")
            
            # Badge display
            badge_str = " ".join([f"`{b}`" for b in lead['badges']]) if lead['badges'] else "`❄️ Cold`"
            score_emoji = "🟢" if lead['score'] >= 70 else "🟡" if lead['score'] >= 50 else "⚪"
            
            f.write(f"### {score_emoji} {lead['score']} pts | **{lead['name']}** {badge_str}\n")
            f.write(f"*{lead['position']} @ {lead['company']}*\n")
            
            # Contextual Outreach Draft
            draft = ""
            if "🏆 Endorser" in lead['badges'] or "❤️ Super Fan" in lead['badges']:
                draft = f"\"Hey {lead['first_name']}, thanks again for believing in my work (saw the endorsement!). We just launched a specialized {current_segment} pilot. Since you know my standard, I'd love your critique on it?\""
            elif "💬 Intent" in str(lead['badges']):
                draft = f"\"Hey {lead['first_name']}, following up on our last chat. We've productized that exact solution for {lead['company']}. Is this still a priority?\""
            elif lead['last_interaction'] and "Recent" in str(lead['badges']):
                draft = f"\"Hey {lead['first_name']}, great catching up recently. Forgot to mention—we're helping {lead['position']}s with {lead['pitch_hook'].split('.')[0].lower()}. thought of you.\""
            else:
                draft = f"\"Hey {lead['first_name']}, noticed you're leading things at {lead['company']}. {lead['pitch_hook']} Open to a quick insight?\""
                
            f.write(f"> **Draft:** {draft}\n\n")

    print(f"Report generated: {OUTPUT_FILE}")
    
    # Generate Clay CSV
    export_to_clay(leads)

if __name__ == "__main__":
    process_leads()
