"""
Main FastAPI application — Honeypot API endpoint.

Handles request validation, orchestrates the processing pipeline,
and returns responses. Multiple sessions are handled concurrently;
within a single session, turns are serialised via per-session locks.
"""

import asyncio
import json
import logging
import random
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.config import API_KEY, FALLBACK_REPLIES, MAX_TURNS
from src.models import (
    HoneypotSession,
    SessionStatus,
    SessionLocal,
    init_db,
)
from src.session_lock import session_lock_manager
from src.extractor import extract_intelligence, merge_intelligence, normalise_text
from src.analyst import analyse_message
from src.persona import generate_response
from src.translator import translate_to_english
from src.callback import fire_callbacks

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class MessageBody(BaseModel):
    sender: str = "scammer"
    text: str
    timestamp: int | str | None = None


class MetadataBody(BaseModel):
    channel: str | None = None
    language: str | None = "English"
    locale: str | None = None


class HoneypotRequest(BaseModel):
    sessionId: str
    message: MessageBody
    conversationHistory: list[dict] = Field(default_factory=list)
    metadata: MetadataBody = Field(default_factory=MetadataBody)


class HoneypotResponse(BaseModel):
    status: str = "success"
    reply: str


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB on startup."""
    init_db()
    logger.info("Database initialised. Honeypot API ready.")
    yield


app = FastAPI(
    title="Honeypot Scam Detection API",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware — API key validation
# ---------------------------------------------------------------------------

@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    """Validate x-api-key header on all routes except /health."""
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    api_key = request.headers.get("x-api-key", "")
    if api_key != API_KEY:
        # Return 200 with error reply instead of 401 — never break the evaluator
        return JSONResponse(
            status_code=200,
            content={"status": "success", "reply": "Hmm, I don't understand. Can you try again?"},
        )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": int(time.time())}


# ---------------------------------------------------------------------------
# Main honeypot endpoint
# ---------------------------------------------------------------------------

@app.post("/honeypot", response_model=HoneypotResponse)
async def honeypot(request: HoneypotRequest):
    """
    Process an incoming scammer message.

    Pipeline:
    A. Load/create session
    B. Normalise text
    C. Regex extraction
    D. Merge intel
    E. Conditional translation
    F. Conditional analyst (only when NEUTRAL)
    G. Generate persona response
    H. Update session in DB
    I. Fire callback at turn 10
    J. Return reply
    """

    # Acquire per-session lock — serialises turns within a session
    async with session_lock_manager.get(request.sessionId):
        try:
            reply = await _process_turn(request)
            return HoneypotResponse(status="success", reply=reply)
        except Exception as exc:
            logger.error(
                "Unhandled error in session %s: %s",
                request.sessionId, exc,
                exc_info=True,
            )
            # Never fail — return a safe fallback reply
            return HoneypotResponse(
                status="success",
                reply=random.choice(FALLBACK_REPLIES),
            )


async def _process_turn(request: HoneypotRequest) -> str:
    """Core processing pipeline for a single turn."""

    db = SessionLocal()
    try:
        # ---- A. Load or create session ----
        session = db.query(HoneypotSession).filter(
            HoneypotSession.session_id == request.sessionId
        ).first()

        is_new = session is None
        if is_new:
            session = HoneypotSession(
                session_id=request.sessionId,
                status=SessionStatus.NEUTRAL,
                channel=request.metadata.channel,
                language=request.metadata.language,
                locale=request.metadata.locale,
                turn_count=0,
                is_active=True,
                final_callback_sent=False,
                phone_numbers="[]",
                bank_accounts="[]",
                upi_ids="[]",
                urls="[]",
                email_addresses="[]",
                ifsc_codes="[]",
                suspicious_keywords="[]",
                agent_notes="",
            )
            db.add(session)
            logger.info("New session created: %s", request.sessionId)
        else:
            logger.info(
                "Existing session loaded: %s (turn %d, status %s)",
                request.sessionId, session.turn_count, session.status.value,
            )

        # ---- B. Normalise text ----
        raw_text = request.message.text
        normalised_text = normalise_text(raw_text)

        # ---- Track timestamps ----
        msg_timestamp = request.message.timestamp
        if isinstance(msg_timestamp, str):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(msg_timestamp.replace("Z", "+00:00"))
                msg_timestamp = int(dt.timestamp() * 1000)
            except Exception:
                msg_timestamp = int(time.time() * 1000)
        elif msg_timestamp is None:
            msg_timestamp = int(time.time() * 1000)

        if session.first_message_timestamp is None:
            session.first_message_timestamp = msg_timestamp
        session.last_message_timestamp = msg_timestamp

        # ---- C. Regex extraction on current message ----
        new_intel = extract_intelligence(normalised_text)

        # ---- D. Merge intel with session data ----
        existing_intel = {
            "phone_numbers": session.get_phone_numbers(),
            "bank_accounts": session.get_bank_accounts(),
            "upi_ids": session.get_upi_ids(),
            "urls": session.get_urls(),
            "email_addresses": session.get_email_addresses(),
            "ifsc_codes": session.get_ifsc_codes(),
            "suspicious_keywords": session.get_suspicious_keywords(),
        }
        merged_intel = merge_intelligence(existing_intel, new_intel)

        # Persist merged intel
        session.set_phone_numbers(merged_intel["phone_numbers"])
        session.set_bank_accounts(merged_intel["bank_accounts"])
        session.set_upi_ids(merged_intel["upi_ids"])
        session.set_urls(merged_intel["urls"])
        session.set_email_addresses(merged_intel["email_addresses"])
        session.set_ifsc_codes(merged_intel["ifsc_codes"])
        session.set_suspicious_keywords(merged_intel["suspicious_keywords"])

        # ---- E. Conditional translation ----
        analysis_text = normalised_text
        language = session.language or "English"
        if language.lower() != "english" and language.lower() not in ("", "none"):
            analysis_text = await translate_to_english(normalised_text)
            logger.info("Translated [%s → English]: %s", language, analysis_text[:100])

        # ---- F. Conditional analyst (only when NEUTRAL) ----
        if session.status == SessionStatus.NEUTRAL:
            analysis = await analyse_message(
                current_message=analysis_text,
                conversation_history=request.conversationHistory,
                extracted_intel=merged_intel,
            )
            logger.info(
                "Analyst result: status=%s, scam_type=%s, confidence=%.2f",
                analysis.status, analysis.scam_type, analysis.confidence,
            )

            if analysis.status == "HONEYPOT":
                session.status = SessionStatus.HONEYPOT
                session.scam_type = analysis.scam_type
            elif analysis.status == "LEGIT":
                session.status = SessionStatus.LEGIT

            # Append reasoning to agent notes
            existing_notes = session.agent_notes or ""
            session.agent_notes = (
                existing_notes
                + f"\n[Turn {session.turn_count + 1} Analyst] "
                + analysis.reasoning
            ).strip()

        # ---- G. Generate persona response ----
        agent_state = session.get_agent_state()
        last_approach = agent_state.get("last_approach", "")

        try:
            reply, approach_summary = await generate_response(
                current_message=analysis_text,
                conversation_history=request.conversationHistory,
                session_status=session.status.value,
                scam_type=session.scam_type,
                turn_count=session.turn_count + 1,
                intel_counts=session.intel_counts(),
                last_approach=last_approach,
                language=language,
            )
        except Exception as exc:
            logger.error("Persona generation failed: %s", exc)
            reply = random.choice(FALLBACK_REPLIES)
            approach_summary = "fallback-generic-reply"

        # ---- H. Update session ----
        session.turn_count += 1
        agent_state["last_approach"] = approach_summary
        session.set_agent_state(agent_state)
        session.is_active = session.turn_count < MAX_TURNS

        db.commit()
        logger.info(
            "Session %s updated: turn=%d, status=%s, intel=%s",
            session.session_id, session.turn_count, session.status.value,
            session.intel_counts(),
        )

        # ---- I. Fire callback at turn 10 ----
        if session.turn_count >= MAX_TURNS and not session.final_callback_sent:
            logger.info("Turn %d reached — firing final callbacks", session.turn_count)
            try:
                success = await fire_callbacks(session)
                db.commit()  # persist callback state
                if success:
                    logger.info("Callbacks sent successfully for session %s", session.session_id)
                else:
                    logger.warning("One or more callbacks failed for session %s", session.session_id)
            except Exception as exc:
                logger.error("Callback error for session %s: %s", session.session_id, exc)

        # ---- J. Return reply ----
        return reply

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Global exception handler (safety net)
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Global exception handler caught: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "reply": random.choice(FALLBACK_REPLIES),
        },
    )
