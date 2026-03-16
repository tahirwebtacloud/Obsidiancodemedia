# Frontend Branding Management & Personalization Implementation Plan
**Goal:** Transform the static, single-tenant LinkedIn Post Generator into a multi-tenant SaaS by implementing dynamic, user-specific branding (via Firecrawl) and professional persona ingestion (via LinkedIn data export).
**Architecture:** A Python backend (FastAPI/Flask) handles Firecrawl extraction and LinkedIn ZIP parsing, storing user-specific data in Supabase/Firestore. The vanilla JS frontend provides a "Magic Link" onboarding, live CSS variable injection for previews, and a dashboard for managing brand assets. The core generation engine (`orchestrator.py`, `generate_assets.py`) is refactored to fetch and inject this dynamic user data into LLM and image generation prompts.
**Tech Stack:** Python, Vanilla JS, CSS Variables, Firecrawl MCP/API, Supabase/Firestore, Gemini API.

---

## Phase 1: Database Schema & Backend Foundation

### Task 1: Define User Profile Schema in Database
**Files:**
- Create: `execution/db_schema.py` (or update existing `supabase_client.py`/`firestore_client.py`)

**Step 1: Write the schema definition**
Create a function to initialize or document the required tables/collections.
```python
# execution/db_schema.py
def get_user_profile_schema():
    return {
        "table_name": "user_profiles",
        "fields": {
            "user_id": "string (Primary Key)",
            "brand_name": "string",
            "primary_color": "string (Hex)",
            "secondary_color": "string (Hex)",
            "font_family": "string",
            "logo_url": "string",
            "visual_style": "text",
            "tone_of_voice": "text",
            "professional_bio": "text",
            "core_skills": "array of strings",
            "writing_style_rules": "array of strings",
            "updated_at": "timestamp"
        }
    }
```

### Task 2: Create Firecrawl Extraction Endpoint
**Files:**
- Modify: `server.py` (or create a new routing file if using FastAPI/Flask)
- Create: `execution/brand_extractor.py`

**Step 1: Implement Firecrawl logic**
```python
# execution/brand_extractor.py
import os
import json
from firecrawl import FirecrawlApp # Assuming Firecrawl SDK or direct API call

def extract_brand_from_url(url: str) -> dict:
    """Uses Firecrawl to extract brand identity from a URL."""
    # In a real implementation, use the Firecrawl SDK or REST API
    # This mimics the MCP tool behavior we tested
    prompt = "Extract the brand identity of this company. Find the primary hex color, secondary hex color, the main font family used, a URL to their high-resolution logo, and a 2-sentence description of their visual style and tone of voice."
    schema = {
        "type": "object",
        "properties": {
            "primaryColor": {"type": "string"},
            "secondaryColor": {"type": "string"},
            "fontFamily": {"type": "string"},
            "logoUrl": {"type": "string"},
            "visualStyle": {"type": "string"},
            "toneOfVoice": {"type": "string"}
        }
    }
    
    # Mocking the Firecrawl call for the plan
    # app = FirecrawlApp(api_key=os.environ.get("FIRECRAWL_API_KEY"))
    # result = app.scrape_url(url, params={"formats": ["extract"], "extract": {"prompt": prompt, "schema": schema}})
    # return result.get("extract", {})
    
    return {
        "primaryColor": "#0073e6",
        "secondaryColor": "#ffcc00",
        "fontFamily": "Arial, sans-serif",
        "logoUrl": "https://example.com/logo.png",
        "visualStyle": "Modern and dynamic.",
        "toneOfVoice": "Professional."
    }
```

**Step 2: Add API Route**
```python
# In server.py (pseudo-code depending on framework)
# @app.route('/api/extract-brand', methods=['POST'])
# def api_extract_brand():
#     data = request.json
#     url = data.get('url')
#     brand_data = extract_brand_from_url(url)
#     return jsonify(brand_data)
```

---

## Phase 2: Frontend Branding UI & Live Preview

### Task 3: Build the Brand Settings UI
**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/style.css`

**Step 1: Add HTML structure**
Add a new section in the settings modal for Brand Management.
```html
<!-- frontend/index.html -->
<div id="brand-settings-section">
    <h3>Brand Identity</h3>
    <div class="input-group">
        <label>Company Website URL (Auto-Extract)</label>
        <input type="url" id="brand-url-input" placeholder="https://yourcompany.com">
        <button id="extract-brand-btn">Analyze Brand</button>
    </div>
    
    <div id="brand-assets-preview" style="display: none;">
        <div class="color-swatches">
            <input type="color" id="primary-color-picker">
            <input type="color" id="secondary-color-picker">
        </div>
        <input type="text" id="font-family-input">
        <img id="logo-preview" src="" alt="Brand Logo" style="max-width: 100px;">
        <textarea id="visual-style-input"></textarea>
        <textarea id="tone-of-voice-input"></textarea>
        <button id="save-brand-btn">Save & Apply</button>
    </div>
</div>
```

**Step 2: Define CSS Variables**
Ensure the main stylesheet uses variables for core branding.
```css
/* frontend/style.css */
:root {
    --brand-primary: #0077b5; /* Default LinkedIn Blue */
    --brand-secondary: #ffffff;
    --brand-font: 'Inter', sans-serif;
}

body {
    font-family: var(--brand-font);
}

.primary-button {
    background-color: var(--brand-primary);
    color: var(--brand-secondary);
}
```

### Task 4: Implement Live CSS Injection
**Files:**
- Modify: `frontend/script.js` (or `frontend/settings.js`)

**Step 1: Write JS to handle extraction and preview**
```javascript
// frontend/script.js
document.getElementById('extract-brand-btn').addEventListener('click', async () => {
    const url = document.getElementById('brand-url-input').value;
    // Show loading state...
    
    try {
        const response = await fetch('/api/extract-brand', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const brandData = await response.json();
        
        // Populate UI
        document.getElementById('primary-color-picker').value = brandData.primaryColor;
        document.getElementById('secondary-color-picker').value = brandData.secondaryColor;
        document.getElementById('font-family-input').value = brandData.fontFamily;
        document.getElementById('logo-preview').src = brandData.logoUrl;
        document.getElementById('visual-style-input').value = brandData.visualStyle;
        document.getElementById('tone-of-voice-input').value = brandData.toneOfVoice;
        
        document.getElementById('brand-assets-preview').style.display = 'block';
        
        // Apply Live Preview
        applyLivePreview(brandData);
        
    } catch (error) {
        console.error("Extraction failed", error);
    }
});

function applyLivePreview(brandData) {
    document.documentElement.style.setProperty('--brand-primary', brandData.primaryColor);
    document.documentElement.style.setProperty('--brand-secondary', brandData.secondaryColor);
    document.documentElement.style.setProperty('--brand-font', brandData.fontFamily);
    // Optionally update a logo element in the navbar
}
```

---

## Phase 3: LinkedIn Data Ingestion (The "Digital Twin")

### Task 5: Create ZIP Upload & Parsing Endpoint
**Files:**
- Create: `execution/linkedin_parser.py`
- Modify: `server.py`

**Step 1: Implement ZIP extraction and CSV parsing**
```python
# execution/linkedin_parser.py
import zipfile
import pandas as pd
import io

def parse_linkedin_export(zip_file_bytes):
    """Extracts key data from a LinkedIn data export ZIP."""
    data = {
        "profile": "",
        "positions": "",
        "shares": ""
    }
    
    with zipfile.ZipFile(io.BytesIO(zip_file_bytes)) as z:
        if "Profile.csv" in z.namelist():
            with z.open("Profile.csv") as f:
                df = pd.read_csv(f)
                data["profile"] = df.to_dict('records')[0] if not df.empty else {}
                
        if "Positions.csv" in z.namelist():
            with z.open("Positions.csv") as f:
                df = pd.read_csv(f)
                data["positions"] = df.to_dict('records')
                
        if "Shares.csv" in z.namelist():
            with z.open("Shares.csv") as f:
                df = pd.read_csv(f)
                # Get last 50 posts for tone analysis
                data["shares"] = df.head(50).to_dict('records')
                
    return data
```

### Task 6: LLM Persona Extraction
**Files:**
- Create: `execution/persona_builder.py`

**Step 1: Use Gemini to summarize career and writing style**
```python
# execution/persona_builder.py
from google import genai # Assuming existing setup

def build_user_persona(parsed_data):
    """Uses Gemini to create a bio and writing rules from raw LinkedIn data."""
    # Mocking Gemini call
    bio_prompt = f"Summarize this career history into a 3-paragraph professional bio: {parsed_data['positions']}"
    style_prompt = f"Analyze these past LinkedIn posts and extract 5 key writing style rules: {parsed_data['shares']}"
    
    # client = genai.Client()
    # bio_response = client.models.generate_content(model='gemini-2.5-flash', contents=bio_prompt)
    # style_response = client.models.generate_content(model='gemini-2.5-flash', contents=style_prompt)
    
    return {
        "professional_bio": "Experienced leader in tech...", # bio_response.text
        "writing_style_rules": ["Uses short sentences", "Starts with a hook", "No emojis"], # Parsed from style_response
        "core_skills": ["Leadership", "Python", "Marketing"] # Extracted from profile/skills
    }
```

---

## Phase 4: Refactoring the Generation Engine

### Task 7: Inject Dynamic Data into Prompts
**Files:**
- Modify: `execution/generate_assets.py`
- Modify: `orchestrator.py`

**Step 1: Update prompt construction to use DB data instead of static files**
Currently, `generate_assets.py` likely reads `directives/brand_knowledge.md`. We need to change this to accept a `user_profile` dictionary.

```python
# execution/generate_assets.py (Conceptual modification)

def generate_caption(topic, user_profile, post_type="educational"):
    """Generates a caption using the user's specific persona and brand voice."""
    
    system_instruction = f"""
    You are acting as the user. 
    Professional Background: {user_profile.get('professional_bio', '')}
    Core Skills: {', '.join(user_profile.get('core_skills', []))}
    Tone of Voice: {user_profile.get('tone_of_voice', 'Professional')}
    
    CRITICAL WRITING RULES:
    {chr(10).join(user_profile.get('writing_style_rules', []))}
    """
    
    prompt = f"Write a {post_type} LinkedIn post about {topic}."
    
    # Call Gemini with system_instruction and prompt
    # ...
```

**Step 2: Update Image Generation Prompts**
```python
# execution/generate_assets.py (Conceptual modification)

def generate_image_prompt(topic, user_profile):
    """Generates an image prompt incorporating brand colors and style."""
    
    prompt = f"""
    Create an image about {topic}.
    MANDATORY BRANDING:
    - Primary Color: {user_profile.get('primary_color', '#000000')}
    - Secondary Color: {user_profile.get('secondary_color', '#FFFFFF')}
    - Visual Style: {user_profile.get('visual_style', 'Minimalist')}
    """
    # ...
```

### Task 8: Update Orchestrator to Fetch User Data
**Files:**
- Modify: `orchestrator.py`

**Step 1: Fetch user profile before running steps**
```python
# orchestrator.py
def main():
    # ... existing arg parsing ...
    parser.add_argument("--user_id", required=True, help="ID of the user generating the post.")
    args = parser.parse_args()
    
    # Fetch user profile from DB
    # user_profile = db_client.get_user_profile(args.user_id)
    
    # Pass user_profile (or user_id) to subsequent execution scripts
    # run_step(["python", "execution/generate_assets.py", "--user_id", args.user_id, ...])
```
