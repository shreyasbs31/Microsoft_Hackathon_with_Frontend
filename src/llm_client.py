"""
LLM client abstraction — Gemini primary, OpenAI fallback.

Provides a single `call_llm()` function that tries Gemini first
and falls back to OpenAI on any failure.  Includes model-name
fallback lists so expired preview names are handled gracefully.
"""

import json
import logging
import asyncio
import traceback
from typing import Literal

import google.generativeai as genai
from openai import AsyncOpenAI

from src.config import (
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    GEMINI_ANALYST_MODEL,
    GEMINI_PERSONA_MODEL,
    GEMINI_TRANSLATOR_MODEL,
    OPENAI_ANALYST_MODEL,
    OPENAI_PERSONA_MODEL,
    LLM_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Initialise SDKs
# ---------------------------------------------------------------------------

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API key configured (len=%d)", len(GEMINI_API_KEY))
else:
    logger.warning("No GEMINI_API_KEY found — Gemini will be unavailable")

_openai_client: AsyncOpenAI | None = None
if OPENAI_API_KEY:
    _openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    logger.info("OpenAI API key configured (len=%d)", len(OPENAI_API_KEY))
else:
    logger.warning("No OPENAI_API_KEY found — OpenAI fallback unavailable")


# ---------------------------------------------------------------------------
# Model mapping — ordered fallback lists
# ---------------------------------------------------------------------------

Role = Literal["analyst", "persona", "translator"]

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
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
    ],
    "translator": [
        GEMINI_TRANSLATOR_MODEL,
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
    ],
}

_OPENAI_MODELS: dict[Role, str] = {
    "analyst": OPENAI_ANALYST_MODEL,
    "persona": OPENAI_PERSONA_MODEL,
    "translator": OPENAI_ANALYST_MODEL,  # translator uses the lighter model
}

# Cache: once a model works for a role, remember it
_working_gemini_model: dict[Role, str] = {}


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------

async def _call_gemini(
    role: Role,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
) -> str:
    """Call Google Gemini, trying fallback model names if primary fails."""

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

            result = await asyncio.wait_for(
                asyncio.to_thread(_generate),
                timeout=LLM_TIMEOUT_SECONDS,
            )

            # Cache this working model
            _working_gemini_model[role] = model_name
            logger.info("Gemini [%s/%s] call succeeded (%d chars)", role, model_name, len(result))
            return result

        except Exception as exc:
            last_exc = exc
            logger.warning("Gemini model %s failed for role %s: %s", model_name, role, exc)
            continue

    raise last_exc or RuntimeError("All Gemini models exhausted")


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------

async def _call_openai(
    role: Role,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
) -> str:
    """Call OpenAI and return the text response."""

    if not _openai_client:
        raise RuntimeError("OpenAI API key not configured")

    model_name = _OPENAI_MODELS[role]
    logger.info("Calling OpenAI [%s/%s]...", role, model_name)

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
        _openai_client.chat.completions.create(**kwargs),
        timeout=LLM_TIMEOUT_SECONDS,
    )
    text = response.choices[0].message.content
    logger.info("OpenAI [%s/%s] call succeeded (%d chars)", role, model_name, len(text))
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

    Tries Gemini first (with model-name fallbacks); on failure, falls back
    to OpenAI.  Returns the raw text response.
    Raises RuntimeError only if BOTH providers fail.
    """

    gemini_error = None
    openai_error = None

    # --- Try Gemini ---
    if GEMINI_API_KEY:
        try:
            return await _call_gemini(role, system_prompt, user_prompt, json_mode)
        except Exception as exc:
            gemini_error = exc
            logger.warning(
                "Gemini [%s] failed (all models): %s — falling back to OpenAI",
                role, exc,
            )

    # --- Fallback: OpenAI ---
    if OPENAI_API_KEY and _openai_client:
        try:
            return await _call_openai(role, system_prompt, user_prompt, json_mode)
        except Exception as exc:
            openai_error = exc
            logger.error("OpenAI [%s] also failed: %s", role, exc)

    # Both failed — log full details
    logger.error(
        "ALL LLM providers failed for role=%s. Gemini: %s | OpenAI: %s",
        role, gemini_error, openai_error,
    )
    raise RuntimeError(
        f"All LLM providers failed for role={role}. "
        f"Gemini: {gemini_error} | OpenAI: {openai_error}"
    )
