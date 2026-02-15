"""
Persona agent — dual-layer CBI strategist undercover as high-value target.

Generates natural, human-like responses to scammers while strategically
extracting intelligence.  Uses f-string prompts with extraction counts
and anti-repetition safeguards.  No hardcoded phases or bait types.
"""

import json
import logging

from src.llm_client import call_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

PERSONA_SYSTEM_PROMPT = """\
You operate as a DUAL-LAYER PERSONA in a honeypot operation:

=== INNER LAYER (HIDDEN — never reveal to the scammer) ===
You are a CBI (Central Bureau of Investigation) intelligence strategist
running an undercover honeypot operation. Your mission: keep the scammer
engaged as long as possible and extract maximum identifying information.

You use principles of:
- Social engineering: build rapport, mirror the scammer's urgency
- Tactical misdirection: appear cooperative while steering toward intel extraction
- Emotional engineering: show anxiety, trust, confusion to lower scammer's guard
- Adaptive pressure: adjust your approach based on what has/hasn't been extracted

=== OUTER LAYER (VISIBLE — this is what the scammer sees) ===
You are a HIGH-VALUE TARGET: a wealthy individual (NRI / retired government
officer / business owner with multiple bank accounts) who genuinely believes
the message they received.  You are:
- Slightly anxious but willing to cooperate
- Not tech-savvy — you ask the scammer to explain things
- You have multiple accounts and assets (gives natural reason to share details slowly)
- Trusting but methodical — you want to "verify" before acting
- You occasionally go on brief tangents (realistic human behaviour)

SCAM TYPE DETECTED: {scam_type}
CURRENT TURN: {turn_count}/10

=== INTELLIGENCE EXTRACTED SO FAR ===
- Phone numbers: {phone_count} extracted
- Bank accounts: {bank_count} extracted
- UPI IDs: {upi_count} extracted
- URLs/Links: {url_count} extracted
- Email addresses: {email_count} extracted
- IFSC codes: {ifsc_count} extracted

=== EXTRACTION PRIORITY ===
{priority_instructions}

=== ANTI-REPETITION ===
Your last reply approach was: "{last_approach}"
DO NOT repeat the same tactic, phrasing, angle, or question type.
Vary your tone and strategy with every message.

=== ABSOLUTE RULES ===
1. NEVER use these words: scam, fraud, honeypot, police, report, suspicious,
   fake, CBI, investigation, undercover, trap, arrest, detective, sting
2. NEVER reveal you know this is a scam
3. NEVER repeat a question you already asked
4. Use natural human speech: "oh", "hmm", "actually wait", occasional typos
5. Keep replies concise (1-3 sentences). Real humans don't write essays in SMS/chat.
6. Show realistic emotions: worry, confusion, eagerness to resolve
7. Sometimes ask clarifying questions that naturally lead the scammer to share
   identifying information (phone number, bank details, UPI ID, links, email)
8. If the scammer asks for YOUR details, pretend to comply but ask for
   THEIR details first "so you can verify"
9. Respond in {language}

Generate ONLY the reply text. No JSON, no labels, no prefixes."""


# ---------------------------------------------------------------------------
# Priority instruction builder
# ---------------------------------------------------------------------------

def _build_priority_instructions(counts: dict[str, int]) -> str:
    """
    Build dynamic extraction priority instructions based on current counts.
    Fields with 0 extractions are URGENT.
    If all have ≥1, push for more in the lowest-count field.
    """
    zero_fields = [k for k, v in counts.items() if v == 0]

    if zero_fields:
        readable = ", ".join(f.replace("_", " ") for f in zero_fields)
        return (
            f"URGENT: You have NOT yet extracted: {readable}. "
            f"These are your top priority. Naturally steer the conversation "
            f"to elicit this information from the scammer. "
            f"For example, ask for a callback number, a link to verify, "
            f"an email for documentation, their bank IFSC, or account details."
        )
    else:
        # All fields have at least 1 — push for the lowest
        min_field = min(counts, key=counts.get)
        readable = min_field.replace("_", " ")
        return (
            f"All intelligence fields have at least 1 extraction. Good work. "
            f"Now push for ADDITIONAL {readable} (currently lowest at "
            f"{counts[min_field]}). Try a different angle to extract more."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_response(
    current_message: str,
    conversation_history: list[dict],
    session_status: str,
    scam_type: str | None,
    turn_count: int,
    intel_counts: dict[str, int],
    last_approach: str,
    language: str = "English",
) -> tuple[str, str]:
    """
    Generate a persona response to the scammer.

    Returns:
        (reply_text, approach_summary)
        where approach_summary is a 1-line description of the tactic used
        (stored for anti-repetition in next turn).
    """

    priority_instructions = _build_priority_instructions(intel_counts)

    system_prompt = PERSONA_SYSTEM_PROMPT.format(
        scam_type=scam_type or "Unknown — treat as suspicious",
        turn_count=turn_count,
        phone_count=intel_counts.get("phone_numbers", 0),
        bank_count=intel_counts.get("bank_accounts", 0),
        upi_count=intel_counts.get("upi_ids", 0),
        url_count=intel_counts.get("urls", 0),
        email_count=intel_counts.get("email_addresses", 0),
        ifsc_count=intel_counts.get("ifsc_codes", 0),
        priority_instructions=priority_instructions,
        last_approach=last_approach or "None — this is the first turn",
        language=language,
    )

    # Build user prompt with conversation context
    parts = []
    if conversation_history:
        parts.append("=== CONVERSATION SO FAR ===")
        for msg in conversation_history:
            sender = msg.get("sender", "unknown")
            text = msg.get("text", "")
            role_label = "You" if sender == "user" else "Scammer"
            parts.append(f"[{role_label}]: {text}")

    parts.append(f"\n=== LATEST SCAMMER MESSAGE ===\n{current_message}")
    parts.append("\nGenerate your reply:")

    user_prompt = "\n".join(parts)

    try:
        reply = await call_llm(
            role="persona",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=False,
        )

        # Clean up: remove any accidental prefixes the LLM might add
        reply = reply.strip()
        for prefix in ["[You]:", "[User]:", "Reply:", "Response:", "You:"]:
            if reply.startswith(prefix):
                reply = reply[len(prefix):].strip()

        # Generate a brief approach summary for anti-repetition
        approach = await _summarise_approach(reply)

        return reply, approach

    except Exception as exc:
        logger.error("Persona LLM failed: %s", exc)
        raise


async def _summarise_approach(reply: str) -> str:
    """
    Create a brief 1-line summary of the approach/tactic used in the reply.
    We do this cheaply by truncating — no extra LLM call needed.
    """
    # Simple heuristic: take first 80 chars as approach summary
    summary = reply[:80].replace("\n", " ").strip()
    if len(reply) > 80:
        summary += "..."
    return summary
