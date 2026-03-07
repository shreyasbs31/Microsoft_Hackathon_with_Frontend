"""LLM client abstraction — Gemini primary, Groq fallback.

Provides a single ``call_llm()`` function that tries Gemini first
and falls back to Groq on any failure.  Includes model-name
fallback lists so expired preview names are handled gracefully.
Gemini calls retry once on empty response before falling back.
"""

import asyncio
import json
import logging
from typing import Literal

import google.generativeai as genai
from groq import AsyncGroq

from src.config import (
    GEMINI_API_KEY,
    GEMINI_API_KEYS,
    GROQ_API_KEY,
    GEMINI_ANALYST_MODEL,
    GEMINI_PERSONA_MODEL,
    GEMINI_TRANSLATOR_MODEL,
    GEMINI_EXTRACTOR_MODEL,
    GROQ_ANALYST_MODEL,
    GROQ_PERSONA_MODEL,
    LLM_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Initialise SDKs
# ---------------------------------------------------------------------------

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini primary key configured (%d keys total)", len(GEMINI_API_KEYS))
else:
    logger.warning("No GEMINI_API_KEY found — Gemini will be unavailable")

_groq_client: AsyncGroq | None = None
if GROQ_API_KEY:
    _groq_client = AsyncGroq(api_key=GROQ_API_KEY)
    logger.info("Groq API key configured (len=%d)", len(GROQ_API_KEY))
else:
    logger.warning("No GROQ_API_KEY found — Groq fallback unavailable")


# ---------------------------------------------------------------------------
# Model mapping — ordered fallback lists
# ---------------------------------------------------------------------------

Role = Literal["analyst", "persona", "translator", "extractor"]

# Each role has a PRIMARY model (from config) and fallback options
_GEMINI_MODEL_FALLBACKS: dict[Role, list[str]] = {
    "analyst": [
        GEMINI_ANALYST_MODEL,
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
    ],
    "persona": [
        GEMINI_PERSONA_MODEL,
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ],
    "translator": [
        GEMINI_TRANSLATOR_MODEL,
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
    ],
    "extractor": [
        GEMINI_EXTRACTOR_MODEL,
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
    ],
}

_GROQ_MODELS: dict[Role, str] = {
    "analyst": GROQ_ANALYST_MODEL,
    "persona": GROQ_PERSONA_MODEL,
    "translator": GROQ_ANALYST_MODEL,
    "extractor": GROQ_ANALYST_MODEL,
}

# Cache: once a model works for a role, remember it
_working_gemini_model: dict[Role, str] = {}


# ---------------------------------------------------------------------------
# Gemini call (with empty-response retry)
# ---------------------------------------------------------------------------

async def _call_gemini(
    role: Role,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
) -> str:
    """Call Google Gemini, trying fallback model names if primary fails.
    Retries once on empty response before moving to next model."""

    # If we already found a working model for this role, try it first
    if role in _working_gemini_model:
        models_to_try = [_working_gemini_model[role]]
    else:
        models_to_try = _GEMINI_MODEL_FALLBACKS[role]

    last_exc = None
    for model_name in models_to_try:
        try:
            generation_config = {}
            if json_mode:
                generation_config["response_mime_type"] = "application/json"

            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt,
                generation_config=generation_config if generation_config else None,
            )

            # Run synchronous Gemini SDK in a thread
            def _generate(m=model):
                response = m.generate_content(user_prompt)
                return response.text

            # Try up to 2 times (handles intermittent empty responses)
            for attempt in range(2):
                result = await asyncio.wait_for(
                    asyncio.to_thread(_generate),
                    timeout=LLM_TIMEOUT_SECONDS,
                )
                if result and result.strip():
                    _working_gemini_model[role] = model_name
                    logger.info(
                        "Gemini [%s/%s] call succeeded (%d chars)",
                        role, model_name, len(result),
                    )
                    return result
                else:
                    logger.warning(
                        "Gemini [%s/%s] returned empty (attempt %d/2)",
                        role, model_name, attempt + 1,
                    )

            # Both attempts returned empty — treat as failure for this model
            raise RuntimeError(f"Gemini {model_name} returned empty response after 2 attempts")

        except Exception as exc:
            last_exc = exc
            logger.warning("Gemini model %s failed for role %s: %s", model_name, role, exc)
            # Clear cache so next call tries all models
            _working_gemini_model.pop(role, None)
            continue

    raise last_exc or RuntimeError("All Gemini models exhausted")


# ---------------------------------------------------------------------------
# Groq call
# ---------------------------------------------------------------------------

async def _call_groq(
    role: Role,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
) -> str:
    """Call Groq and return the text response."""

    if not _groq_client:
        raise RuntimeError("Groq API key not configured")

    model_name = _GROQ_MODELS[role]
    logger.info("Calling Groq [%s/%s]...", role, model_name)

    kwargs: dict = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await asyncio.wait_for(
        _groq_client.chat.completions.create(**kwargs),
        timeout=LLM_TIMEOUT_SECONDS,
    )
    text = response.choices[0].message.content
    logger.info("Groq [%s/%s] call succeeded (%d chars)", role, model_name, len(text))
    return text


# ---------------------------------------------------------------------------
# Public API — unified call with fallback
# ---------------------------------------------------------------------------

async def call_llm(
    role: Role,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
) -> str:
    """
    Call an LLM for the given *role*.

    Cycles through ALL available Gemini API keys first (primary + extras).
    Only falls back to Groq if every single Gemini key fails.
    Raises RuntimeError only if ALL providers and ALL keys fail.
    """

    gemini_error = None
    groq_error = None

    # --- Try every Gemini API key in sequence ---
    if GEMINI_API_KEYS:
        for idx, api_key in enumerate(GEMINI_API_KEYS):
            try:
                # Reconfigure with this specific key
                genai.configure(api_key=api_key)
                # Clear model cache so the new key gets a fresh attempt
                _working_gemini_model.pop(role, None)
                result = await _call_gemini(role, system_prompt, user_prompt, json_mode)
                if idx > 0:
                    logger.info("Gemini key #%d succeeded for role=%s", idx + 1, role)
                return result
            except Exception as exc:
                gemini_error = exc
                logger.warning(
                    "Gemini key #%d failed for role=%s: %s — trying next key",
                    idx + 1, role, exc,
                )
                _working_gemini_model.pop(role, None)
                continue

        logger.warning(
            "All %d Gemini key(s) exhausted for role=%s — falling back to Groq",
            len(GEMINI_API_KEYS), role,
        )
    else:
        logger.warning("No Gemini API keys configured — falling back to Groq")

    # --- Emergency fallback: Groq ---
    if GROQ_API_KEY and _groq_client:
        try:
            return await _call_groq(role, system_prompt, user_prompt, json_mode)
        except Exception as exc:
            groq_error = exc
            logger.error("Groq [%s] also failed: %s", role, exc)

    # All providers failed
    logger.error(
        "ALL LLM providers failed for role=%s. Last Gemini error: %s | Groq: %s",
        role, gemini_error, groq_error,
    )
    raise RuntimeError(
        f"All LLM providers failed for role={role}. "
        f"Gemini ({len(GEMINI_API_KEYS)} keys tried): {gemini_error} | Groq: {groq_error}"
    )
