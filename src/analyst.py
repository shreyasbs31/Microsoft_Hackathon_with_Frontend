"""
Analyst LLM — classifies whether a conversation is a scam.

Runs only when session status is NEUTRAL.
Returns classification (NEUTRAL / HONEYPOT / LEGIT), scam_type, confidence, and reasoning.
"""

import json
import logging
from dataclasses import dataclass

from src.llm_client import call_llm
from src.config import HONEYPOT_CONFIDENCE_THRESHOLD, LEGIT_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    status: str  # "NEUTRAL", "HONEYPOT", or "LEGIT"
    scam_type: str | None  # e.g. "bank_fraud", "upi_fraud", "phishing", etc.
    confidence: float  # 0.0–1.0
    reasoning: str


ANALYST_SYSTEM_PROMPT = """Indian financial scam detection analyst.

Classify conversation:
- HONEYPOT (scam): confidence>{honeypot_threshold}
- LEGIT (not scam): confidence>{legit_threshold}, zero indicators across ALL messages
- NEUTRAL: insufficient evidence

Scam types: bank_fraud(OTP/account impersonation) | upi_fraud(fake cashback/refund) | phishing(malicious URLs) | kyc_fraud(fake KYC update) | job_fraud(fake job+fees) | lottery_fraud(fake prize+fees) | electricity_bill(fake utility payment) | govt_scheme(fake subsidy) | crypto_investment(fake platforms) | customs_parcel(fake duty) | tech_support(fake virus scare) | loan_approval(fake pre-approved loan) | income_tax(fake tax refund/notice) | refund_scam(fake refund processing) | insurance(fake claim/renewal)

Red flags: urgency/pressure, OTP/password requests, upfront fees, suspicious links/downloads, legal threats, authority impersonation, unsolicited financial contact, too-good-to-be-true offers.

Respond ONLY valid JSON:
{{"status":"HONEYPOT"|"NEUTRAL"|"LEGIT","scam_type":"<type>"|null,"confidence":0.0-1.0,"reasoning":"1-2 sentences"}}"""


def _build_user_prompt(
    current_message: str,
    conversation_history: list[dict],
    extracted_intel: dict[str, list[str]],
) -> str:
    """Build the user prompt with conversation context."""

    parts = ["=== CONVERSATION HISTORY ==="]
    for msg in conversation_history:
        sender = msg.get("sender", "unknown")
        text = msg.get("text", "")
        parts.append(f"[{sender}]: {text}")

    parts.append(f"\n=== CURRENT MESSAGE ===\n[scammer]: {current_message}")

    # Include extracted intelligence as evidence
    if any(v for v in extracted_intel.values() if v):
        parts.append("\n=== EXTRACTED INTELLIGENCE (evidence) ===")
        for key, values in extracted_intel.items():
            if values:
                parts.append(f"  {key}: {values}")

    return "\n".join(parts)


async def analyse_message(
    current_message: str,
    conversation_history: list[dict],
    extracted_intel: dict[str, list],
) -> AnalysisResult:
    """
    Run the analyst LLM to classify the conversation.

    Returns an AnalysisResult with status, scam_type, confidence, reasoning.
    """

    system_prompt = ANALYST_SYSTEM_PROMPT.format(
        honeypot_threshold=HONEYPOT_CONFIDENCE_THRESHOLD,
        legit_threshold=LEGIT_CONFIDENCE_THRESHOLD,
    )

    user_prompt = _build_user_prompt(
        current_message, conversation_history, extracted_intel
    )

    try:
        raw = await call_llm(
            role="analyst",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_mode=True,
        )

        data = json.loads(raw)
        status = data.get("status", "NEUTRAL").upper()
        confidence = float(data.get("confidence", 0.0))
        scam_type = data.get("scam_type")
        reasoning = data.get("reasoning", "")

        # Enforce thresholds
        if status == "HONEYPOT" and confidence < HONEYPOT_CONFIDENCE_THRESHOLD:
            status = "NEUTRAL"
        if status == "LEGIT" and confidence < LEGIT_CONFIDENCE_THRESHOLD:
            status = "NEUTRAL"

        # Validate status value
        if status not in ("NEUTRAL", "HONEYPOT", "LEGIT"):
            status = "NEUTRAL"

        return AnalysisResult(
            status=status,
            scam_type=scam_type if status == "HONEYPOT" else None,
            confidence=confidence,
            reasoning=reasoning,
        )

    except Exception as exc:
        logger.error("Analyst LLM failed entirely: %s", exc)
        # On total failure, stay NEUTRAL — don't make a wrong call
        return AnalysisResult(
            status="NEUTRAL",
            scam_type=None,
            confidence=0.0,
            reasoning=f"Analyst error: {exc}",
        )
