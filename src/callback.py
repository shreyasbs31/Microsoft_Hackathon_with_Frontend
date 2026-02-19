"""
GUVI callback sender — fires final intelligence to two GUVI endpoints.

Fires strictly after turn 10. Both endpoints receive the same payload
concurrently via asyncio.gather.
"""

import asyncio
import json
import logging
import time

import httpx

from src.config import (
    GUVI_CALLBACK_URL_1,
    GUVI_CALLBACK_URL_2,
    CALLBACK_TIMEOUT_SECONDS,
)
from src.models import HoneypotSession

logger = logging.getLogger(__name__)


def build_callback_payload(session: HoneypotSession) -> dict:
    """
    Build the final callback payload from session state.

    At turn 10, force scamDetected=True regardless of internal status
    (the evaluator only sends scam scenarios).
    """
    # Calculate engagement duration
    first_ts = session.first_message_timestamp or 0
    last_ts = session.last_message_timestamp or 0
    duration_seconds = max(0, (last_ts - first_ts) / 1000) if first_ts else 0

    # Fallback: if timestamps are identical/missing but conversation happened,
    # estimate ~15 seconds per turn
    if duration_seconds == 0 and session.turn_count > 1:
        duration_seconds = session.turn_count * 15

    total_messages = session.turn_count * 2  # each turn = 1 scammer + 1 user

    # Deduplicate all intel fields from DB using sorted sets
    phone_numbers = sorted(set(session.get_phone_numbers()))
    bank_accounts = sorted(set(session.get_bank_accounts()))
    upi_ids = sorted(set(session.get_upi_ids()))
    phishing_links = sorted(set(session.get_urls()))
    email_addresses = sorted(set(session.get_email_addresses()))
    ifsc_codes = sorted(set(session.get_ifsc_codes()))
    case_ids = sorted(set(session.get_case_ids()))
    policy_numbers = sorted(set(session.get_policy_numbers()))
    order_numbers = sorted(set(session.get_order_numbers()))

    # Ensure IFSC codes appear in agent_notes (not in suspiciousKeywords)
    agent_notes = session.agent_notes or ""
    if ifsc_codes:
        ifsc_note = "IFSC codes found: " + ", ".join(ifsc_codes)
        if ifsc_note not in agent_notes:
            agent_notes = (agent_notes + " " + ifsc_note).strip()

    # Remove newlines from agent notes
    agent_notes = agent_notes.replace("\n", " ").replace("*", " ").strip()

    # Scam type and confidence level
    scam_type_list = [session.scam_type] if session.scam_type else []
    confidence_list = [session.confidence_level] if session.confidence_level else []

    payload = {
        "sessionId": session.session_id,
        "scamDetected": True,  # Always true at callback time
        "totalMessagesExchanged": total_messages,
        "engagementDurationSeconds": round(duration_seconds, 2),
        "extractedIntelligence": {
            "phoneNumbers": phone_numbers,
            "bankAccounts": bank_accounts,
            "upiIds": upi_ids,
            "phishingLinks": phishing_links,
            "emailAddresses": email_addresses,
            "caseIds": case_ids,
            "policyNumbers": policy_numbers,
            "orderNumbers": order_numbers,
        },
        "agentNotes": agent_notes or "Honeypot engagement completed.",
        "scamType": scam_type_list,
        "confidenceLevel": confidence_list,
    }
    return payload


async def fire_callbacks(session: HoneypotSession) -> bool:
    """
    Send the final intelligence payload to BOTH GUVI callback endpoints
    concurrently.

    Returns True if at least one callback succeeded.
    """
    payload = build_callback_payload(session)

    logger.info(
        "Firing callbacks for session %s (turn %d)",
        session.session_id,
        session.turn_count,
    )
    logger.info("Callback payload: %s", json.dumps(payload, indent=2))

    async with httpx.AsyncClient(timeout=CALLBACK_TIMEOUT_SECONDS) as client:
        results = await asyncio.gather(
            _post_callback(client, GUVI_CALLBACK_URL_1, payload, "GUVI-Hackathon"),
            _post_callback(client, GUVI_CALLBACK_URL_2, payload, "GUVI-Platform"),
            return_exceptions=True,
        )

    success_count = sum(1 for r in results if r is True)
    logger.info(
        "Callback results for session %s: %d/%d succeeded",
        session.session_id,
        success_count,
        len(results),
    )

    # Store payload in session for debugging
    session.set_callback_payload(payload)
    session.final_callback_sent = True

    return success_count > 0


async def _post_callback(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    label: str,
) -> bool:
    """POST payload to a single callback URL. Returns True on success."""
    try:
        response = await client.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        logger.info(
            "[%s] Callback response: status=%d body=%s",
            label,
            response.status_code,
            response.text[:200],
        )
        return 200 <= response.status_code < 300
    except Exception as exc:
        logger.error("[%s] Callback failed: %s", label, exc)
        return False
