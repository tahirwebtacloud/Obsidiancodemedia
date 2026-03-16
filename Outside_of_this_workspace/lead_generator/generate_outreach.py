import pandas as pd
import os
import datetime

# --- Configuration ---
INPUT_FILE = "Linkedin Data/Connections.csv"
OUTPUT_FILE = "LEAD_GEN_REPORT.md"

# Product Segments & Keywords
SEGMENTS = {
    "Strategic Lead Gen": {
        "keywords": ["Founder", "Co-Founder", "Owner", "CEO", "Agency", "Sales Director", "Head of Sales", "Business Development"],
        "value_prop": "helping agencies and founders build scalable, automated lead gen systems that don't rely on manual grinding.",
        "dm_template": """
**DM Draft (7-Step Flow)**
1. **Icebreaker**: "Hey {first_name}, connecting from {company}. [Mention specific detail from profile/post]."
2. **Goal Alignment**: "Curious, are you focused on scaling outbound this quarter, or mostly relying on referrals?"
3. **Bottleneck/Insight**: "We're seeing a lot of agencies get stuck on the manual outreach hamster wheel. We help build systems that run on autopilot."
4. **Offer**: "Happy to share a breakdown of how we automated lead gen for a similar agency? Let me know."
"""
    },
    "Workflow Automation": {
        "keywords": ["COO", "Chief Operating Officer", "Operations Manager", "Head of Operations", "Director of Operations", "VP Operations"],
        "value_prop": "automating complex internal workflows to reduce overhead and increase velocity.",
        "dm_template": """
**DM Draft (7-Step Flow)**
1. **Icebreaker**: "Hey {first_name}, saw you're leading ops at {company}. [Mention specific detail]."
2. **Goal Alignment**: "How's the operational efficiency looking for '26? Any big initiatives to streamline?"
3. **Bottleneck/Insight**: "Often see ops leaders bogged down by repetitive manual processes. We build AI agents to handle that grunt work."
4. **Offer**: "We helped a client cut onboarding time by 80%. Worth a quick chat to see if we could do the same for you?"
"""
    },
    "Compliance & Onboarding": {
        "keywords": ["Compliance", "HR Director", "Head of People", "Human Resources", "Onboarding"],
        "value_prop": "streamlining compliance and onboarding tailored for high-risk or complex industries.",
        "dm_template": """
**DM Draft (7-Step Flow)**
1. **Icebreaker**: "Hey {first_name}, noticed your role in {company}. [Mention detail]."
2. **Goal Alignment**: "Is scaling the team or managing compliance a bigger headache right now?"
3. **Bottleneck/Insight**: "Manual compliance checks are a massive time sink. We automate that pipeline."
4. **Offer**: "Happy to share a case study on how we automated compliance workflows? Let me know."
"""
    }
}

def load_connections(filepath):
    """Loads connections, handling potential header offset."""
    try:
        df = pd.read_csv(filepath)
    except:
        try:
            df = pd.read_csv(filepath, skiprows=3)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return pd.DataFrame()
    return df

def segment_connection(position):
    """Determines the segment based on position title."""
    if pd.isna(position):
        return None, None
    
    position_lower = position.lower()
    for segment, data in SEGMENTS.items():
        for keyword in data["keywords"]:
            if keyword.lower() in position_lower:
                return segment, data
    return None, None

def generate_report():
    print(f"Loading data from {INPUT_FILE}...")
    df = load_connections(INPUT_FILE)
    
    if df.empty:
        print("No data found.")
        return

    matches = []
    
    print(f"Analyzing {len(df)} connections...")
    for _, row in df.iterrows():
        position = row.get("Position", "")
        company = row.get("Company", "")
        first_name = row.get("First Name", "There")
        
        segment_name, segment_data = segment_connection(position)
        
        if segment_name:
            matches.append({
                "first_name": first_name,
                "last_name": row.get("Last Name", ""),
                "company": company,
                "position": position,
                "segment": segment_name,
                "data": segment_data,
                "connected_on": row.get("Connected On", "")
            })

    # Sort matches by Segment
    matches.sort(key=lambda x: x['segment'])

    # Generate Markdown Output
    with open(OUTPUT_FILE, "w") as f:
        f.write(f"# Lead Generation Report\n\n")
        f.write(f"**Generated On:** {datetime.datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"**Source Data:** {len(df)} connections analyzed\n")
        f.write(f"**Potential Leads Identified:** {len(matches)}\n\n")
        f.write("---\n\n")
        
        current_segment = None
        for match in matches:
            if match['segment'] != current_segment:
                current_segment = match['segment']
                f.write(f"## Segment: {current_segment}\n")
                f.write(f"**Target Audience:** {', '.join(match['data']['keywords'])}\n")
                f.write(f"**Value Proposition:** {match['data']['value_prop']}\n\n")
                
                # Add Strategy Post Concept for this segment
                f.write(f"### Strategy Post Idea for {current_segment}\n")
                f.write(f"> **Hook:** \"Why manual {{process}} is killing your {{metric}}.\"\n")
                f.write(f"> **Story/Insight:** Share a story about a client in this segment who automated their workflow.\n")
                f.write(f"> **Call to Engage:** \"How are you handling {{process}} today?\"\n\n")
                f.write("---\n\n")

            dm_draft = match['data']['dm_template'].format(
                first_name=match['first_name'],
                company=match['company']
            )

            f.write(f"### {match['first_name']} {match['last_name']}\n")
            f.write(f"- **Role:** {match['position']} @ {match['company']}\n")
            f.write(f"- **Connected:** {match['connected_on']}\n")
            f.write(f"- **Suggested Outreach:**\n{dm_draft}\n")
            f.write("\n")

    print(f"Report generated: {OUTPUT_FILE} with {len(matches)} matches.")

if __name__ == "__main__":
    generate_report()
