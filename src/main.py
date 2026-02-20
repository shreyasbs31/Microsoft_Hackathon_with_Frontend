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
from src.extractor import (
    extract_intelligence_regex,
    extract_misc_notes,
    merge_intelligence,
    normalise_text,
    detect_denials,
    adjust_counts_for_denials,
    detect_denials_llm,
    detect_single_value_confirmations,
    has_reference_hints,
    extract_reference_ids,
    extract_invalid_ifsc_hints,
)
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
        # Return 401 on invalid API key so callers can detect auth failures.
        return JSONResponse(
            status_code=401,
            content={"status": "error", "detail": "Invalid API key"},
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


# Alias — GUVI evaluator sends to /api/message
@app.post("/api/message", response_model=HoneypotResponse)
async def api_message(request: HoneypotRequest):
    """Alias for /honeypot — the GUVI evaluation platform uses this path."""
    return await honeypot(request)


async def _process_turn(request: HoneypotRequest) -> str:
    """Core processing pipeline for a single turn."""

    def _append_agent_note(existing: str, note: str, max_len: int = 1000) -> str:
        note = (note or "").strip()
        if not note:
            return existing
        # Exact duplicate check
        if note in existing:
            return existing
        # Semantic dedup: skip if first 60 chars of note already appear
        note_prefix = note[:60]
        if note_prefix and note_prefix in existing:
            return existing
        sep = " " if existing else ""
        combined = (existing + sep + note).strip()
        if len(combined) > max_len:
            combined = combined[:max_len - 3].rsplit(" ", 1)[0] + "..."
        return combined

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
            # Try numeric epoch string first (e.g. "1770005528731")
            stripped = msg_timestamp.strip()
            if stripped.isdigit():
                msg_timestamp = int(stripped)
            else:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
                    msg_timestamp = int(dt.timestamp() * 1000)
                except Exception:
                    msg_timestamp = int(time.time() * 1000)
        elif msg_timestamp is None:
            msg_timestamp = int(time.time() * 1000)

        if session.first_message_timestamp is None:
            session.first_message_timestamp = msg_timestamp
        session.last_message_timestamp = msg_timestamp

        # ---- C. Regex extraction for structured fields ----
        new_intel = extract_intelligence_regex(normalised_text)

        # ---- C2. LLM extraction for misc contextual notes ----
        misc_notes = await extract_misc_notes(normalised_text)
        if misc_notes:
            existing_notes = session.agent_notes or ""
            session.agent_notes = _append_agent_note(existing_notes, misc_notes)

        # ---- C3. IFSC codes → agent_notes ----
        if new_intel.ifsc_codes:
            ifsc_note = "IFSC codes found: " + ", ".join(new_intel.ifsc_codes)
            existing_notes = session.agent_notes or ""
            session.agent_notes = _append_agent_note(existing_notes, ifsc_note)

        # ---- C3b. Invalid IFSC hints → agent_notes ----
        invalid_ifsc = extract_invalid_ifsc_hints(normalised_text)
        if invalid_ifsc:
            hint_note = "Scammer provided invalid IFSC: " + ", ".join(invalid_ifsc)
            existing_notes = session.agent_notes or ""
            session.agent_notes = _append_agent_note(existing_notes, hint_note)

        # ---- C4. LLM extraction for case_ids, policy_numbers, order_numbers ----
        if has_reference_hints(normalised_text):
            ref_ids = await extract_reference_ids(normalised_text)
            for cid in ref_ids.get("case_ids", []):
                if cid and cid not in new_intel.case_ids:
                    new_intel.case_ids.append(cid)
            for pn in ref_ids.get("policy_numbers", []):
                if pn and pn not in new_intel.policy_numbers:
                    new_intel.policy_numbers.append(pn)
            for on in ref_ids.get("order_numbers", []):
                if on and on not in new_intel.order_numbers:
                    new_intel.order_numbers.append(on)

        # ---- D. Merge intel with session data ----
        existing_intel = {
            "phone_numbers": session.get_phone_numbers(),
            "bank_accounts": session.get_bank_accounts(),
            "upi_ids": session.get_upi_ids(),
            "urls": session.get_urls(),
            "email_addresses": session.get_email_addresses(),
            "ifsc_codes": session.get_ifsc_codes(),
            "suspicious_keywords": session.get_suspicious_keywords(),
            "case_ids": session.get_case_ids(),
            "policy_numbers": session.get_policy_numbers(),
            "order_numbers": session.get_order_numbers(),
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
        session.set_case_ids(merged_intel["case_ids"])
        session.set_policy_numbers(merged_intel["policy_numbers"])
        session.set_order_numbers(merged_intel["order_numbers"])

        # ---- I0. Fire callback when we've just processed the 19th scammer message
        try:
            conversation_history = request.conversationHistory or []
            scammer_count = sum(
                1 for m in conversation_history if (m.get("sender") or "").lower() == "scammer"
            )
            if (request.message and (request.message.sender or "").lower() == "scammer"):
                scammer_count += 1
        except Exception:
            scammer_count = 0

        # Trigger only when this is exactly the 19th scammer message (after extraction)
        # Guard: check final_callback_sent FIRST so we never double-fire
        if (
            not session.final_callback_sent
            and scammer_count == 19
            and (request.message.sender or "").lower() == "scammer"
        ):
            logger.info("19th scammer message reached — firing interim final callbacks")
            # Set flag BEFORE firing to prevent the turn-10 block from re-triggering
            session.final_callback_sent = True
            try:
                success = await fire_callbacks(session)
                db.commit()
                if success:
                    logger.info("Callbacks sent successfully for session %s (19th message)", session.session_id)
                else:
                    logger.warning("One or more callbacks failed for session %s (19th message)", session.session_id)
            except Exception as exc:
                # Reset flag if the callback itself failed
                session.final_callback_sent = False
                logger.error("Callback error for session %s at 19th message: %s", session.session_id, exc)

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
                session.confidence_level = str(analysis.confidence)
            elif analysis.status == "LEGIT":
                session.status = SessionStatus.LEGIT

            # Append analyst reasoning to agent notes
            if analysis.reasoning:
                existing_notes = session.agent_notes or ""
                session.agent_notes = _append_agent_note(existing_notes, analysis.reasoning)

        # ---- G. Generate persona response ----
        agent_state = session.get_agent_state()
        last_approach = agent_state.get("last_approach", "")

        try:
            # Detect explicit denials in recent scammer messages and current text
            denied_fields: set[str] = set()
            single_value_fields: set[str] = set()

            # Check the translated/current message with regex
            denied_fields |= detect_denials(analysis_text)
            # Check for single-value confirmations ("that's the only number I have")
            single_value_fields |= detect_single_value_confirmations(analysis_text)

            # LLM-based denial detection — complements regex by catching
            # natural phrasing the regex misses (may find denials for
            # different fields than what regex caught)
            llm_denied = await detect_denials_llm(analysis_text)
            denied_fields |= llm_denied

            # Also scan the last few scammer messages from the conversation history
            try:
                conv = request.conversationHistory or []
                # Check up to last 3 scammer messages for explicit denials
                scammer_msgs = [m for m in conv if (m.get("sender") or "").lower() == "scammer"]
                for m in scammer_msgs[-3:]:
                    denied_fields |= detect_denials(m.get("text", ""))
                    single_value_fields |= detect_single_value_confirmations(m.get("text", ""))
            except Exception:
                pass

            if denied_fields:
                # Persist a short agent note about the denial for auditing
                existing_notes = session.agent_notes or ""
                denial_readable = ", ".join(sorted(denied_fields))
                session.agent_notes = _append_agent_note(existing_notes, f"Scammer denied sharing: {denial_readable}")

            if single_value_fields:
                existing_notes = session.agent_notes or ""
                sv_readable = ", ".join(sorted(single_value_fields))
                session.agent_notes = _append_agent_note(existing_notes, f"Scammer confirmed single value for: {sv_readable}")

            # Feed denials and single-value confirmations into cycling exhaustion
            agent_state = session.get_agent_state()
            exhausted = set(agent_state.get("exhausted_fields", []))
            exhausted |= denied_fields
            exhausted |= single_value_fields
            agent_state["exhausted_fields"] = sorted(exhausted)
            session.set_agent_state(agent_state)

            adjusted_counts = adjust_counts_for_denials(session.intel_counts(), denied_fields | single_value_fields)

            reply, approach_summary, updated_agent_state = await generate_response(
                current_message=analysis_text,
                conversation_history=request.conversationHistory,
                session_status=session.status.value,
                scam_type=session.scam_type,
                turn_count=session.turn_count + 1,
                intel_counts=adjusted_counts,
                last_approach=last_approach,
                language=language,
                agent_state=agent_state,
            )
        except Exception as exc:
            logger.error("Persona generation failed: %s", exc)
            reply = random.choice(FALLBACK_REPLIES)
            approach_summary = "fallback-generic-reply"

        # ---- H. Update session ----
        session.turn_count += 1
        updated_agent_state["last_approach"] = approach_summary
        session.set_agent_state(updated_agent_state)
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
        # Remove asterisks used for emphasis from outgoing reply text
        try:
            if isinstance(reply, str):
                reply = reply.replace("*", "")
        except Exception:
            pass

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
