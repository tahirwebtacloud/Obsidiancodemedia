"""
Message Generator Module
Generates personalized outreach messages based on CRM contact analysis.
"""

import os
from typing import Dict, Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv

from google import genai
from google.genai import types

load_dotenv()


@dataclass
class GeneratedMessage:
    """Generated outreach message."""
    subject: str
    body: str
    tone: str
    personalization_notes: str


class MessageGenerator:
    """Generate personalized LinkedIn messages using AI."""
    
    MESSAGE_TEMPLATES = {
        'warm_lead': {
            'tone': 'consultative and direct',
            'goal': 'advance toward a concrete next step (call, demo, or proposal)',
            'cta': 'suggest one specific time slot or ask one qualifying question',
            'instruction': (
                'This prospect has shown genuine interest. Be confident and specific. '
                'Reference their exact interest or question from the conversation. '
                'Propose a concrete next step — do not be vague. '
                'Do NOT mention your products unless they asked about them. Lead with their problem, not your solution.'
            ),
        },
        'client': {
            'tone': 'direct, collegial, and results-focused',
            'goal': 'strengthen the working relationship and surface next opportunity',
            'cta': 'check in on a specific deliverable or ask about their next goal',
            'instruction': (
                'This is an existing or past paying client. Treat them as a colleague, not a prospect. '
                'Reference a specific shared project, deliverable, or outcome from the conversation. '
                'Do NOT pitch new services unless they brought it up. '
                'Keep the tone warm but efficient — they value your time and theirs.'
            ),
        },
        'referrer': {
            'tone': 'warm, genuine, and appreciative',
            'goal': 'acknowledge the referral and keep the relationship warm',
            'cta': 'offer to update them on the outcome or ask how you can add value back',
            'instruction': (
                'This person referred you to someone or offered to recommend you. Show sincere gratitude. '
                'Be specific about what you are grateful for. '
                'Do NOT pitch your services. The message is about them, not you. '
                'End with an offer to reciprocate or keep them updated.'
            ),
        },
        'ghosted': {
            'tone': 'casual, light, and completely pressure-free',
            'goal': 're-open the conversation without any implied expectation',
            'cta': 'one easy, low-commitment question or observation — no ask',
            'instruction': (
                'This conversation went cold. Do NOT reference the previous unanswered message directly. '
                'Do NOT say "just following up" or "bumping this" or "I wanted to circle back". '
                'Open with something genuinely interesting — a relevant observation, a question about their work, or a short insight. '
                'Keep it under 80 words. Zero pressure.'
            ),
        },
        'cold_pitch': {
            'tone': 'polite, brief, and non-committal',
            'goal': 'acknowledge their message without engaging the pitch',
            'cta': 'none — do not invite further conversation about their offer',
            'instruction': (
                'This person reached out to sell something to the account owner. '
                'Write a brief, polite acknowledgment that closes the loop without rudeness. '
                'Do NOT express interest in their offer. Do NOT ask questions. '
                'Keep it to 2-3 sentences maximum. Firm but respectful.'
            ),
        },
        'dead': {
            'tone': 'light and conversational',
            'goal': 'reopen the relationship without any business agenda',
            'cta': 'a genuine question about what they have been working on',
            'instruction': (
                'This conversation has been inactive for a long time. Start completely fresh. '
                'Lead with curiosity about them, not your services. '
                'Do NOT reference old conversations unless there is a natural, positive callback. '
                'Keep it short and human.'
            ),
        },
        'unknown': {
            'tone': 'professional and curious',
            'goal': 'open the conversation and understand their context',
            'cta': 'one open-ended question about their work or goals',
            'instruction': (
                'There is no clear classification for this contact. '
                'Write a neutral, friendly message that opens dialogue without assuming any intent. '
                'Be curious and genuine.'
            ),
        },
    }
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.1-pro-preview")
    
    # Keep transcript compact to avoid prompt bloat and output truncation
    _MAX_TRANSCRIPT_MESSAGES = 20
    _MAX_CHARS_PER_MESSAGE = 300

    def _format_conversation_for_prompt(self, conversation_messages: Optional[List[Dict]]) -> str:
        """Format conversation transcript for prompt context (last N messages, trimmed)."""
        if not conversation_messages:
            return "No prior conversation messages available."

        # Take only the most recent messages to keep prompt compact
        recent = conversation_messages[-self._MAX_TRANSCRIPT_MESSAGES:]

        lines = []
        for msg in recent:
            if not isinstance(msg, dict):
                continue

            sender = str(msg.get("from", "Unknown") or "Unknown").strip()
            timestamp = str(msg.get("date", "") or "").strip()
            content = str(msg.get("content", "") or "").strip()
            if not content:
                continue

            # Trim very long individual messages
            if len(content) > self._MAX_CHARS_PER_MESSAGE:
                content = content[:self._MAX_CHARS_PER_MESSAGE] + "..."

            if timestamp:
                lines.append(f"[{timestamp}] {sender}: {content}")
            else:
                lines.append(f"{sender}: {content}")

        return "\n".join(lines) if lines else "No prior conversation messages available."

    def _build_products_block(self, products_services: list) -> str:
        """Format top 3 products/services for prompt context."""
        if not isinstance(products_services, list) or not products_services:
            return "Not specified"
        lines = []
        for p in products_services[:3]:
            if not isinstance(p, dict):
                continue
            name = str(p.get("name", "") or "").strip()
            desc = str(p.get("description", "") or "").strip()[:100]
            if name:
                lines.append(f"- {name}: {desc}" if desc else f"- {name}")
        return "\n".join(lines) if lines else "Not specified"

    def _build_prospect_summary(self, contact: Dict) -> str:
        """Build a concise prospect intel block for the prompt."""
        lines = []
        full_name = str(contact.get("full_name", "") or "").strip()
        company = str(contact.get("company", "") or "").strip()
        position = str(contact.get("position", "") or "").strip()
        buyer_stage = str(contact.get("buyer_stage", "") or "").strip()
        reason_summary = str(contact.get("reason_summary", "") or "").strip()
        evidence = contact.get("evidence", []) or []
        urgency = int(contact.get("urgency_score", 0) or 0)
        fit = int(contact.get("fit_score", 0) or 0)

        if full_name:
            lines.append(f"Name: {full_name}")
        if position:
            lines.append(f"Title: {position}")
        if company:
            lines.append(f"Company: {company}")
        if buyer_stage:
            lines.append(f"Buyer stage: {buyer_stage}")
        if reason_summary:
            lines.append(f"Classification rationale: {reason_summary}")
        if isinstance(evidence, list) and evidence:
            ev_str = " | ".join(str(e) for e in evidence[:3])
            lines.append(f"Key signals: {ev_str}")
        if urgency or fit:
            lines.append(f"Urgency: {urgency}/100 | Fit: {fit}/100")
        return "\n".join(lines) if lines else "No prospect data available"

    def generate_outreach(
        self,
        contact: Dict,
        user_context: Dict,
        message_type: str = "auto",
        conversation_messages: Optional[List[Dict]] = None,
    ) -> GeneratedMessage:
        """
        Generate personalized outreach message with context bundle.

        Args:
            contact: CRM contact data (behavioral_tag, reason_summary, evidence,
                     buyer_stage, urgency_score, fit_score, etc.)
            user_context: Dict with 'persona' sub-dict AND 'products_services' list.
                          Also accepts flat persona dict for backward compatibility.
            message_type: CRM tag override or 'auto'
            conversation_messages: Full conversation history

        Returns:
            GeneratedMessage with body, tone, and personalization_notes
        """
        if message_type == "auto":
            message_type = contact.get("behavioral_tag", "unknown")

        template = self.MESSAGE_TEMPLATES.get(message_type, self.MESSAGE_TEMPLATES["unknown"])

        # Support both flat-persona and bundle-with-persona formats
        if "persona" in user_context and isinstance(user_context["persona"], dict):
            persona = user_context["persona"]
            products_services = user_context.get("products_services", [])
        else:
            persona = user_context
            products_services = user_context.get("products_services", [])

        # ── Sender context ────────────────────────────────────────────────────
        user_bio = str(persona.get("professional_bio", "") or "").strip()[:300]
        user_tone = str(persona.get("tone_of_voice", "professional") or "professional").strip()
        expertise = ", ".join((persona.get("expertise_areas", []) or [])[:4])
        target_icp = str(persona.get("target_icp", "") or "").strip()[:150]
        products_block = self._build_products_block(products_services)

        # ── Contact identifiers ───────────────────────────────────────────────
        full_name = str(contact.get("full_name", "") or "").strip()
        first_name = full_name.split()[0] if full_name else "there"

        # ── Prospect intel block ──────────────────────────────────────────────
        prospect_block = self._build_prospect_summary(contact)

        # ── Conversation transcript ───────────────────────────────────────────
        transcript = self._format_conversation_for_prompt(conversation_messages)
        transcript_count = len(conversation_messages or [])

        prompt = f"""Write a short LinkedIn message from the account owner to {first_name}.

ACCOUNT OWNER: {user_bio or 'Professional'} | Expertise: {expertise or 'General'} | Tone: {user_tone}
Products: {products_block}

PROSPECT:
{prospect_block}
CRM tag: {message_type.replace('_', ' ').title()}

CONVERSATION ({transcript_count} messages, most recent last):
{transcript}

GOAL: {template['goal']}
Tone: {template['tone']} | CTA: {template['cta']}
{template['instruction']}

RULES:
- Reply with ONLY the message text. No labels, headers, or commentary.
- Be concise and direct. Default to 2-4 short sentences. Only go longer if the topic genuinely requires explanation.
- Every sentence must earn its place. No filler, no fluff, no generic pleasantries.
- Start with {first_name}'s name once. Reference a specific detail from the conversation.
- Continue naturally from the last exchange.
- End with one clear question or next step.
- No em dashes, bullet points, numbered lists, or emojis.
- Finish every sentence completely. Never stop mid-thought.

Message:"""

        try:
            body = self._generate_with_retry(prompt, first_name, message_type)

            return GeneratedMessage(
                subject="",
                body=body,
                tone=template["tone"],
                personalization_notes=(
                    f"Tag: {message_type} | Transcript msgs: {transcript_count} | "
                    f"Products in context: {len(products_services or [])} | "
                    f"Buyer stage: {contact.get('buyer_stage', 'unknown')}"
                ),
            )

        except Exception as e:
            print(f"[MessageGenerator] Generation error: {e}")
            return GeneratedMessage(
                subject="",
                body=self._fallback_message(first_name, message_type),
                tone=template["tone"],
                personalization_notes="Fallback message due to generation error",
            )

    def _looks_truncated(self, text: str) -> bool:
        """Check if text appears to be cut off mid-sentence."""
        if not text:
            return True
        text = text.rstrip()
        # Proper messages end with sentence-ending punctuation
        if text[-1] in '.?!"\'':
            return False
        # Ends with a word or comma — likely truncated
        return True

    def _generate_with_retry(self, prompt: str, first_name: str, message_type: str, max_attempts: int = 2) -> str:
        """Generate message with truncation detection and retry."""
        for attempt in range(max_attempts):
            response = self.client.models.generate_content(
                model=self.model,
                config=types.GenerateContentConfig(
                    temperature=0.45 + (attempt * 0.1),
                    max_output_tokens=2048,
                ),
                contents=prompt,
            )
            body = response.text.strip() if response.text else ""

            if body and not self._looks_truncated(body):
                return body

            print(f"[MessageGenerator] Attempt {attempt + 1}: output looks truncated ({body[-40:]!r}), retrying...")

        # All attempts produced truncated output — return best effort or fallback
        return body if body else self._fallback_message(first_name, message_type)
    
    def _fallback_message(self, contact_name: str, message_type: str) -> str:
        """Fallback message if generation fails."""
        fallbacks = {
            'warm_lead': f"Hi {contact_name}, really appreciate your interest. What does your current situation look like and what outcome are you hoping to achieve? That will help me point you in the right direction.",
            'cold_pitch': f"Hi {contact_name}, thanks for your message. This isn't something I'm looking for right now, but I appreciate you reaching out.",
            'ghosted': f"Hi {contact_name}, been a while. What have you been working on lately?",
            'client': f"Hi {contact_name}, wanted to check in on how things are going on your end. Any updates on the project, or anything you need from me?",
            'referrer': f"Hi {contact_name}, genuinely appreciate you making that connection. I'll keep you posted on how it goes and let me know if there's ever anything I can do on my end.",
            'dead': f"Hi {contact_name}, it has been some time. What are you focused on these days?",
            'unknown': f"Hi {contact_name}, good to connect. What are you working on at the moment?",
        }
        return fallbacks.get(message_type, fallbacks['unknown'])
    
    def generate_follow_up(self, original_message: str, days_since: int, contact: Dict) -> str:
        """Generate a follow-up message."""
        contact_name = contact.get('first_name', 'there')
        
        prompt = f"""
        Write a brief, non-pushy follow-up message to {contact_name}.
        
        Original message was sent {days_since} days ago:
        ""{original_message}""
        
        RULES:
        - Keep it under 50 words
        - Be casual, not desperate
        - Acknowledge they might be busy
        - One specific, easy-to-answer question
        - No "just following up" or "bumping this"
        
        Return ONLY the message text.
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                config=types.GenerateContentConfig(
                    temperature=0.6,
                    max_output_tokens=150
                ),
                contents=prompt
            )
            return response.text.strip() if response.text else f"Hey {contact_name}, quick question - have you had a chance to look at my last message? No rush, just wanted to make sure it didn't get buried."
        except Exception as e:
            print(f"[MessageGenerator] Follow-up error: {e}")
            return f"Hey {contact_name}, quick question - have you had a chance to look at my last message? No rush, just wanted to make sure it didn't get buried."
    
    def generate_value_message(self, contact: Dict, topic: str, user_expertise: str) -> str:
        """Generate a value-first message sharing insights."""
        contact_name = contact.get('first_name', 'there')
        
        prompt = f"""
        Write a value-first LinkedIn message to {contact_name} sharing insights about {topic}.
        
        SENDER EXPERTISE: {user_expertise}
        
        RULES:
        - Lead with genuine value, no ask
        - Share a specific insight or observation
        - Keep it under 100 words
        - End with an open-ended question (not a CTA)
        - Sound like a thoughtful peer, not a vendor
        
        Return ONLY the message text.
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=200
                ),
                contents=prompt
            )
            return response.text.strip() if response.text else f"Hi {contact_name}, I've been thinking about {topic} and wanted to share something that might be useful for your work. {self._get_generic_insight(topic)} What are your thoughts?"
        except Exception as e:
            print(f"[MessageGenerator] Value message error: {e}")
            return f"Hi {contact_name}, I've been thinking about {topic} and wanted to share something that might be useful for your work. What trends are you seeing in this space?"
    
    def _get_generic_insight(self, topic: str) -> str:
        """Get a generic insight for fallback."""
        insights = {
            'ai': "The companies seeing the best ROI aren't the ones with the biggest models, but the ones with the cleanest data pipelines.",
            'marketing': "Authenticity is becoming the only moat. The brands winning are the ones willing to show the messy middle.",
            'leadership': "The best leaders I know aren't the loudest in the room - they're the ones who ask the best questions.",
            'sales': "Discovery is the new closing. The reps hitting quota are spending 70% of their time understanding, not pitching."
        }
        return insights.get(topic.lower(), f"I've noticed the most successful approaches to {topic} focus on consistency over intensity.")


def generate_outreach_message(
    contact: Dict,
    user_context: Dict,
    message_type: str = "auto",
    conversation_messages: Optional[List[Dict]] = None,
) -> Dict:
    """
    Convenience function to generate outreach message.
    
    Args:
        contact: CRM contact data
        user_context: User's persona context
        message_type: Type of message or 'auto'
        
    Returns:
        Dictionary with message details
    """
    try:
        generator = MessageGenerator()
        result = generator.generate_outreach(
            contact,
            user_context,
            message_type,
            conversation_messages=conversation_messages,
        )
        
        return {
            "success": True,
            "message": result.body,
            "tone": result.tone,
            "personalization_notes": result.personalization_notes
        }
    except Exception as e:
        print(f"[generate_outreach_message] Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Hi, good to connect. What are you working on at the moment?"
        }


if __name__ == "__main__":
    print("[MessageGenerator] Module loaded successfully")

    test_contact = {
        "full_name": "Sarah Chen",
        "company": "TechCorp",
        "position": "VP of Marketing",
        "behavioral_tag": "warm_lead",
        "reason_summary": "Prospect asked about pricing for the AI content suite and requested a demo.",
        "evidence": ["asked about pricing", "requested a demo link"],
        "buyer_stage": "decision",
        "urgency_score": 75,
        "fit_score": 80,
    }

    test_user = {
        "persona": {
            "professional_bio": "AI consultant helping B2B marketers build content systems that scale.",
            "tone_of_voice": "direct and human",
            "expertise_areas": ["AI content", "LinkedIn strategy", "B2B marketing"],
            "target_icp": "Marketing leaders at 50-500 person companies",
        },
        "products_services": [
            {"name": "AI Content Suite", "description": "Done-for-you LinkedIn content system with weekly posts and analytics."},
        ],
    }

    result = generate_outreach_message(test_contact, test_user)
    print(f"\n[Generated Message]:\n{result['message']}")
    print(f"\n[Notes]: {result.get('personalization_notes', '')}")
