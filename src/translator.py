"""
Conditional translator — translates non-English messages to English via LLM.

Only invoked when metadata.language is not "English".
Preserves names, numbers, IDs, and URLs exactly.
"""

import logging

from src.llm_client import call_llm

logger = logging.getLogger(__name__)

TRANSLATOR_SYSTEM_PROMPT = """\
You are a precise translator. Translate the following text to English.

CRITICAL RULES:
- Preserve ALL names, numbers, phone numbers, account numbers, UPI IDs, 
  URLs, email addresses, and IFSC codes EXACTLY as they appear
- Do not modify any alphanumeric identifiers
- Translate ONLY the natural language portions
- Return ONLY the translated text, nothing else"""


async def translate_to_english(text: str) -> str:
    """
    Translate *text* to English using the translator LLM.
    Returns the translated text, or the original text on failure.
    """
    try:
        translated = await call_llm(
            role="translator",
            system_prompt=TRANSLATOR_SYSTEM_PROMPT,
            user_prompt=f"Translate to English:\n\n{text}",
            json_mode=False,
        )
        result = translated.strip()
        logger.info("Translation succeeded: %d chars → %d chars", len(text), len(result))
        return result
    except Exception as exc:
        logger.warning("Translation failed (%s), using original text", exc)
        return text
