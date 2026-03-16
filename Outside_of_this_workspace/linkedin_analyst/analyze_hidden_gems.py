import pandas as pd
import os
import datetime
import re

# --- Configuration ---
ENDORSEMENTS_GIVEN_FILE = "Linkedin Data/Endorsement_Given_Info.csv"
COMPANY_FOLLOWS_FILE = "Linkedin Data/Company Follows.csv"
CONNECTIONS_FILE = "Linkedin Data/Connections.csv"
LEARNING_FILE = "Linkedin Data/Learning.csv"
MEMBER_FOLLOWS_FILE = "Linkedin Data/Member_Follows.csv"
SEARCH_QUERIES_FILE = "Linkedin Data/SearchQueries.csv"
OUTPUT_FILE = "HIDDEN_GEMS_REPORT.md"

def load_csv(filepath, skip_lines=0):
    try:
        if not os.path.exists(filepath):
            return pd.DataFrame()
        return pd.read_csv(filepath, skiprows=skip_lines)
    except:
        return pd.DataFrame()

def analyze_social_debt(endorsements_given_df):
    if endorsements_given_df.empty: return []
    df = endorsements_given_df.copy()
    df.columns = [c.strip() for c in df.columns]
    if 'Endorsee Name' not in df.columns: return []
    
    results = []
    for _, row in df.iterrows():
        results.append({
            'name': str(row.get('Endorsee Name', 'Unknown')),
            'skill': str(row.get('Endorsement Skill', 'General'))
        })
    return results[:50]

def analyze_warm_accounts(follows_df, connections_df):
    if follows_df.empty or connections_df.empty: return []
    follows_df.columns = [c.strip() for c in follows_df.columns]
    col_name = 'Organization' if 'Organization' in follows_df.columns else 'Company'
    
    if col_name not in follows_df.columns: return []
    followed_companies = set(follows_df[col_name].dropna().astype(str).str.strip().str.lower().tolist())
    
    if 'Company' not in connections_df.columns: return []
    
    warm_leads = []
    conn_groups = connections_df.groupby('Company')
    for company, group in conn_groups:
        company_clean = str(company).strip().lower()
        if company_clean in followed_companies:
            count = len(group)
            if count > 0:
                warm_leads.append({
                    'company': str(company),
                    'count': count
                })
    warm_leads.sort(key=lambda x: x['count'], reverse=True)
    return warm_leads

def analyze_learning(learning_df):
    if learning_df.empty or 'Content Title' not in learning_df.columns: return []
    return learning_df['Content Title'].dropna().head(10).tolist()

def analyze_influencers(follows_df, connections_df):
    """
    Analyzes Member_Follows to find connected vs unconnected influencers.
    """
    if follows_df.empty: return [], []
    
    follows_df.columns = [c.strip() for c in follows_df.columns]
    if 'FullName' not in follows_df.columns: return [], []
    
    # Filter for active follows
    active_follows = follows_df[follows_df['Status'] == 'Active']['FullName'].dropna().unique().tolist()
    
    # Connection Names
    connected_names = set()
    if not connections_df.empty:
        connected_names = set((connections_df['First Name'] + " " + connections_df['Last Name']).str.strip().tolist())
        
    connected_influencers = []
    unconnected_influencers = []
    
    for person in active_follows:
        # Standardize name for simple match
        # (Real implementation might need robust normalization)
        if person in connected_names:
            connected_influencers.append(person)
        else:
            unconnected_influencers.append(person)
            
    return connected_influencers, unconnected_influencers

def analyze_persona(search_df):
    """
    Extracts high-frequency search terms to validate persona.
    """
    if search_df.empty: return []
    search_df.columns = [c.strip() for c in search_df.columns]
    if 'Search Query' not in search_df.columns: return []
    
    # Count frequency
    counts = search_df['Search Query'].value_counts()
    return counts.head(10).index.tolist()

def generate_report(social_debt, warm_accounts, learning_topics, connected_inf, unconnected_inf, personas):
    with open(OUTPUT_FILE, 'w') as f:
        f.write("# 💎 Hidden Gems Report (Deep Dive)\n")
        f.write(f"**Date:** {datetime.date.today()}\n\n")
        
        # Section 1: Persona Mirror
        f.write(f"## 🎯 Targeted Persona (Based on Search)\n")
        f.write("> **Insight:** You are actively searching for these roles. Ensure your `products.json` matches.\n")
        for p in personas:
            f.write(f"*   `{p}`\n")
        f.write("\n---\n")

        # Section 2: Influencer Sphere
        f.write(f"## 🌟 Influencer Sphere\n")
        f.write(f"**Connected Influencers ({len(connected_inf)})**: *You follow them AND are connected.*\n")
        for i in connected_inf[:10]:
             f.write(f"*   **{i}**: Valid 'Warm Lead'. Dwell on their content -> DM.\n")
        
        f.write(f"\n**Wishlist ({len(unconnected_inf)} People)**: *You follow them but are NOT connected.*\n")
        for i in unconnected_inf[:10]:
            f.write(f"*   {i}\n")
        f.write("\n---\n")

        # Section 3: Social Debt
        f.write(f"## 🤝 The Boomerang List ({len(social_debt)} People)\n")
        for item in social_debt[:10]:
            f.write(f"*   **{item['name']}** (Endorsed for *{item['skill']}*)\n")
        f.write("\n---\n")

        # Section 4: Warm Accounts
        f.write(f"## 🔥 Warm Accounts\n")
        for account in warm_accounts[:10]:
            f.write(f"*   **{account['company']}** ({account['count']} Connections)\n")

    print(f"Report generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    print("Loading data including Second Archive...")
    connections = load_csv(CONNECTIONS_FILE, skip_lines=2)
    if connections.empty: connections = load_csv(CONNECTIONS_FILE)
    
    endorsements = load_csv(ENDORSEMENTS_GIVEN_FILE)
    company_follows = load_csv(COMPANY_FOLLOWS_FILE)
    learning = load_csv(LEARNING_FILE)
    member_follows = load_csv(MEMBER_FOLLOWS_FILE)
    search_queries = load_csv(SEARCH_QUERIES_FILE)

    print("Analyzing...")
    social = analyze_social_debt(endorsements)
    warm = analyze_warm_accounts(company_follows, connections)
    topics = analyze_learning(learning)
    conn_inf, unconn_inf = analyze_influencers(member_follows, connections)
    personas = analyze_persona(search_queries)

    generate_report(social, warm, topics, conn_inf, unconn_inf, personas)
