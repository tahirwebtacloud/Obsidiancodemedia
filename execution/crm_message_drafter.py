"""
crm_message_drafter.py
----------------------
Generate personalized draft messages for CRM contacts via LLM.

Style constraints enforced in the system prompt:
  - No em dashes (—), no asterisks (*), no markdown formatting
  - Professional but conversational tone
  - Short paragraphs (2-3 sentences max)
  - Clear call-to-action at the end
  - Personalized based on conversation history and contact profile

Uses OpenRouter (free) as primary, Gemini as fallback.
"""

from typing import Dict, List, Optional

from execution.gemini_structured import call_llm_text


_SYSTEM_PROMPT = """You are an expert B2B sales copywriter who drafts personalized LinkedIn messages.

STRICT STYLE RULES (MUST follow):
- NO em dashes. Use commas, periods, or "and" instead.
- NO asterisks or markdown formatting of any kind.
- NO bullet points or numbered lists in the message.
- Keep paragraphs to 2-3 sentences maximum.
- Professional but conversational tone - like talking to a colleague.
- Total message length: 80-150 words.
- End with a clear, specific call-to-action (suggest a call, meeting, or specific next step).
- Reference something specific from their profile or conversation to show you paid attention.
- Do NOT start with "I hope this message finds you well" or similar generic openers.
- Do NOT use exclamation marks excessively (max 1 in entire message).

IMPORTANT: Return ONLY the message text. No subject line, no "Dear X", no signature block.
Start directly with the message body."""


def generate_draft_message(
    user_profile_summary: str,
    user_products: str,
    contact_info: Dict,
    conversation_thread: List[Dict] = None,
) -> str:
    """Generate a personalized draft message for a CRM contact.

    Args:
        user_profile_summary: User's own profile summary text.
        user_products: User's products/services description.
        contact_info: Dict with first_name, last_name, title, company, intent_points, tag.
        conversation_thread: Optional list of message dicts for context.

    Returns:
        Draft message string, or fallback template on failure.
    """
    # Build contact description
    name = f"{contact_info.get('first_name', '')} {contact_info.get('last_name', '')}".strip()
    title = contact_info.get("title", "")
    company = contact_info.get("company", "")
    tag = contact_info.get("tag", "prospect")
    intent_points = contact_info.get("intent_points", [])

    contact_desc = f"Name: {name}"
    if title:
        contact_desc += f"\nTitle: {title}"
    if company:
        contact_desc += f"\nCompany: {company}"
    if tag:
        contact_desc += f"\nRelationship Tag: {tag}"
    if intent_points:
        contact_desc += f"\nIntent Summary: {'; '.join(intent_points[:3])}"

    # Format recent conversation if available
    conv_context = ""
    if conversation_thread:
        recent = conversation_thread[-10:]  # Last 10 messages
        lines = []
        for msg in recent:
            sender = msg.get("from", "Unknown")
            content = msg.get("content", "")
            if content:
                lines.append(f"{sender}: {content[:200]}")
        if lines:
            conv_context = f"\n\n## Recent Conversation\n" + "\n".join(lines)

    goal = "re-engage" if tag == "ghosted" else "advance the relationship"
    user_prompt = (
        f"## My Profile\n{user_profile_summary}\n\n"
        f"## My Products/Services\n{user_products}\n\n"
        f"## Contact to Message\n{contact_desc}"
        f"{conv_context}\n\n"
        f"Write a personalized LinkedIn message to {name or 'this contact'} "
        f"based on the above context. The goal is to {goal} "
        f"and explore potential business opportunities."
    )

    message = call_llm_text(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=500,
        temperature=0.5,
    )

    if message:
        # Post-process: enforce style rules
        message = message.replace("—", ",")
        message = message.replace("**", "")
        message = message.replace("*", "")
        message = message.replace("###", "")
        message = message.replace("##", "")
        message = message.replace("#", "")
        # Strip any "Subject:" or "Dear X," prefix
        lines = message.strip().split("\n")
        while lines and (
            lines[0].lower().startswith("subject:") or
            lines[0].lower().startswith("dear ") or
            lines[0].lower().startswith("hi ") and len(lines[0]) < 20
        ):
            lines.pop(0)
        return "\n".join(lines).strip()

    # Fallback template
    first = contact_info.get("first_name", "there")
    return (
        f"Hi {first}, I noticed we are connected on LinkedIn and "
        f"wanted to reach out. "
        f"{'I see you work at ' + company + ' and ' if company else ''}"
        f"I think there could be some interesting synergies between what "
        f"we do.\n\n"
        f"Would you be open to a brief call this week to explore?"
    )
