# Network Intelligence & Voice Engine Implementation Plan
**Goal:** Integrate the existing `network_intelligence` module into the main SaaS architecture, creating a 4-tab Dashboard (Surveillance, CRM, Voice Engine, Brand Assets) that powers hyper-personalized, context-aware LinkedIn post generation and automated lead engagement.
**Architecture:** Move the standalone `network_intelligence` module into the main backend. Refactor it to use Supabase/Firestore. Implement robust ZIP validation, percentile-based post tiering, and a deeply structured `VoiceEngineProfile`. The CRM will use a 2-stage pipeline: Python behavioral analysis to tag connections (filtering out 3+ message cold pitches), followed by an LLM pass to generate relationship summaries and intents for genuine connections.
**Tech Stack:** Python, Pandas, Supabase/Firestore, Gemini API, Vanilla JS.

---

## Phase 1: ZIP Ingestion & Network Intelligence Integration

### Task 1: Robust ZIP Validation & Parsing
**Files:**
- Create: `execution/linkedin_parser.py`

**Step 1: Implement graceful degradation for ZIP parsing**
```python
# execution/linkedin_parser.py
import zipfile
import io
import pandas as pd

def validate_and_parse_zip(zip_file_bytes):
    """Validates the ZIP and extracts available CSVs gracefully."""
    required_files = ['Profile.csv', 'Connections.csv', 'SearchQueries.csv']
    optional_files = ['messages.csv', 'Invitations.csv', 'Endorsement_Received_Info.csv', 'Recommendations_Received.csv', 'Positions.csv', 'Shares.csv']
    
    extracted_data = {}
    missing_required = []
    
    with zipfile.ZipFile(io.BytesIO(zip_file_bytes)) as z:
        namelist = z.namelist()
        
        for req in required_files:
            if req not in namelist:
                missing_required.append(req)
            else:
                with z.open(req) as f:
                    extracted_data[req.split('.')[0].lower()] = pd.read_csv(f).to_dict('records')
                    
        for opt in optional_files:
            if opt in namelist:
                with z.open(opt) as f:
                    extracted_data[opt.split('.')[0].lower()] = pd.read_csv(f).to_dict('records')
                    
    status = "partial" if missing_required else "complete"
    message = f"Missing required files: {missing_required}. Some features will be limited." if missing_required else "All files present."
    
    return {
        "status": status,
        "message": message,
        "proceed": True,
        "data": extracted_data
    }
```

### Task 2: The 2-Stage Message Analyzer (Behavioral + LLM)
**Files:**
- Create: `execution/message_analyzer.py`

**Step 1: Stage 1 - Python Behavioral Tagging**
```python
# execution/message_analyzer.py
def assign_behavioral_tags(thread_df, user_name):
    """Assigns tags based purely on reply patterns, ignoring content."""
    total_msgs = len(thread_df)
    user_msgs = len(thread_df[thread_df['FROM'] == user_name])
    conn_msgs = total_msgs - user_msgs
    
    # Rule 1: Cold Pitch Received (3+ msgs from connection, 0 from user)
    if conn_msgs >= 3 and user_msgs == 0:
        return ["Cold Pitch (Received)"]
        
    # Rule 2: Ghosted Sent (3+ msgs from user, 0 from connection)
    if user_msgs >= 3 and conn_msgs == 0:
        return ["Ghosted (Sent)"]
        
    # Rule 3: Superficial (1-2 msgs total)
    if total_msgs <= 2 and user_msgs > 0 and conn_msgs > 0:
        return ["Superficial"]
        
    # Rule 4: Warm (Back and forth)
    if user_msgs >= 2 and conn_msgs >= 2:
        return ["Warm"]
        
    # Rule 5: Unreplied Single Message (Potential Lead)
    if conn_msgs == 1 and user_msgs == 0:
        return ["Unreplied"]
        
    return ["Uncategorized"]
```

**Step 2: Stage 2 - LLM Intent & Summary Generation**
```python
# execution/message_analyzer.py
def generate_relationship_summary(thread_text, tags):
    """Uses Gemini to summarize intent ONLY for non-spam threads."""
    if "Cold Pitch (Received)" in tags or "Superficial" in tags:
        return {"intent": "N/A", "summary": "Filtered out to save noise."}
        
    prompt = f"""
    Analyze this LinkedIn conversation.
    1. What is the core intent of the connection? (e.g., Buying Services, Networking, Seeking Advice, Recruiting)
    2. Provide a 1-sentence summary of where the relationship currently stands.
    
    Conversation:
    {thread_text}
    """
    # Call Gemini API...
    return {"intent": "Buying Services", "summary": "Connection asked for pricing on AI consulting."}
```

### Task 3: Update CRM Database Schema
**Files:**
- Modify: `execution/db_schema.py`

**Step 1: Add Tags, Intent, and Summary to CRM Contacts**
```python
# execution/db_schema.py
def get_crm_contacts_schema():
    return {
        "table_name": "crm_contacts",
        "fields": {
            "user_id": "string (PK)",
            "linkedin_url": "string",
            "full_name": "string",
            "company": "string",
            "title": "string",
            "behavioral_tags": "array of strings", # e.g., ["Warm", "Hot Lead"]
            "ai_intent": "string", # e.g., "Buying Services"
            "ai_summary": "string", # e.g., "Asked for pricing on AI consulting."
            "last_interaction_date": "timestamp"
        }
    }
```

---

## Phase 2: The Voice Engine & Structured Context

### Task 4: Define the Structured VoiceEngineProfile
**Files:**
- Modify: `execution/db_schema.py`

**Step 1: Update database schema for deep context**
```python
# execution/db_schema.py
def get_voice_engine_schema():
    return {
        "table_name": "voice_engine_profiles",
        "fields": {
            "user_id": "string (PK)",
            "professional_context": {
                "current_role": "string",
                "current_company": "string",
                "years_in_industry": "integer",
                "career_pivot_story": "string",
                "expertise_areas": "array of strings",
                "recent_achievements": "array of strings"
            },
            "target_icp": "string",
            "products_services": [
                {
                    "name": "string",
                    "description": "string",
                    "ideal_customer": "string",
                    "pain_point_solved": "string",
                    "price_range": "string"
                }
            ],
            "messaging_pillars": "array of strings",
            "competitor_positioning": "string"
        }
    }
```

---

## Phase 3: Context-Aware Generation & CRM UI

### Task 5: The "Generate Message" Action
**Files:**
- Create: `execution/message_generator.py`

**Step 1: Draft highly contextual replies**
```python
# execution/message_generator.py
def draft_crm_reply(contact_id, user_voice_profile, recent_messages):
    """Drafts a reply using the Voice Engine and chat history."""
    prompt = f"""
    You are {user_voice_profile['professional_context']['current_role']}.
    You sell: {user_voice_profile['products_services'][0]['name']}.
    
    Draft a LinkedIn DM reply to this connection.
    Recent Chat History:
    {recent_messages}
    
    Keep it casual, professional, and under 3 sentences. Do not be overly salesy unless they explicitly asked for pricing.
    """
    # Call Gemini API...
    return generated_draft
```

### Task 6: The Sleek CRM UI (Frontend Concept)
**Files:**
- Create: `frontend/crm_dashboard.html` (Conceptual)

**Step 1: Implement Smart Filters and Action Buttons**
```html
<!-- Unified Search & Smart Views -->
<div class="crm-header">
    <input type="text" placeholder="Search name, company, or filter by tag..." class="unified-search">
    <select class="smart-views-dropdown">
        <option value="all">View: All Contacts</option>
        <option value="hot">🔥 Needs Attention (Hot Leads)</option>
        <option value="warm">🤝 My Network (Warm + Active)</option>
        <option value="dormant">💤 Needs Reactivation (Dormant)</option>
        <option value="spam">🛑 Spam/Pitches (Cold Pitches)</option>
    </select>
</div>

<!-- CRM Table -->
<table class="crm-table">
    <thead>
        <tr>
            <th>Name</th>
            <th>Company</th>
            <th>Title</th>
            <th>Status (Tags)</th>
            <th>Intent / Summary</th>
            <th>Last Interaction</th>
            <th>Action</th>
        </tr>
    </thead>
    <tbody>
        <!-- Example Row -->
        <tr>
            <td>Sarah Chen</td>
            <td>Acme Corp</td>
            <td>VP Marketing</td>
            <td><span class="badge badge-warm">Warm</span></td>
            <td>
                <strong>Networking</strong><br>
                <small>Discussed AI trends last month; agreed to catch up.</small>
            </td>
            <td>Oct 25, 2023</td>
            <td><button class="btn-generate-msg">✨ Generate Message</button></td>
        </tr>
    </tbody>
</table>
```
