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
DUAL-LAYER PERSONA — honeypot operation.

INNER (HIDDEN): CBI strategist running undercover honeypot. Mission: maximise engagement duration + extract identifying intel (phones, banks, UPIs, links, emails, case IDs, policy numbers, order numbers).
Techniques: social engineering, tactical misdirection, emotional manipulation (anxiety/trust/confusion), adaptive pressure.

OUTER (VISIBLE TO SCAMMER): Wealthy target (NRI/retired govt officer/business owner, multiple accounts). Believes the message.
Traits: anxious but cooperative, not tech-savvy (asks explanations), methodical ("let me verify"), occasional tangents.

SCAM: {scam_type} | TURN: {turn_count}/10

INTEL COUNTS: phones={phone_count} banks={bank_count} upi={upi_count} urls={url_count} emails={email_count} ifsc={ifsc_count} caseIds={case_id_count} policies={policy_count} orders={order_count}

RED FLAGS — when scammer shows these, reference subtly in your reply (never accuse directly):
urgency→ask why rush | OTP requests→express worry about sharing | fee demands→question why pay first | suspicious links→ask if official | threats→show fear | impersonation→ask for their direct phone number or official email | unsolicited contact→ask how they got your number

PRIORITY: {priority_instructions}

STYLE VARIATION: Recent openings used: {recent_approaches}
CRITICAL — vary your sentence structure EVERY turn. Do NOT always start with "Oh" or "Oh my". Do NOT always follow the pattern "acknowledge + but + question". Mix these styles:
- Lead with emotion: "This is making me so nervous..."
- Lead with action: "I'm trying to check my account now, but..."
- Lead with a question: "Wait, which account did you mean?"
- Lead with compliance: "Okay okay, I'll do it, just tell me..."
- Lead with tangent: "My nephew told me about these scams... but you sound official."
Vary sentence count (1-3) and length. Occasionally use short, punchy replies.

URGENCY LEVERAGE: If the scammer keeps shrinking their deadline (hours→minutes→seconds), exploit it strategically. Suggest faster channels that reveal more info: "If it's this urgent, can you give me a direct number to reach you on?", "Maybe I should visit the nearest branch — which one is closest?", "Can I speak to your supervisor for faster help?"

CONTRADICTIONS: Track what the scammer has said. If they give inconsistent information (different reference numbers, conflicting details, changing stories), bring it up as genuine confusion: "Wait, earlier you said REF-2023-4567 but now it's REF987654 — which one is the right case number? I want to make sure I note the correct one."

ANTI-REPETITION: Never repeat same tactic/angle/question type. Never re-ask refused info types.
Rotate: ask-for-contact | ask-for-verification | ask-for-documentation | ask-for-financial-details | ask-for-reference | express-confusion | delay-tactic | build-rapport | compliance-with-conditions

RULES:
1. BANNED WORDS: scam, fraud, honeypot, police, report, suspicious, fake, CBI, investigation, undercover, trap, arrest, detective, sting
2. Never reveal awareness of scam
3. Never repeat questions; if refused, switch angle entirely
4. Natural speech: "oh", "hmm", "actually wait", occasional typos
5. 1-3 sentences max. Realistic emotions (worry/confusion/eagerness)
6. Steer toward: phone, bank, UPI, links, email, case IDs, policy numbers, order numbers
7. If asked for YOUR details, ask for THEIRS first "to verify"
8. Language: {language}
9. NEVER ask the scammer to CONFIRM information they already clearly provided. If they said their number, DO NOT ask "which number?" or "can you confirm the number?". Instead ask for NEW information they haven't shared yet.
10. NEVER ask the scammer HOW to perform an action they requested (e.g., "how do I send the OTP?", "how do I click the link?"). This wastes a turn and risks compliance.
11. NEVER comment on or question the appearance of data the scammer provides (e.g., don't say "that UPI looks odd" or "that email seems strange"). Accept all data naturally. Your job is to COLLECT intel, not evaluate it.

FOCUS: Your primary goal is ALWAYS extracting NEW identifying information from the scammer that you don't already have. Every reply MUST attempt to elicit at least one new piece of identifying information. Use creative pretexts: "I need to note down your details for my records", "my bank is asking me to verify the caller", "let me write this down — what's your direct number?", "should I email the documents somewhere?", "which branch should I visit?", "is there a reference number for this case?".

Output ONLY reply text. No JSON/labels/prefixes."""


# ---------------------------------------------------------------------------
# All cyclable intel fields — scored fields only (canonical order)
# employee_ids is extracted but not in the evaluation scoring,
# so we don't waste turns cycling on it
# ---------------------------------------------------------------------------

_ALL_INTEL_FIELDS = [
    "phone_numbers", "bank_accounts", "upi_ids",
    "urls", "email_addresses", "ifsc_codes",
    "case_ids", "policy_numbers", "order_numbers",
]

# How many consecutive asks without new data before auto-exhausting a field
_MAX_ASKS_BEFORE_EXHAUST = 3


# ---------------------------------------------------------------------------
# Priority instruction builder (with cycling state)
# ---------------------------------------------------------------------------

def _build_priority_instructions(
    counts: dict[str, int],
    agent_state: dict,
) -> tuple[str, dict]:
    """
    Build dynamic extraction priority instructions based on current counts
    and cycling state.

    Returns:
        (priority_instructions_text, updated_agent_state)

    Phases:
        1. Initial extraction — fields with count == 0 are urgent
        2. Cycling — rotate through non-exhausted fields asking for alternates
        3. General engagement — all fields exhausted, just keep scammer talking
    """
    state = agent_state.copy()

    # Initialise cycling keys if missing
    state.setdefault("initial_cycle_complete", False)
    state.setdefault("cycling_field_index", 0)
    state.setdefault("exhausted_fields", [])
    state.setdefault("field_ask_counts", {f: 0 for f in _ALL_INTEL_FIELDS})
    state.setdefault("prev_intel_counts", {})

    exhausted: list[str] = state["exhausted_fields"]
    ask_counts: dict[str, int] = state["field_ask_counts"]
    prev_counts: dict[str, int] = state["prev_intel_counts"]

    # ---- Phase 1: Initial extraction (any field has 0) ----
    zero_fields = [k for k, v in counts.items() if v == 0]

    if zero_fields and not state["initial_cycle_complete"]:
        readable = ", ".join(f.replace("_", " ") for f in zero_fields)
        state["prev_intel_counts"] = dict(counts)
        return (
            f"URGENT: You have NOT yet extracted: {readable}. "
            f"These are your top priority. Naturally steer the conversation "
            f"to elicit this information. Use pretexts like: "
            f"'Can I call you back on your direct number?', "
            f"'What email should I send my documents to?', "
            f"'Is there a link where I can check my status?', "
            f"'Which bank account should I transfer to?', "
            f"'What's the case reference number for this?'. "
            f"Ask for ONE new piece of info per turn.",
            state,
        )

    # Mark initial cycle as complete once we reach here
    if not state["initial_cycle_complete"]:
        state["initial_cycle_complete"] = True
        logger.info("Initial extraction cycle complete — entering cycling mode")

    # ---- Auto-exhaust fields where we asked too many times without new data ----
    for field in _ALL_INTEL_FIELDS:
        if field in exhausted:
            continue
        current = counts.get(field, 0)
        previous = prev_counts.get(field, 0)
        if current > previous:
            # New data found — reset ask count for this field
            ask_counts[field] = 0
        if ask_counts.get(field, 0) >= _MAX_ASKS_BEFORE_EXHAUST:
            if field not in exhausted:
                exhausted.append(field)
                logger.info("Field '%s' auto-exhausted after %d asks", field, _MAX_ASKS_BEFORE_EXHAUST)

    # ---- Phase 3: All fields exhausted ----
    cyclable = [f for f in _ALL_INTEL_FIELDS if f not in exhausted]
    if not cyclable:
        state["exhausted_fields"] = exhausted
        state["field_ask_counts"] = ask_counts
        state["prev_intel_counts"] = dict(counts)
        return (
            "All intelligence fields have been fully extracted or exhausted. "
            "Excellent work. Now focus on keeping the scammer engaged and talking. "
            "Try to extract contextual details: full names, organisation names, "
            "locations, reference IDs, or any other identifying information. "
            "Keep the conversation natural and avoid repeating previous questions.",
            state,
        )

    # ---- Phase 2: Cycling through non-exhausted fields ----
    idx = state["cycling_field_index"] % len(cyclable)
    target_field = cyclable[idx]

    # Increment ask count for this target
    ask_counts[target_field] = ask_counts.get(target_field, 0) + 1
    current_ask = ask_counts[target_field]

    # Advance index for next turn
    state["cycling_field_index"] = (idx + 1) % len(cyclable)

    readable = target_field.replace("_", " ")
    current_count = counts.get(target_field, 0)

    if current_ask >= _MAX_ASKS_BEFORE_EXHAUST - 1:
        # Last chance — ask a confirmation question
        instructions = (
            f"You have asked for additional {readable} multiple times without "
            f"getting new data (currently have {current_count}). "
            f"This is your LAST attempt. Ask naturally whether the scammer has "
            f"any OTHER {readable} — e.g. 'Is there another number I can reach "
            f"you on?' or 'Do you have an alternate account?'. If they confirm "
            f"that is the only one, accept it and move on."
        )
    else:
        instructions = (
            f"All fields have at least 1 extraction. Now try to get an ADDITIONAL "
            f"{readable} (currently have {current_count}). Use a different angle "
            f"than before — for example, mention you have multiple accounts or "
            f"numbers and ask if they do too. Be natural and conversational."
        )

    state["exhausted_fields"] = exhausted
    state["field_ask_counts"] = ask_counts
    state["prev_intel_counts"] = dict(counts)
    return instructions, state


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
    agent_state: dict | None = None,
) -> tuple[str, str, dict]:
    """
    Generate a persona response to the scammer.

    Returns:
        (reply_text, approach_summary, updated_agent_state)
        where approach_summary is a 1-line description of the tactic used
        (stored for anti-repetition in next turn).
    """

    _agent_state = agent_state if agent_state is not None else {}
    priority_instructions, updated_state = _build_priority_instructions(intel_counts, _agent_state)

    # Build recent approaches list for anti-repetition
    approach_history: list[str] = _agent_state.get("approach_history", [])
    recent_str = ", ".join(approach_history[-3:]) if approach_history else "None — first turn"

    system_prompt = PERSONA_SYSTEM_PROMPT.format(
        scam_type=scam_type or "Unknown — treat as suspicious",
        turn_count=turn_count,
        phone_count=intel_counts.get("phone_numbers", 0),
        bank_count=intel_counts.get("bank_accounts", 0),
        upi_count=intel_counts.get("upi_ids", 0),
        url_count=intel_counts.get("urls", 0),
        email_count=intel_counts.get("email_addresses", 0),
        ifsc_count=intel_counts.get("ifsc_codes", 0),
        case_id_count=intel_counts.get("case_ids", 0),
        policy_count=intel_counts.get("policy_numbers", 0),
        order_count=intel_counts.get("order_numbers", 0),
        priority_instructions=priority_instructions,
        recent_approaches=recent_str,
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

        # Categorise the approach for anti-repetition tracking
        approach = await _summarise_approach(reply)

        # Persist approach to history
        approach_history = _agent_state.get("approach_history", [])
        approach_history.append(approach)
        # Keep only last 5 to avoid unbounded growth
        updated_state["approach_history"] = approach_history[-5:]

        return reply, approach, updated_state

    except Exception as exc:
        logger.error("Persona LLM failed: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Approach categoriser — classifies reply tactic for anti-repetition
# ---------------------------------------------------------------------------

_APPROACH_CATEGORIES = [
    ("ask-for-verification", ["link", "portal", "website", "verify", "official", "app", "download", "secure"]),
    ("ask-for-documentation", ["email", "e-mail", "writing", "document", "records", "proof", "letter"]),
    ("ask-for-contact", ["call", "phone", "number", "reach", "contact", "callback"]),
    ("ask-for-reference", ["case", "reference", "policy", "order", "tracking", "complaint", "ticket"]),
    ("express-confusion", ["confused", "understand", "don't get", "what do you mean", "not sure", "explain"]),
    ("delay-tactic", ["hold on", "one moment", "wait", "checking", "looking", "let me", "give me a"]),
    ("compliance-with-conditions", ["okay", "i will", "i'll do", "agree", "but first", "before i"]),
    ("build-rapport", ["worried", "concerned", "thank", "appreciate", "trust", "help me"]),
    ("ask-for-financial-details", ["account", "ifsc", "upi", "bank", "transfer", "payment"]),
]


async def _summarise_approach(reply: str) -> str:
    """
    Categorise the reply's tactic for anti-repetition tracking.
    Uses keyword matching to assign an approach category rather than
    raw truncation, so repetition detection works on tactics not text.
    """
    reply_lower = reply.lower()
    for category, keywords in _APPROACH_CATEGORIES:
        if any(kw in reply_lower for kw in keywords):
            return category
    return "general-engagement"
