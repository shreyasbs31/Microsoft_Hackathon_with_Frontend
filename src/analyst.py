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


ANALYST_SYSTEM_PROMPT = """You are an expert fraud detection analyst specialising in Indian financial scams.

Your task: analyse the conversation and classify it as one of:
- HONEYPOT: This is a scam. Confidence must be > {honeypot_threshold}.
- LEGIT: This is definitely NOT a scam. Confidence must be > {legit_threshold} AND there must be zero scam indicators across ALL messages.
- NEUTRAL: Insufficient evidence to decide conclusively.

Scam types to identify (if applicable):
- bank_fraud: Impersonating bank officials, requesting OTP/account details
- upi_fraud: Fake UPI cashback, refund, or verification scams
- phishing: Fake links, offers, product deals with malicious URLs
- investment_fraud: Fake investment schemes, stock tips, crypto scams
- lottery_fraud: Fake lottery/prize winnings requiring fees
- job_fraud: Fake job offers requiring registration fees
- impersonation: Impersonating government officials, police, etc.
- other: Any other scam type

Analyse these scam indicators:
- Urgency tactics ("immediately", "blocked", "expire")
- Requests for sensitive info (OTP, passwords, account numbers)
- Unsolicited contact about financial matters
- Too-good-to-be-true offers
- Pressure to act without verification
- Requests to click links or download apps
- Impersonation of authority figures

You MUST respond with valid JSON only:
{{
    "status": "HONEYPOT" | "NEUTRAL" | "LEGIT",
    "scam_type": "bank_fraud" | "upi_fraud" | "phishing" | "investment_fraud" | "lottery_fraud" | "job_fraud" | "impersonation" | "other" | null,
    "confidence": 0.0 to 1.0,
    "reasoning": "Brief explanation of your analysis"
}}"""


def _build_user_prompt(
    current_message: str,
    conversation_history: list[dict],
    extracted_intel: dict[str, list],
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
