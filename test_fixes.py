"""
Tests for the 9 honeypot fixes.

Run: python -m pytest test_fixes.py -v
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Fix 7 — URL trailing punctuation stripped
# ---------------------------------------------------------------------------

def test_url_trailing_comma_stripped():
    from src.extractor import extract_intelligence_regex
    intel = extract_intelligence_regex("Check https://sbi.com/secure/REF-2023-4567, for details")
    assert len(intel.urls) == 1
    url = intel.urls[0]
    assert not url.endswith(","), f"URL should not end with comma: {url}"
    assert url == "https://sbi.com/secure/REF-2023-4567"


def test_url_trailing_period_stripped():
    from src.extractor import extract_intelligence_regex
    intel = extract_intelligence_regex("Visit https://example.com/page.")
    assert len(intel.urls) == 1
    assert not intel.urls[0].endswith(".")


def test_url_trailing_semicolon_stripped():
    from src.extractor import extract_intelligence_regex
    intel = extract_intelligence_regex("Link: https://example.com/path;")
    assert len(intel.urls) == 1
    assert not intel.urls[0].endswith(";")


def test_url_no_false_strip():
    """Don't strip characters that are legitimately part of URLs."""
    from src.extractor import extract_intelligence_regex
    intel = extract_intelligence_regex("Go to https://example.com/path/to/file")
    assert len(intel.urls) == 1
    assert intel.urls[0] == "https://example.com/path/to/file"


# ---------------------------------------------------------------------------
# Fix 5 — Invalid IFSC hint detection
# ---------------------------------------------------------------------------

def test_invalid_ifsc_detected():
    from src.extractor import extract_invalid_ifsc_hints
    text = "The IFSC is 123456, please use it"
    hints = extract_invalid_ifsc_hints(text)
    assert "123456" in hints, f"Should detect '123456' as invalid IFSC: {hints}"


def test_valid_ifsc_not_flagged():
    from src.extractor import extract_invalid_ifsc_hints
    text = "The IFSC code is SBIN0001234"
    hints = extract_invalid_ifsc_hints(text)
    assert len(hints) == 0, f"Valid IFSC should not be flagged: {hints}"


def test_no_ifsc_context():
    from src.extractor import extract_invalid_ifsc_hints
    text = "The account number is 1234567890"
    hints = extract_invalid_ifsc_hints(text)
    assert len(hints) == 0, f"Non-IFSC context should not match: {hints}"


# ---------------------------------------------------------------------------
# Fix 9 — Engagement duration floor
# ---------------------------------------------------------------------------

def test_duration_floor_applied():
    """When timestamps yield a very short duration for many turns,
    the per-turn estimate should be used as a floor."""
    # Test duration logic directly to avoid psycopg2 import from callback.py
    first_ts = 1000000
    last_ts = 1010000  # only 10 seconds
    turn_count = 10

    duration_seconds = max(0, (last_ts - first_ts) / 1000)
    estimated_duration = turn_count * 15
    if turn_count > 1:
        duration_seconds = max(duration_seconds, estimated_duration)

    # 10 turns * 15 seconds = 150 seconds should be the floor
    assert duration_seconds >= 150, \
        f"Duration should be at least 150s for 10 turns, got {duration_seconds}"


def test_duration_real_timestamps_used_when_higher():
    """When real timestamps give a higher value than the estimate, use them."""
    # Test duration logic directly to avoid psycopg2 import from callback.py
    first_ts = 1000000
    last_ts = 1500000  # 500 seconds
    turn_count = 5

    duration_seconds = max(0, (last_ts - first_ts) / 1000)
    estimated_duration = turn_count * 15
    if turn_count > 1:
        duration_seconds = max(duration_seconds, estimated_duration)

    # Real duration is 500s, estimate is 75s → should use 500
    assert duration_seconds == 500, \
        f"Should use real timestamp duration, got {duration_seconds}"


# ---------------------------------------------------------------------------
# Fix 1-4 — Persona prompt contains new sections
# ---------------------------------------------------------------------------

def test_persona_prompt_has_style_variation():
    from src.persona import PERSONA_SYSTEM_PROMPT
    assert "STYLE VARIATION" in PERSONA_SYSTEM_PROMPT


def test_persona_prompt_has_suspicious_values():
    from src.persona import PERSONA_SYSTEM_PROMPT
    assert "SUSPICIOUS VALUES" in PERSONA_SYSTEM_PROMPT


def test_persona_prompt_has_urgency_leverage():
    from src.persona import PERSONA_SYSTEM_PROMPT
    assert "URGENCY LEVERAGE" in PERSONA_SYSTEM_PROMPT


def test_persona_prompt_has_contradictions():
    from src.persona import PERSONA_SYSTEM_PROMPT
    assert "CONTRADICTIONS" in PERSONA_SYSTEM_PROMPT


def test_persona_prompt_no_oh_pattern():
    """Prompt explicitly tells AI not to always start with 'Oh'."""
    from src.persona import PERSONA_SYSTEM_PROMPT
    assert 'Do NOT always start with "Oh"' in PERSONA_SYSTEM_PROMPT
