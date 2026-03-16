import pandas as pd
import datetime
import os
import re

# --- Configuration ---
INVITATIONS_FILE = "Linkedin Data/Invitations.csv"
CONNECTIONS_FILE = "Linkedin Data/Connections.csv"
OUTPUT_FILE = "NETWORK_DEPTH_REPORT.md"

def load_csv(filepath, skip_check=True):
    try:
        if not os.path.exists(filepath):
            print(f"Warning: {filepath} not found. Skipping.")
            return pd.DataFrame()

        # Try determining header row for Connections.csv (e.g. usually on line 3 or 4)
        if "Connections.csv" in filepath:
             with open(filepath, 'r') as f:
                 lines = f.readlines()
                 for i, line in enumerate(lines[:10]):
                     if "First Name" in line:
                         return pd.read_csv(filepath, skiprows=i)
        
        return pd.read_csv(filepath)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return pd.DataFrame()

def analyze_inbound(invitations_df):
    """
    Scans for INCOMING invitations with messages.
    Returns a list of dicts: {name, date, message, url, time_ago}
    """
    if invitations_df.empty:
        return []
    
    # Filter for Incoming and Non-Empty Messages
    # Note: Column names might vary slightly, treating carefully
    df = invitations_df.copy()
    df.columns = [c.strip() for c in df.columns]
    
    # Ensure columns exist
    if 'Direction' not in df.columns or 'Message' not in df.columns:
        print("Columns 'Direction' or 'Message' missing in Invitations.csv")
        return []

    inbound = df[
        (df['Direction'] == 'INCOMING') & 
        (df['Message'].notna()) & 
        (df['Message'].astype(str).str.strip() != "")
    ]
    
    results = []
    for _, row in inbound.iterrows():
        # Parse date
        try:
            sent_at = row.get('Sent At', '')
            # Handle "1/28/26, 4:03 PM" format
            date_obj = pd.to_datetime(sent_at, format="%m/%d/%y, %I:%M %p", errors='coerce')
            if pd.isna(date_obj):
                 # Fallback for simple date
                 date_obj = pd.to_datetime(sent_at, errors='coerce')
                 
            date_str = date_obj.strftime('%Y-%m-%d') if pd.notna(date_obj) else str(sent_at)
            days_ago = (datetime.datetime.now() - date_obj).days if pd.notna(date_obj) else 999
            
        except:
            date_str = str(row.get('Sent At', ''))
            days_ago = 999

        full_name = str(row.get('From', 'Unknown'))
        
        results.append({
            'name': full_name,
            'date': date_str,
            'days_ago': days_ago,
            'message': str(row.get('Message', '')),
            'url': str(row.get('inviterProfileUrl', ''))
        })

    # Sort by recent
    results.sort(key=lambda x: x['days_ago'])
    return results

def analyze_abm(connections_df):
    """
    Groups connections by company to find ABM clusters.
    Returns list of dicts: {company, count, contacts: []}
    """
    if connections_df.empty:
        return []

    df = connections_df.copy()
    
    # Clean company names
    if 'Company' not in df.columns:
        return []

    # Filter out empty or generic companies
    df = df[df['Company'].notna()]
    df = df[~df['Company'].str.lower().isin(['self-employed', 'freelance', 'stealth mode', 'confidential'])]

    # Group
    company_counts = df['Company'].value_counts()
    
    # Filter for companies with >= 3 connections
    target_companies = company_counts[company_counts >= 3].index.tolist()
    
    clusters = []
    for company in target_companies:
        employees = df[df['Company'] == company]
        contacts = []
        for _, row in employees.iterrows():
            contacts.append({
                'name': f"{row.get('First Name', '')} {row.get('Last Name', '')}",
                'title': row.get('Position', ''),
                'url': row.get('URL', '')
            })
            
        clusters.append({
            'company': company,
            'count': len(contacts),
            'contacts': contacts
        })
        
    # Sort by network density (count)
    clusters.sort(key=lambda x: x['count'], reverse=True)
    return clusters

def generate_report(inbound_leads, abm_clusters):
    with open(OUTPUT_FILE, 'w') as f:
        f.write("# 📡 Network Depth Report: Inbound & ABM\n")
        f.write(f"**Date:** {datetime.date.today()}\n\n")
        
        # Section 1: Inbound Sweeper
        f.write(f"## 📥 The Inbound Sweeper ({len(inbound_leads)} Unreplied Invites)\n")
        f.write("> **Strategy:** These people messaged you FIRST. They are the warmest leads in your stack.\n\n")
        
        if not inbound_leads:
            f.write("*No pending inbound messages found.*\n")
        
        for lead in inbound_leads:
            # Highlight recent ones
            icon = "🔥" if lead['days_ago'] < 30 else "📩"
            
            f.write(f"### {icon} {lead['name']} ({lead['date']})\n")
            f.write(f"**Message:** \"{lead['message']}\"\n")
            f.write(f"**Action:** [Reply on LinkedIn]({lead['url']})\n")
            f.write(f"> **Draft Reply:** \"Hey {lead['name'].split()[0]}, thanks for the note! Apologies strictly for the delay here—I was heads down on a project. Regarding your point on '{lead['message'][:20]}...', I'd love to chat. Are you free Thurs?\"\n\n")
            f.write("---\n")

        # Section 2: ABM Radar
        f.write(f"\n## 🏢 The ABM Radar ({len(abm_clusters)} Company Clusters)\n")
        f.write("> **Strategy:** You have multiple contacts at these companies. Treat them as an Account, not individuals.\n\n")
        
        if not abm_clusters:
            f.write("*No company clusters (>2 connections) found.*\n")

        for cluster in abm_clusters:
            f.write(f"### 🏰 {cluster['company']} ({cluster['count']} Connections)\n")
            
            # List contacts
            for contact in cluster['contacts']:
                f.write(f"*   **{contact['name']}** - {contact['title']} ([View]({contact['url']}))\n")
                
            f.write(f"\n> **ABM Play:** \"Hey team, I noticed I'm connected with a few of you at {cluster['company']}. We've been doing deep work on [Topic] that seems relevant to your initiatives. Open to a group lunch and learn?\"\n")
            f.write("---\n")

    print(f"Report generated: {OUTPUT_FILE}")

def main():
    print("Loading data...")
    invites = load_csv(INVITATIONS_FILE)
    conns = load_csv(CONNECTIONS_FILE)
    
    # 1. Analyze Inbound
    print("Scanning Inbox...")
    inbound = analyze_inbound(invites)
    print(f"Found {len(inbound)} inbound opportunities.")
    
    # 2. Analyze ABM
    print("Clustering Network...")
    clusters = analyze_abm(conns)
    print(f"Found {len(clusters)} company clusters.")
    
    # 3. Report
    generate_report(inbound, clusters)

if __name__ == "__main__":
    main()
