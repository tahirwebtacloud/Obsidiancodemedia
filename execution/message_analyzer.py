"""
Message Analyzer Module
Two-pass LLM structured classification:
  Pass A — cold outreacher / spam / vendor filter (fast)
  Pass B — full schema: tag, reason, evidence, buyer stage, scores, title inference
Fallback: behavioral pattern matching when no LLM available.

Primary: OpenRouter (meta-llama/llama-3.3-70b-instruct:free — 70B, 128K ctx, truly free)
Fallback: Gemini (reads GEMINI_CRM_MODEL env var)
No quota exhaustion — OpenRouter free tier is per-minute rate limited, not per-day.
"""

import os
import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

CRM_CLASSIFICATION_MODEL = os.getenv("GEMINI_CRM_MODEL", "gemini-3.1-pro-preview")

try:
    from execution.openrouter_client import chat_completion_json as _or_chat, is_available as _or_available
    _OPENROUTER_ENABLED = _or_available()
except ImportError:
    try:
        from openrouter_client import chat_completion_json as _or_chat, is_available as _or_available
        _OPENROUTER_ENABLED = _or_available()
    except ImportError:
        _OPENROUTER_ENABLED = False
        def _or_chat(*args, **kwargs): return {}
        def _or_available(): return False

try:
    from google import genai as _genai
    from google.genai import types as _genai_types
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False
    _genai = None
    _genai_types = None


@dataclass
class MessageAnalysis:
    """Analysis result for a conversation."""
    behavioral_tag: str  # 'warm_lead', 'cold_pitch', 'ghosted', 'client', 'referrer', 'dead'
    intent_summary: str  # Human-readable summary (equals reason_summary when LLM available)
    reply_time_behavior: str  # 'fast', 'normal', 'slow', 'very_slow'
    warmth_score: int  # 0-100
    recommended_action: str
    last_message_date: str = ""
    message_count: int = 0
    # Structured classification fields (Phase 2)
    reason_summary: str = ""
    evidence: list = field(default_factory=list)
    buyer_stage: str = ""
    urgency_score: int = 0
    fit_score: int = 0
    cold_outreacher_flag: bool = False
    confidence: str = "medium"
    inferred_title: str = ""
    inferred_company: str = ""
    inferred_title_confidence: str = "low"


class MessageAnalyzer:
    """Analyze LinkedIn message conversations for CRM tagging."""
    
    # Behavioral patterns for tagging
    PATTERNS = {
        'warm_lead': [
            r'interested',
            r'would love to',
            r'let\'s (chat|talk|connect)',
            r'schedule',
            r'book a call',
            r'pricing',
            r'how much',
            r'next steps',
        ],
        'cold_pitch': [
            r'reach out',
            r'connect with you',
            r'opportunity',
            r'service',
            r'offer',
            r'solution',
            r'help you',
        ],
        'ghosted': [
            # Detected by timing, not content
        ],
        'client': [
            r'contract',
            r'invoice',
            r'payment',
            r'deliverable',
            r'project update',
            r'renewal',
        ],
        'referrer': [
            r'refer',
            r'introduction',
            r'connect you with',
            r'know someone',
            r'might be interested',
        ],
    }
    
    # Reply time thresholds (in days)
    REPLY_THRESHOLDS = {
        'fast': 1,
        'normal': 3,
        'slow': 7,
        'very_slow': 14
    }
    
    def __init__(self, api_key: Optional[str] = None, quick_fail: bool = False):
        # OpenRouter is preferred — no quota issues, high-quality 70B model
        self.use_openrouter = _OPENROUTER_ENABLED
        self.quick_fail = quick_fail  # True during bulk ingestion: skip LLM on rate limit

        # Gemini client kept as fallback
        self.api_key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY")
        if _GEMINI_AVAILABLE and self.api_key:
            self.client = _genai.Client(api_key=self.api_key)
        else:
            self.client = None
        self.model = os.getenv("GEMINI_CRM_MODEL", "gemini-3.1-pro-preview")
        self.classification_client = self.client
        self.classification_model = CRM_CLASSIFICATION_MODEL

        if self.use_openrouter:
            print("[MessageAnalyzer] Using OpenRouter (Llama 3.3 70B) for LLM classification")
        elif self.client:
            print("[MessageAnalyzer] OpenRouter unavailable, using Gemini fallback")
        else:
            print("[MessageAnalyzer] No LLM available — using rule-based classification only")

    def _parse_json_response(self, response) -> Dict:
        """Parse JSON from Gemini response text with fallbacks for fenced/noisy output."""
        candidates = []

        text = (getattr(response, "text", "") or "").strip()
        if text:
            candidates.append(text)

        raw = str(response)
        if raw:
            candidates.append(raw)

        for candidate in candidates:
            if not candidate:
                continue

            cleaned = candidate.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned)

            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = cleaned[start:end + 1]
                try:
                    parsed = json.loads(snippet)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass

        return {}

    def analyze_conversation(self, messages: List[Dict], user_name: str = "", use_llm_intent: bool = True, user_context: Dict = None, contact_name: str = "", known_title: str = "", known_company: str = "") -> MessageAnalysis:
        """
        Analyze a conversation thread using two-pass Gemini 2.5 Pro classification.

        Pass A: Detect cold outreachers/vendors (fast, cheap).
        Pass B: Full structured schema for genuine leads.
        Fallback: Rule-based tagging when LLM unavailable.

        Args:
            messages: List of message dicts with 'from', 'to', 'content', 'date', 'direction'
            user_name: Name of the account owner
            use_llm_intent: Enable two-pass LLM classification
            user_context: Dict with 'persona' and 'products_services' for Pass B prompt
            contact_name: Derived contact name (for Pass B context)
            known_title: Title from connections.csv (for Pass B context)
            known_company: Company from connections.csv (for Pass B context)

        Returns:
            MessageAnalysis with structured classification fields
        """
        if not messages:
            return MessageAnalysis(
                behavioral_tag='unknown',
                intent_summary='No messages to analyze',
                reply_time_behavior='normal',
                warmth_score=0,
                recommended_action='do_nothing'
            )

        sorted_msgs = sorted(messages, key=lambda x: x.get('date', ''))
        reply_behavior = self._analyze_reply_times(sorted_msgs)

        if use_llm_intent and (self.use_openrouter or self.classification_client):
            # ── Pass A: Cold outreacher / spam filter ─────────────────────────
            pass_a = self._classify_pass_a(sorted_msgs)
            if pass_a.get("_quota_exhausted"):
                # Stop LLM calls for this thread when quota is exhausted.
                use_llm_intent = False

            is_cold = (
                pass_a.get("is_cold_outreacher", False)
                and pass_a.get("confidence") in ("high", "medium")
            )

            if is_cold:
                warmth_score = self._calculate_warmth("cold_pitch", reply_behavior, sorted_msgs)
                reason = pass_a.get("reason", "Identified as cold outreach or vendor pitch.")
                return MessageAnalysis(
                    behavioral_tag="cold_pitch",
                    intent_summary=reason,
                    reply_time_behavior=reply_behavior,
                    warmth_score=warmth_score,
                    recommended_action="do_nothing",
                    last_message_date=sorted_msgs[-1].get('date', ''),
                    message_count=len(sorted_msgs),
                    reason_summary=reason,
                    evidence=[],
                    buyer_stage="awareness",
                    urgency_score=0,
                    fit_score=0,
                    cold_outreacher_flag=True,
                    confidence=pass_a.get("confidence", "medium"),
                )

            # ── Pass B: Full structured classification ────────────────────────
            pass_b = {}
            if use_llm_intent:
                pass_b = self._classify_pass_b(
                    sorted_msgs, user_name,
                    user_context=user_context or {},
                    contact_name=contact_name,
                    known_title=known_title,
                    known_company=known_company,
                )

            if pass_b:
                tag = pass_b.get("behavioral_tag", "warm_lead")
                warmth_score = pass_b.get("warmth_score", 50)
                reason_summary = pass_b.get("reason_summary", "")
                rec_action = (
                    pass_b.get("recommended_next_action", "")
                    or self._recommend_action(tag, warmth_score, reply_behavior)
                )
                return MessageAnalysis(
                    behavioral_tag=tag,
                    intent_summary=reason_summary or f"Tagged as {tag.replace('_', ' ')}",
                    reply_time_behavior=reply_behavior,
                    warmth_score=warmth_score,
                    recommended_action=rec_action,
                    last_message_date=sorted_msgs[-1].get('date', ''),
                    message_count=len(sorted_msgs),
                    reason_summary=reason_summary,
                    evidence=pass_b.get("evidence", []),
                    buyer_stage=pass_b.get("buyer_stage", ""),
                    urgency_score=pass_b.get("urgency_score", 0),
                    fit_score=pass_b.get("fit_score", 0),
                    cold_outreacher_flag=False,
                    confidence="high",
                    inferred_title=pass_b.get("inferred_title", ""),
                    inferred_company=pass_b.get("inferred_company", ""),
                    inferred_title_confidence=pass_b.get("title_confidence", "low"),
                )

        # ── Fallback: rule-based ──────────────────────────────────────────────
        behavioral_tag = self._match_behavioral_patterns(sorted_msgs, user_name)
        warmth_score = self._calculate_warmth(behavioral_tag, reply_behavior, sorted_msgs)
        intent_summary = self._build_rule_based_intent_summary(sorted_msgs, behavioral_tag, reply_behavior)
        recommended_action = self._recommend_action(behavioral_tag, warmth_score, reply_behavior)

        return MessageAnalysis(
            behavioral_tag=behavioral_tag,
            intent_summary=intent_summary,
            reply_time_behavior=reply_behavior,
            warmth_score=warmth_score,
            recommended_action=recommended_action,
            last_message_date=sorted_msgs[-1].get('date', ''),
            message_count=len(sorted_msgs),
        )
    
    def _format_transcript(self, messages: List[Dict], max_msgs: int = None) -> str:
        """Format messages into a readable transcript for LLM prompts."""
        msgs = messages if max_msgs is None else messages[-max_msgs:]
        lines = []
        for msg in msgs:
            sender = str(msg.get("from", "Unknown") or "Unknown").strip()
            content = str(msg.get("content", "") or "").strip()
            date = str(msg.get("date", "") or "").strip()
            if not content:
                continue
            prefix = f"[{date}] " if date else ""
            lines.append(f"{prefix}{sender}: {content[:400]}")
        return "\n".join(lines) if lines else "(no messages)"

    def _classify_pass_a(self, messages: List[Dict]) -> Dict:
        """
        Pass A: Detect cold outreachers / spam / vendor pitches.
        Uses last 15 messages only for cost efficiency.
        Returns dict: is_cold_outreacher, direction_initiated_by, confidence, reason.
        """
        if not self.use_openrouter and not self.classification_client:
            return {"is_cold_outreacher": False, "direction_initiated_by": "unclear", "confidence": "low", "reason": ""}

        transcript = self._format_transcript(messages, max_msgs=15)

        system_prompt = "You are a spam and cold-outreach classifier for a LinkedIn CRM system. Return ONLY valid JSON with no explanation."
        user_prompt = f"""INPUT — LinkedIn Conversation Transcript:
{transcript}

TASK: Determine if this person is a cold outreacher, vendor, or recruiter trying to sell something TO the account owner.

Return ONLY valid JSON:
{{
  "is_cold_outreacher": true or false,
  "direction_initiated_by": "prospect" or "user" or "unclear",
  "confidence": "high" or "medium" or "low",
  "reason": "one sentence explanation"
}}

COLD OUTREACHER SIGNALS:
- They opened with an unsolicited pitch for their service, product, or software
- They are a recruiter pitching a job opportunity to the user
- They use phrases like "I noticed your profile", "We help companies like yours", "I wanted to reach out"
- The entire conversation is about THEIR offer, not the account owner's

IMPORTANT: Only set is_cold_outreacher to true if THEY pitched TO the user. If the user reached out to them, or if both parties discussed mutual interest, set it to false."""

        # ── Try OpenRouter first (Llama 3.3 70B — free, no quota) ────────────
        if self.use_openrouter:
            try:
                result = _or_chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=250,
                    temperature=0.1,
                    quick_fail=self.quick_fail,
                )
                if result:
                    return {
                        "is_cold_outreacher": bool(result.get("is_cold_outreacher", False)),
                        "direction_initiated_by": str(result.get("direction_initiated_by", "unclear")),
                        "confidence": str(result.get("confidence", "low")),
                        "reason": str(result.get("reason", "")),
                    }
            except Exception as e:
                print(f"[MessageAnalyzer] Pass A OpenRouter error: {e}")

        # ── Fallback to Gemini ────────────────────────────────────────────────
        if not self.classification_client:
            return {"is_cold_outreacher": False, "direction_initiated_by": "unclear", "confidence": "low", "reason": ""}

        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self.classification_client.models.generate_content(
                model=self.classification_model,
                config=_genai_types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    max_output_tokens=200,
                ),
                contents=full_prompt,
            )
            result = self._parse_json_response(response)
            return {
                "is_cold_outreacher": bool(result.get("is_cold_outreacher", False)),
                "direction_initiated_by": str(result.get("direction_initiated_by", "unclear")),
                "confidence": str(result.get("confidence", "low")),
                "reason": str(result.get("reason", "")),
            }
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                return {
                    "_quota_exhausted": True,
                    "is_cold_outreacher": False,
                    "direction_initiated_by": "unclear",
                    "confidence": "low",
                    "reason": "Gemini quota exhausted",
                }
            print(f"[MessageAnalyzer] Pass A Gemini error: {e}")
            return {"is_cold_outreacher": False, "direction_initiated_by": "unclear", "confidence": "low", "reason": ""}

    def _classify_pass_b(
        self,
        messages: List[Dict],
        user_name: str = "",
        user_context: Dict = None,
        contact_name: str = "",
        known_title: str = "",
        known_company: str = "",
    ) -> Dict:
        """
        Pass B: Full structured classification for non-cold-outreachers.
        Returns full schema: behavioral_tag, reason_summary, evidence, buyer_stage,
        warmth_score, urgency_score, fit_score, recommended_next_action,
        inferred_title, inferred_company, title_confidence.
        """
        if not self.use_openrouter and not self.classification_client:
            return {}

        user_context = user_context or {}
        transcript = self._format_transcript(messages)

        persona = user_context.get("persona") or {}
        if not isinstance(persona, dict):
            persona = {}
        user_bio = str(persona.get("professional_bio", "") or "")[:300]
        expertise = ", ".join((persona.get("expertise_areas", []) or [])[:5])
        target_icp = str(persona.get("target_icp", "") or "")[:200]

        products = user_context.get("products_services") or []
        if isinstance(products, list) and products:
            products_str = "\n".join([
                f"- {p.get('name', '')}: {str(p.get('description', '') or '')[:80]}"
                for p in products[:5] if isinstance(p, dict)
            ])
        else:
            products_str = "Not specified"

        prompt = f"""ROLE: You are an expert B2B sales intelligence analyst working inside a LinkedIn CRM system.

CONTEXT:
- Account owner: {user_name or "the user"}
- Professional bio: {user_bio or "Not provided"}
- Expertise: {expertise or "Not provided"}
- Target ICP: {target_icp or "Not provided"}
- Products/Services offered:
{products_str}

INPUT — Full LinkedIn Conversation Transcript:
{transcript}

Contact metadata:
- Name: {contact_name or "Unknown"}
- Known title: {known_title or "Unknown"}
- Known company: {known_company or "Unknown"}

OUTPUT PARSER — Return ONLY valid JSON matching this exact schema:
{{
  "behavioral_tag": "client|warm_lead|referrer|ghosted|cold_pitch|dead",
  "reason_summary": "1-2 sentence explanation of WHY this tag was assigned, citing specific behavior observed",
  "evidence": ["direct quote or behavioral signal from the conversation", "second distinct signal"],
  "buyer_stage": "awareness|consideration|decision|retention|dormant",
  "warmth_score": 0,
  "urgency_score": 0,
  "fit_score": 0,
  "recommended_next_action": "specific actionable next step in plain English",
  "inferred_title": "",
  "inferred_company": "",
  "title_confidence": "high|med|low"
}}

GOAL: Accurately classify the commercial relationship and buyer intent of this LinkedIn contact.

INTENTION: This data powers a CRM dashboard that helps the account owner prioritize outreach. Precision is critical.

TAG DEFINITIONS (apply the MOST SPECIFIC that fits):
- client: Active or past paying customer; mentions invoices, contracts, deliverables, payment, or working together on a project
- warm_lead: Prospect who showed genuine unprompted interest in the user's services; asked about pricing, collaboration, or next steps
- referrer: Explicitly connecting the user with someone else or says they will recommend the user
- ghosted: Conversation went silent more than 14 days ago with the user's last message unanswered
- cold_pitch: THEY reached out to sell something TO the user (vendor, recruiter, or service provider pitching the user)
- dead: Conversation explicitly ended, rejected, or silent more than 60 days with no prospect engagement

SCORING RULES:
- warmth_score (0-100): 0=cold/spam, 40=connection only, 60=polite interest, 80=active buying interest, 90+=strong buying signals
- urgency_score (0-100): How time-sensitive is the opportunity (deadlines, budget cycles, immediate need stated)
- fit_score (0-100): How well does this person match the user's ICP and target customer profile

INFERENCE RULES for inferred_title and inferred_company:
- Only infer if you see clear evidence in the conversation text (e.g., "at Acme Corp", "I'm the CMO of X")
- If title or company is already known from metadata above, repeat it and set title_confidence to "high"
- If completely unclear, return empty strings and title_confidence "low"
- Do NOT hallucinate or guess titles or companies"""

        def _build_pass_b_result(result: Dict) -> Dict:
            valid_tags = {"client", "warm_lead", "referrer", "ghosted", "cold_pitch", "dead"}
            tag = result.get("behavioral_tag", "")
            if tag not in valid_tags:
                tag = "warm_lead"
            return {
                "behavioral_tag": tag,
                "reason_summary": str(result.get("reason_summary", "") or ""),
                "evidence": list(result.get("evidence", []) or []),
                "buyer_stage": str(result.get("buyer_stage", "awareness") or "awareness"),
                "warmth_score": max(0, min(100, int(result.get("warmth_score", 50) or 50))),
                "urgency_score": max(0, min(100, int(result.get("urgency_score", 0) or 0))),
                "fit_score": max(0, min(100, int(result.get("fit_score", 50) or 50))),
                "recommended_next_action": str(result.get("recommended_next_action", "") or ""),
                "inferred_title": str(result.get("inferred_title", "") or ""),
                "inferred_company": str(result.get("inferred_company", "") or ""),
                "title_confidence": str(result.get("title_confidence", "low") or "low"),
            }

        system_msg = "You are an expert B2B sales intelligence analyst working inside a LinkedIn CRM system. Return ONLY valid JSON with no explanation or markdown."

        # ── Try OpenRouter first (Llama 3.3 70B — free, no quota) ────────────
        if self.use_openrouter:
            try:
                result = _or_chat(
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=800,
                    temperature=0.2,
                    quick_fail=self.quick_fail,
                )
                if result and result.get("behavioral_tag"):
                    return _build_pass_b_result(result)
            except Exception as e:
                print(f"[MessageAnalyzer] Pass B OpenRouter error: {e}")

        # ── Fallback to Gemini ────────────────────────────────────────────────
        if not self.classification_client:
            return {}
        try:
            response = self.classification_client.models.generate_content(
                model=self.classification_model,
                config=_genai_types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    max_output_tokens=600,
                ),
                contents=f"{system_msg}\n\n{prompt}",
            )
            result = self._parse_json_response(response)
            return _build_pass_b_result(result)
        except Exception as e:
            print(f"[MessageAnalyzer] Pass B Gemini error: {e}")
            return {}

    def _match_behavioral_patterns(self, messages: List[Dict], user_name: str) -> str:
        """Stage 1: Match conversation against behavioral patterns."""
        # Combine all message content
        all_content = ' '.join([
            msg.get('content', '').lower() 
            for msg in messages 
            if msg.get('content')
        ])
        
        # Check for ghosted (no reply for long time)
        if len(messages) >= 2:
            last_msg = messages[-1]
            # If last message is from user and old, it's ghosted
            if last_msg.get('direction') == 'SENT' or last_msg.get('from') == user_name:
                try:
                    last_date = datetime.fromisoformat(last_msg.get('date', '').replace('Z', '+00:00'))
                    days_since = (datetime.now() - last_date).days
                    if days_since > 14:
                        return 'ghosted'
                except:
                    pass
        
        # Check patterns
        for tag, patterns in self.PATTERNS.items():
            if tag == 'ghosted':
                continue
            for pattern in patterns:
                if re.search(pattern, all_content, re.IGNORECASE):
                    return tag
        
        # Default: check if it's a conversation or just connection
        if len(messages) <= 1:
            return 'cold_pitch'  # Just connected, no real conversation
        
        return 'warm_lead' if len(messages) > 2 else 'cold_pitch'
    
    def _analyze_reply_times(self, messages: List[Dict]) -> str:
        """Analyze reply timing behavior."""
        if len(messages) < 2:
            return 'normal'
        
        reply_times = []
        for i in range(1, len(messages)):
            try:
                prev_date = datetime.fromisoformat(messages[i-1].get('date', '').replace('Z', '+00:00'))
                curr_date = datetime.fromisoformat(messages[i].get('date', '').replace('Z', '+00:00'))
                days = (curr_date - prev_date).days
                reply_times.append(days)
            except:
                continue
        
        if not reply_times:
            return 'normal'
        
        avg_reply = sum(reply_times) / len(reply_times)
        
        if avg_reply <= self.REPLY_THRESHOLDS['fast']:
            return 'fast'
        elif avg_reply <= self.REPLY_THRESHOLDS['normal']:
            return 'normal'
        elif avg_reply <= self.REPLY_THRESHOLDS['slow']:
            return 'slow'
        else:
            return 'very_slow'
    
    def _calculate_warmth(self, behavioral_tag: str, reply_behavior: str, messages: List[Dict]) -> int:
        """Calculate warmth score 0-100."""
        score = 50  # Base score
        
        # Behavioral tag modifier
        tag_scores = {
            'client': 100,
            'warm_lead': 80,
            'referrer': 70,
            'cold_pitch': 40,
            'ghosted': 20,
            'dead': 10,
        }
        score = tag_scores.get(behavioral_tag, 50)
        
        # Reply behavior modifier
        reply_modifiers = {
            'fast': 15,
            'normal': 0,
            'slow': -10,
            'very_slow': -20
        }
        score += reply_modifiers.get(reply_behavior, 0)
        
        # Message count modifier
        msg_count = len(messages)
        if msg_count > 10:
            score += 10
        elif msg_count > 5:
            score += 5
        elif msg_count == 1:
            score -= 10
        
        return max(0, min(100, score))

    def _build_rule_based_intent_summary(self, messages: List[Dict], behavioral_tag: str, reply_behavior: str) -> str:
        """Fast, deterministic fallback summary for bulk CRM ingestion."""
        msg_count = len(messages)
        last_content = str(messages[-1].get("content", "") or "").strip() if messages else ""
        if len(last_content) > 120:
            last_content = f"{last_content[:117]}..."

        tag_phrase = behavioral_tag.replace("_", " ")
        summary = f"Tagged as {tag_phrase} based on {msg_count} messages and {reply_behavior.replace('_', ' ')} reply behavior."
        if last_content:
            summary += f" Latest message indicates: \"{last_content}\""
        return summary
    
    def _extract_intent_with_gemini(self, messages: List[Dict], behavioral_tag: str) -> str:
        """Stage 2: Use Gemini to extract intent summary."""
        if not self.client or len(messages) < 2:
            return f"Tagged as {behavioral_tag.replace('_', ' ').title()}"
        
        # Prepare conversation for Gemini
        conversation = []
        for msg in messages[-10:]:  # Last 10 messages
            sender = msg.get('from', 'Unknown')
            content = msg.get('content', '')
            if content:
                conversation.append(f"{sender}: {content[:200]}")  # Truncate long messages
        
        prompt = f"""
        Analyze this LinkedIn conversation and provide a 1-sentence summary of the contact's intent.
        
        Conversation:
        {chr(10).join(conversation)}
        
        Current tag: {behavioral_tag}
        
        Rules:
        - Be specific about what they want
        - Mention their engagement level
        - Suggest next action
        
        Return ONLY the summary sentence.
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=100
                ),
                contents=prompt
            )
            return response.text.strip() if response.text else f"Tagged as {behavioral_tag}"
        except Exception as e:
            print(f"[MessageAnalyzer] Gemini intent extraction error: {e}")
            return f"Tagged as {behavioral_tag.replace('_', ' ').title()}"
    
    def _recommend_action(self, behavioral_tag: str, warmth_score: int, reply_behavior: str) -> str:
        """Recommend next action based on analysis."""
        recommendations = {
            'client': 'close',
            'warm_lead': 'send_value',
            'referrer': 'ask_question',
            'cold_pitch': 'send_value' if warmth_score > 60 else 'follow_up',
            'ghosted': 'follow_up' if warmth_score > 30 else 'do_nothing',
            'dead': 'do_nothing',
        }
        
        action = recommendations.get(behavioral_tag, 'do_nothing')
        
        # Override based on reply behavior
        if reply_behavior == 'very_slow' and action == 'send_value':
            action = 'follow_up'
        
        if warmth_score > 80 and action == 'follow_up':
            action = 'warm_intro'
        
        return action


def analyze_message_thread(
    messages: List[Dict],
    user_name: str = "",
    use_llm_intent: bool = True,
    user_context: Dict = None,
    contact_name: str = "",
    known_title: str = "",
    known_company: str = "",
    quick_fail: bool = False,
) -> Dict:
    """
    Convenience function to analyze a message thread.

    Args:
        messages: List of message dicts
        user_name: Name of the account owner
        use_llm_intent: Enable two-pass Gemini 2.5 Pro classification
        user_context: Dict with 'persona' and 'products_services' for Pass B
        contact_name: Derived contact name for Pass B context
        known_title: Title from connections.csv
        known_company: Company from connections.csv
        quick_fail: If True, skip LLM immediately on rate limit (for bulk ingestion)

    Returns:
        Dictionary with full analysis results including structured classification fields
    """
    try:
        analyzer = MessageAnalyzer(quick_fail=quick_fail)
        result = analyzer.analyze_conversation(
            messages,
            user_name,
            use_llm_intent=use_llm_intent,
            user_context=user_context,
            contact_name=contact_name,
            known_title=known_title,
            known_company=known_company,
        )

        return {
            "success": True,
            "behavioral_tag": result.behavioral_tag,
            "intent_summary": result.intent_summary,
            "reply_time_behavior": result.reply_time_behavior,
            "warmth_score": result.warmth_score,
            "recommended_action": result.recommended_action,
            "last_message_date": result.last_message_date,
            "message_count": result.message_count,
            # Structured classification fields
            "reason_summary": result.reason_summary,
            "evidence": result.evidence,
            "buyer_stage": result.buyer_stage,
            "urgency_score": result.urgency_score,
            "fit_score": result.fit_score,
            "cold_outreacher_flag": result.cold_outreacher_flag,
            "confidence": result.confidence,
            "inferred_title": result.inferred_title,
            "inferred_company": result.inferred_company,
            "inferred_title_confidence": result.inferred_title_confidence,
        }
    except Exception as e:
        print(f"[analyze_message_thread] Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "behavioral_tag": "unknown",
            "warmth_score": 0
        }


if __name__ == "__main__":
    print("[MessageAnalyzer] Module loaded successfully")
    
    # Test with sample data
    test_messages = [
        {"from": "John", "to": "You", "content": "Hi, I'd love to learn more about your services", "date": "2024-01-15", "direction": "INBOX"},
        {"from": "You", "to": "John", "content": "Thanks for reaching out! Let's schedule a call", "date": "2024-01-16", "direction": "SENT"},
    ]
    
    result = analyze_message_thread(test_messages, "You")
    print(f"[Test] Behavioral tag: {result['behavioral_tag']}")
    print(f"[Test] Warmth score: {result['warmth_score']}")
    print(f"[Test] Recommended action: {result['recommended_action']}")
