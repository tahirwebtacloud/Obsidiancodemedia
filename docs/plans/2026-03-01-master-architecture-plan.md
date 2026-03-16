# Master Architecture Plan: Branding, Network Intelligence & Voice Engine
**Goal:** Build a comprehensive, multi-tenant SaaS platform that handles automated brand extraction (Firecrawl), live UI previews, folder-agnostic LinkedIn ZIP ingestion, behavioral CRM tagging, and context-aware AI post/message generation.
**Architecture:** A 4-Tab Dashboard (Brand Assets, Surveillance, CRM, Voice Engine). The backend uses Supabase/Firestore for multi-tenant data, Firecrawl for brand extraction, Python/Pandas for ZIP parsing and behavioral message analysis, and Gemini for intent extraction and content generation.
**Tech Stack:** Python, Pandas, Supabase/Firestore, Firecrawl API, Gemini API, Vanilla JS/CSS.

---

## Phase 1: Database Schema & Core Foundation

### Task 1: Unified Database Schema
**Files:**
- Create/Modify: `execution/db_schema.py`

**Step 1: Define the multi-tenant tables**
```python
# execution/db_schema.py
def get_master_schema():
    return {
        "user_profiles": { # Branding & Core Identity
            "user_id": "string (PK)",
            "brand_name": "string",
            "primary_color": "string (Hex)",
            "secondary_color": "string (Hex)",
            "font_family": "string",
            "logo_url": "string",
            "tone_of_voice": "text"
        },
        "voice_engine_profiles": { # Deep Context for LLM
            "user_id": "string (PK)",
            "professional_context": {
                "current_role": "string",
                "career_pivot_story": "string",
                "expertise_areas": "array of strings"
            },
            "target_icp": "string",
            "products_services": "array of objects (name, description, pain_point, price)",
            "messaging_pillars": "array of strings",
            "competitor_positioning": "string"
        },
        "crm_contacts": { # Network Intelligence
            "user_id": "string (FK)",
            "linkedin_url": "string",
            "full_name": "string",
            "company": "string",
            "title": "string",
            "behavioral_tags": "array of strings", # e.g., ["Warm", "Hot Lead"]
            "ai_intent": "string",
            "ai_summary": "string",
            "last_interaction_date": "timestamp"
        }
    }
```

---

## Phase 2: Frontend Branding & Firecrawl Integration

### Task 2: Firecrawl Brand Extractor
**Files:**
- Create: `execution/brand_extractor.py`

**Step 1: Implement Firecrawl extraction logic**
```python
# execution/brand_extractor.py
import requests

def extract_brand_assets(url, firecrawl_api_key):
    """Uses Firecrawl to extract colors, fonts, and logo from a URL."""
    # Implementation using Firecrawl's 'branding' format or LLM extraction
    # Returns: {"primary_color": "#...", "font_family": "...", "logo_url": "..."}
    pass
```

### Task 3: Live CSS Preview (Frontend)
**Files:**
- Create: `frontend/branding_dashboard.html`
- Create: `frontend/js/brand_preview.js`

**Step 1: Implement real-time CSS variable injection**
```javascript
// frontend/js/brand_preview.js
function updateBrandPreview(colors, font, logoUrl) {
    const root = document.documentElement;
    if (colors.primary) root.style.setProperty('--brand-primary', colors.primary);
    if (colors.secondary) root.style.setProperty('--brand-secondary', colors.secondary);
    if (font) root.style.setProperty('--brand-font', font);
    
    const logoEl = document.getElementById('preview-logo');
    if (logoUrl && logoEl) logoEl.src = logoUrl;
}
```

---

## Phase 3: Folder-Agnostic ZIP Ingestion

### Task 4: Robust ZIP Validation & Parsing
**Files:**
- Create: `execution/linkedin_parser.py`

**Step 1: Implement folder-agnostic ZIP parsing**
```python
# execution/linkedin_parser.py
import zipfile
import io
import pandas as pd

def validate_and_parse_zip(zip_file_bytes):
    """Validates the ZIP and extracts CSVs, ignoring internal folder structures (e.g., 'raw/')."""
    required_files = ['Profile.csv', 'Connections.csv', 'SearchQueries.csv']
    optional_files = ['messages.csv', 'Invitations.csv']
    
    extracted_data = {}
    missing_required = []
    
    with zipfile.ZipFile(io.BytesIO(zip_file_bytes)) as z:
        namelist = z.namelist()
        
        for req in required_files:
            # Find the file regardless of which folder it is in (e.g., 'raw/Profile.csv')
            matched_path = next((path for path in namelist if path.endswith(req)), None)
            
            if not matched_path:
                missing_required.append(req)
            else:
                with z.open(matched_path) as f:
                    extracted_data[req.split('.')[0].lower()] = pd.read_csv(f).to_dict('records')
                    
        for opt in optional_files:
            matched_path = next((path for path in namelist if path.endswith(opt)), None)
            if matched_path:
                with z.open(matched_path) as f:
                    extracted_data[opt.split('.')[0].lower()] = pd.read_csv(f).to_dict('records')
                    
    status = "partial" if missing_required else "complete"
    return {"status": status, "proceed": True, "data": extracted_data}
```

---

## Phase 4: Network Intelligence & CRM

### Task 5: The 2-Stage Message Analyzer
**Files:**
- Create: `execution/message_analyzer.py`

**Step 1: Stage 1 - Python Behavioral Tagging**
```python
# execution/message_analyzer.py
def assign_behavioral_tags(thread_df, user_name):
    """Assigns tags based purely on reply patterns."""
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
        
    # Call Gemini API to extract Intent (e.g., "Networking") and a 1-sentence Summary.
    pass
```

### Task 6: The Sleek CRM UI
**Files:**
- Create: `frontend/crm_dashboard.html`

**Step 1: Implement Smart Filters and Action Buttons**
```html
<!-- Unified Search & Smart Views -->
<div class="crm-header">
    <input type="text" placeholder="Search name, company, or filter by tag..." class="unified-search">
    <select class="smart-views-dropdown">
        <option value="all">View: All Contacts</option>
        <option value="hot">🔥 Needs Attention (Hot Leads)</option>
        <option value="warm">🤝 My Network (Warm + Active)</option>
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
            <td><strong>Networking</strong><br><small>Discussed AI trends.</small></td>
            <td>Oct 25, 2023</td>
            <td><button class="btn-generate-msg">✨ Generate Message</button></td>
        </tr>
    </tbody>
</table>
```

---

## Phase 5: The Voice Engine & Generation

### Task 7: Context-Aware Generation (Posts & Messages)
**Files:**
- Modify: `execution/generate_assets.py`
- Create: `execution/message_generator.py`

**Step 1: Draft highly contextual CRM replies**
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
    
    Keep it casual, professional, and under 3 sentences.
    """
    # Call Gemini API...
    return generated_draft
```

---

## Phase 6: Dynamic Prompt Engineering & SOP Integration

### Task 8: The "SOP + Context" Injection Engine
**Goal:** Integrate the 8 existing SOPs (Authority, Educational, Promotional, Storytelling x Article/Caption) as system instructions, injecting dynamic variables at runtime without modifying the static SOP files.

**Files:**
- Create: `execution/prompt_engine.py`

**Step 1: Build the Prompt Constructor**
```python
# execution/prompt_engine.py
import os

def load_sop(post_type, format_type):
    """Loads the specific SOP file (e.g., directives/authority_article.md)."""
    # Map 'money', 'math', 'id', 'challenge' to the existing file names if needed, 
    # or use the user's specific 8 types: Authority, Educational, Promotional, Storytelling
    filename = f"directives/{post_type}_{format_type}.md"
    try:
        with open(filename, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "SOP not found. Using default."

def construct_master_prompt(user_profile, topic, research_summary, rag_context, post_type="authority", format_type="article"):
    """
    Combines the Static SOP with Dynamic Variables.
    
    Args:
        user_profile (dict): From VoiceEngineProfile (Role, Tone, Products).
        topic (str): User input.
        research_summary (str): From Jina AI.
        rag_context (str): Personal stories from Vector DB.
        post_type (str): authority, educational, promotional, storytelling.
        format_type (str): article, caption.
    """
    sop_content = load_sop(post_type, format_type)
    
    return f"""
    [SYSTEM INSTRUCTION]
    You are an expert LinkedIn ghostwriter for {user_profile['brand_name']}.
    You MUST follow the Standard Operating Procedure (SOP) below EXACTLY.
    
    === BEGIN SOP ===
    {sop_content}
    === END SOP ===

    [DYNAMIC CONTEXT]
    **User Role:** {user_profile['professional_context']['current_role']}
    **Tone of Voice:** {user_profile['tone_of_voice']}
    **Target Audience:** {user_profile['target_icp']}
    
    [RESEARCH & FACTS]
    {research_summary}
    
    [USER'S PERSONAL HISTORY (RAG)]
    Use these real anecdotes to ground the post in reality:
    {rag_context}
    
    [TASK]
    Write a {post_type} {format_type} about "{topic}".
    Follow the SOP structure (Hook, Story, Lesson, etc.) strictly.
    """
```
