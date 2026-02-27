---
trigger: glob
description: Expert LinkedIn Content Researcher. Performs deep web research on topics to extract real-time data, company information, logos, and recent news for intelligent content generation. Uses Jina AI for search and extraction, with deer-flow orchestration patterns for multi-step research workflows.
---

# Research Intelligence Skill

**Persona:** Expert LinkedIn Content Researcher with real-time access to web data, news sources, and company information databases.

**Core Mission:** Transform vague topics into rich, factual content by discovering and synthesizing real-world information about products, companies, tools, and trends.

---

## Core Capabilities

### 1. **Entity Detection & Classification**

- Identify if a topic refers to a product, company, person, or abstract concept
- Determine if entity has an official website and online presence
- Confidence scoring for research quality

### 2. **Multi-Source Web Research**

- **Jina Search API**: Find top-ranked, relevant web pages for any topic
- **Jina Reader API**: Convert web pages to clean, LLM-friendly markdown
- **News Discovery**: Extract recent announcements, launches, and trending discussions

### 3. **Asset Discovery**

- Logo extraction from company websites
- Product screenshots and visual assets
- Brand color palette detection

### 4. **Real-Time Intelligence**

- Recent news articles (last 30 days prioritized)
- Product launches and updates
- Industry trends and discussions
- Key features and differentiators

### 5. **Structured Data Synthesis**

- LLM-powered analysis of raw research data
- JSON-formatted output for downstream tools
- Fact verification and source citation

---

## Research Workflow (Deer-Flow Pattern)

The research process follows a **4-phase workflow** with error handling and validation at each step:

### **Phase 1: Entity Detection**

```
Input: Topic string (e.g., "Moltbook")
Process: LLM pre-classification
Output: entity_type, has_website (boolean)
```

- Ask GenAI: "Is '{topic}' a software, tool, product, or company with an official website?"
- If NO → Return minimal research (concept-only)
- If YES → Proceed to Phase 2

### **Phase 2: Search**

```
Input: Topic + entity context
Process: Jina Search API (top 5 results)
Output: List of relevant URLs
```

- Query construction: "{topic} official website features"
- Additional query: "{topic} recent news 2026"
- Filter results by relevance score

### **Phase 3: Content Extraction**

```
Input: List of URLs
Process: Jina Reader API (parallel extraction)
Output: Markdown content per URL
```

- Convert each URL to clean markdown
- Extract: headings, paragraphs, images, links
- Timeout: 10s per URL

### **Phase 4: Analysis & Synthesis**

```
Input: Raw extracted content
Process: LLM analysis with structured output
Output: research.json
```

- GenAI prompt: "Analyze this content and extract key information"
- Schema enforcement for consistent output
- Confidence scoring based on data quality

---

## Output Schema

The research tool outputs a structured JSON file to `.tmp/topic_research.json`:

```json
{
  "topic": "string",
  "entity_type": "product | company | person | concept",
  "has_website": boolean,
  "website_url": "string | null",
  "logo_url": "string | null",
  "description": "string (1-2 sentences)",
  "key_features": ["string", "string", "string"],
  "recent_news": [
    {
      "headline": "string",
      "date": "YYYY-MM-DD",
      "source": "string",
      "url": "string",
      "summary": "string"
    }
  ],
  "confidence_score": 0.0-1.0,
  "research_timestamp": "ISO 8601 datetime",
  "sources": ["url1", "url2", "url3"]
}
```

**Field Descriptions:**

- `confidence_score`: 0.0-0.3 (low quality), 0.3-0.7 (medium), 0.7-1.0 (high quality)
- `entity_type`: Determines downstream content strategy
- `recent_news`: Only includes news from last 30 days
- `logo_url`: Direct URL to company logo (used for image generation)

---

## Usage Instructions

### For Script Developers

When calling `execution/web_research_jina.py`:

```bash
python execution/web_research_jina.py \
  --topic "Moltbook AI platform" \
  --output ".tmp/topic_research.json" \
  --max-urls 5 \
  --news-lookback-days 30
```

### For Content Generation Scripts

Reading research data in `generate_assets.py`:

```python
import json

# Load research data
with open('.tmp/topic_research.json', 'r', encoding='utf-8') as f:
    research = json.load(f)

# Check if high-quality data available
if research['confidence_score'] > 0.7:
    # Use rich context for image generation
    prompt = f"Create image about {research['description']}"
    logo_ref = research.get('logo_url')
else:
    # Fallback to generic prompt
    prompt = f"Create image about {research['topic']}"
```

---

## Integration Points

### With Orchestrator (`orchestrator.py`)

The research step runs **BEFORE** asset generation:

```
1. viral_research (competitor posts - optional)
2. web_research_jina (topic intelligence - ALWAYS)  ← THIS SKILL
3. generate_assets (uses research data)
4. generate_caption (uses research data)
```

### With Asset Generation (`generate_assets.py`)

Research data influences:

- **Image prompts**: More specific descriptions
- **Logo integration**: Company logo as reference image
- **Visual style**: Adapts to product category

### With Caption Generation (`generate_caption.py`)

Research data provides:

- **Factual grounding**: Real product features, not assumptions
- **Trend context**: Recent news for timely hooks
- **Authority**: Citations and specific examples

---

## Error Handling

| Error Scenario | Mitigation |
|----------------|-----------|
| Jina API timeout | Retry with exponential backoff (3 attempts) |
| No website found | Return concept-type research with low confidence |
| Logo URL invalid | Fallback to Google favicon API |
| LLM hallucination | Require source citations in analysis |
| Rate limit hit | Cache research results for 24 hours |

---

## Best Practices

### ✅ DO

- Always check `confidence_score` before using research data
- Cache research results to avoid redundant API calls
- Validate logo URLs before passing to image generation
- Include source citations in generated content

### ❌ DON'T

- Trust research data with confidence < 0.5 without human review
- Use outdated news (check `date` field)
- Assume logo URL works without validation
- Skip error handling for external API calls

---

## Example Usage

### Example 1: Product Research (High Confidence)

**Input:** `"Moltbook AI productivity platform"`

**Output:**

```json
{
  "topic": "Moltbook",
  "entity_type": "product",
  "has_website": true,
  "website_url": "https://moltbook.com",
  "logo_url": "https://moltbook.com/assets/logo.png",
  "description": "Moltbook is an AI-powered productivity platform that recently launched an AI-to-AI social network for automated collaboration.",
  "key_features": [
    "AI automation workflows",
    "AI-to-AI social platform",
    "Unified workspace",
    "Predictive task management"
  ],
  "recent_news": [
    {
      "headline": "Moltbook Launches First AI Social Platform",
      "date": "2026-01-31",
      "source": "TechCrunch",
      "url": "https://techcrunch.com/...",
      "summary": "Moltbook unveiled a revolutionary AI-to-AI social network..."
    }
  ],
  "confidence_score": 0.92,
  "research_timestamp": "2026-02-04T14:30:00Z",
  "sources": [
    "https://moltbook.com",
    "https://techcrunch.com/...",
    "https://producthunt.com/..."
  ]
}
```

### Example 2: Abstract Concept (Low Confidence)

**Input:** `"Leadership tips for remote teams"`

**Output:**

```json
{
  "topic": "Leadership tips for remote teams",
  "entity_type": "concept",
  "has_website": false,
  "website_url": null,
  "logo_url": null,
  "description": "General leadership strategies and best practices for managing distributed teams.",
  "key_features": [],
  "recent_news": [],
  "confidence_score": 0.25,
  "research_timestamp": "2026-02-04T14:35:00Z",
  "sources": []
}
```

---

## Dependencies

### External APIs

- **Jina AI Search** (`s.jina.ai`) - Requires `JINA_API_KEY`
- **Jina AI Reader** (`r.jina.ai`) - Same API key
- **Google GenAI** (Gemini 2.0) - For analysis

### Python Libraries

- `requests` - HTTP calls to Jina endpoints
- `google-generativeai` - LLM analysis
- `json` - Data serialization
- `datetime` - Timestamp management

### Configuration

- `.env` must contain `JINA_API_KEY`
- Timeout settings: 30s total per research run
- Caching: 24-hour TTL for identical topics

---

## Maintenance & Updates

### When to Update This Skill

- Jina API adds new features or endpoints
- New research sources become available
- Output schema needs additional fields
- Error patterns emerge from production logs

### Performance Monitoring

- Track `confidence_score` distribution
- Monitor API latency and timeout rates
- Validate logo URL success rate
- Review LLM hallucination incidents

---

**Last Updated:** 2026-02-04  
**Version:** 1.0.0  
**Maintained By:** LinkedIn Autopilot Research Team
