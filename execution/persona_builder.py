"""
Persona Builder Module
Uses Gemini LLM to extract and build user persona from LinkedIn data.
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Gemini
from google import genai
from google.genai import types


@dataclass
class UserPersona:
    """Structured user persona extracted from LinkedIn data."""
    professional_bio: str = ""
    writing_style_rules: List[str] = None
    core_skills: List[str] = None
    expertise_areas: List[str] = None
    target_icp: str = ""  # Ideal Customer Profile
    tone_of_voice: str = ""
    
    def __post_init__(self):
        if self.writing_style_rules is None:
            self.writing_style_rules = []
        if self.core_skills is None:
            self.core_skills = []
        if self.expertise_areas is None:
            self.expertise_areas = []
    
    def to_dict(self) -> Dict:
        return {
            "professional_bio": self.professional_bio,
            "writing_style_rules": self.writing_style_rules,
            "core_skills": self.core_skills,
            "expertise_areas": self.expertise_areas,
            "target_icp": self.target_icp,
            "tone_of_voice": self.tone_of_voice
        }


class PersonaBuilder:
    """Build user persona using Gemini LLM."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize persona builder.
        
        Args:
            api_key: Gemini API key. If not provided, uses GOOGLE_GEMINI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set GOOGLE_GEMINI_API_KEY environment variable.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
    
    def build_persona(self, linkedin_data: Dict) -> UserPersona:
        """
        Build complete persona from LinkedIn data.
        
        Args:
            linkedin_data: Parsed LinkedIn data from linkedin_parser
            
        Returns:
            UserPersona object with extracted persona attributes
        """
        persona = UserPersona()
        
        # Extract professional bio from profile and positions
        persona.professional_bio = self._extract_bio(
            linkedin_data.get("profile"),
            linkedin_data.get("positions", []),
            linkedin_data.get("career_summary", "")
        )
        
        # Extract writing style from shares (posts)
        persona.writing_style_rules = self._extract_writing_style(
            linkedin_data.get("shares", [])
        )
        
        # Extract core skills
        persona.core_skills = self._extract_skills(
            linkedin_data.get("profile"),
            linkedin_data.get("positions", [])
        )
        
        # Extract expertise areas
        persona.expertise_areas = self._extract_expertise(
            linkedin_data.get("profile"),
            linkedin_data.get("positions", [])
        )
        
        # Determine tone of voice
        persona.tone_of_voice = self._extract_tone(
            linkedin_data.get("profile"),
            linkedin_data.get("shares", [])
        )
        
        return persona
    
    def _extract_bio(self, profile, positions: List, career_summary: str) -> str:
        """Generate professional bio using Gemini."""
        # Prepare context for Gemini
        profile_data = {}
        if profile:
            profile_data = {
                "name": getattr(profile, 'full_name', ''),
                "headline": getattr(profile, 'headline', ''),
                "summary": getattr(profile, 'summary', ''),
                "industry": getattr(profile, 'industry', '')
            }
        
        positions_data = []
        for pos in positions[:5]:  # Top 5 positions
            positions_data.append({
                "title": getattr(pos, 'title', ''),
                "company": getattr(pos, 'company', ''),
                "is_current": getattr(pos, 'is_current', False)
            })
        
        prompt = f"""
        Create a compelling 3-paragraph professional bio based on this LinkedIn data.
        
        Profile: {profile_data}
        Career Summary: {career_summary}
        Positions: {positions_data}
        
        Rules:
        1. First paragraph: Who they are now (current role + expertise)
        2. Second paragraph: Their journey and key achievements
        3. Third paragraph: What they help people with / their mission
        
        Write in first person ("I", "my"). Keep it professional but warm.
        Return ONLY the bio text, no headers or formatting.
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=500
                ),
                contents=prompt
            )
            text = (response.text or "").strip()
            if text:
                return text
            return self._fallback_bio(profile, career_summary)
        except Exception as e:
            print(f"[PersonaBuilder] Bio extraction error: {e}")
            return self._fallback_bio(profile, career_summary)
    
    def _fallback_bio(self, profile, career_summary: str) -> str:
        """Fallback bio if Gemini fails."""
        if profile:
            name = getattr(profile, 'full_name', '')
            headline = getattr(profile, 'headline', '')
            return f"{name} - {headline}. {career_summary}"
        return career_summary
    
    def _extract_writing_style(self, shares: List) -> List[str]:
        """Extract writing style rules from posts using Gemini."""
        if not shares:
            return ["Professional tone", "Clear and concise", "Engaging content"]
        
        # Get top posts content
        posts_content = []
        for share in shares[:10]:  # Analyze top 10 posts
            content = getattr(share, 'content', '')
            if content and len(content) > 50:
                posts_content.append(content[:500])  # First 500 chars
        
        if not posts_content:
            return ["Professional tone", "Clear and concise", "Engaging content"]
        
        prompt = f"""
        Analyze these LinkedIn posts and extract 5 writing style characteristics.
        
        Posts:
        {chr(10).join(f"- {post}" for post in posts_content[:3])}
        
        Return a JSON array of 5 strings describing the writing style.
        Examples: "Uses short punchy sentences", "Starts with questions", "Heavy use of emojis"
        
        Return ONLY the JSON array, no other text.
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=300
                ),
                contents=prompt
            )
            
            import json
            # Try to parse as JSON
            text = response.text.strip()
            # Remove markdown code blocks if present
            text = text.replace('```json', '').replace('```', '').strip()
            rules = json.loads(text)
            return rules if isinstance(rules, list) else ["Professional tone"]
        except Exception as e:
            print(f"[PersonaBuilder] Writing style extraction error: {e}")
            return ["Professional tone", "Clear and concise"]
    
    def _extract_skills(self, profile, positions: List) -> List[str]:
        """Extract core skills from profile and positions."""
        skills = set()
        
        # From profile
        if profile:
            headline = getattr(profile, 'headline', '').lower()
            # Extract skills from headline
            skill_keywords = [
                'marketing', 'sales', 'leadership', 'strategy', 'operations',
                'product', 'engineering', 'design', 'finance', 'analytics',
                'ai', 'ml', 'data', 'cloud', 'software', 'management'
            ]
            for keyword in skill_keywords:
                if keyword in headline:
                    skills.add(keyword.title())
        
        # From positions
        for pos in positions[:3]:
            title = getattr(pos, 'title', '').lower()
            if 'marketing' in title:
                skills.add('Marketing')
            elif 'sales' in title:
                skills.add('Sales')
            elif 'product' in title:
                skills.add('Product Management')
            elif 'engineer' in title or 'developer' in title:
                skills.add('Engineering')
            elif 'founder' in title or 'ceo' in title:
                skills.add('Leadership')
                skills.add('Entrepreneurship')
        
        return list(skills) if skills else ['Leadership', 'Strategy']
    
    def _extract_expertise(self, profile, positions: List) -> List[str]:
        """Extract expertise areas from profile and positions."""
        expertise = set()
        
        # From profile industry
        if profile:
            industry = getattr(profile, 'industry', '')
            if industry:
                expertise.add(industry)
        
        # From company industries
        company_industries = {
            'tech': ['software', 'technology', 'ai', 'startup', 'saas'],
            'finance': ['banking', 'finance', 'investment', 'fintech'],
            'healthcare': ['healthcare', 'medical', 'biotech', 'pharma'],
            'consulting': ['consulting', 'advisory', 'strategy']
        }
        
        for pos in positions[:5]:
            company = getattr(pos, 'company', '').lower()
            for industry, keywords in company_industries.items():
                if any(kw in company for kw in keywords):
                    expertise.add(industry.title())
        
        return list(expertise) if expertise else ['Business', 'Technology']
    
    def _extract_tone(self, profile, shares: List) -> str:
        """Extract tone of voice from profile and posts."""
        # Analyze posts for tone
        if shares:
            posts_content = []
            for share in shares[:5]:
                content = getattr(share, 'content', '')
                if content:
                    posts_content.append(content[:300])
            
            if posts_content:
                prompt = f"""
                Analyze the tone of voice in these LinkedIn posts.
                Describe it in 2-3 words (e.g., "Professional yet casual", "Bold and energetic").
                
                Posts:
                {chr(10).join(posts_content[:2])}
                
                Return ONLY the tone description, nothing else.
                """
                
                try:
                    response = self.client.models.generate_content(
                        model=self.model,
                        config=types.GenerateContentConfig(
                            temperature=0.3,
                            max_output_tokens=50
                        ),
                        contents=prompt
                    )
                    return response.text.strip() if response.text else "Professional"
                except Exception as e:
                    print(f"[PersonaBuilder] Tone extraction error: {e}")
        
        return "Professional"


def build_user_persona(linkedin_data: Dict, api_key: Optional[str] = None) -> Dict:
    """
    Convenience function to build user persona from LinkedIn data.
    
    Args:
        linkedin_data: Parsed LinkedIn data from linkedin_parser
        api_key: Optional Gemini API key
        
    Returns:
        Dictionary with persona attributes
    """
    try:
        builder = PersonaBuilder(api_key)
        persona = builder.build_persona(linkedin_data)
        return persona.to_dict()
    except Exception as e:
        print(f"[build_user_persona] Error: {e}")
        # Return default persona
        return {
            "professional_bio": linkedin_data.get("career_summary", ""),
            "writing_style_rules": ["Professional tone", "Clear and concise"],
            "core_skills": ["Leadership", "Strategy"],
            "expertise_areas": ["Business"],
            "tone_of_voice": "Professional"
        }


if __name__ == "__main__":
    print("[PersonaBuilder] Module loaded successfully")
