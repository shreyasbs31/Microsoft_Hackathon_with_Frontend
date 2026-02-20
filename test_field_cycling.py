"""
Tests for the field cycling logic in persona._build_priority_instructions
and the single-value confirmation detection in extractor.

Run: python -m pytest test_field_cycling.py -v
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Single-value confirmation detection tests
# ---------------------------------------------------------------------------

def test_detect_single_value_phone():
    from src.extractor import detect_single_value_confirmations
    text = "That's the only number I have, sir."
    result = detect_single_value_confirmations(text)
    assert "phone_numbers" in result


def test_detect_single_value_account():
    from src.extractor import detect_single_value_confirmations
    text = "I only have one account with the bank."
    result = detect_single_value_confirmations(text)
    assert "bank_accounts" in result


def test_detect_single_value_email():
    from src.extractor import detect_single_value_confirmations
    text = "That is my only email address."
    result = detect_single_value_confirmations(text)
    assert "email_addresses" in result


def test_detect_single_value_none():
    from src.extractor import detect_single_value_confirmations
    text = "Please send the OTP to proceed with verification."
    result = detect_single_value_confirmations(text)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Phase 1 → Phase 2 transition
# ---------------------------------------------------------------------------

def test_phase1_urgent_fields():
    """When some fields have 0 count, those should be flagged as URGENT."""
    from src.persona import _build_priority_instructions
    counts = {
        "phone_numbers": 1,
        "bank_accounts": 0,
        "upi_ids": 0,
        "urls": 1,
        "email_addresses": 0,
        "ifsc_codes": 1,
    }
    instructions, state = _build_priority_instructions(counts, {})
    assert "URGENT" in instructions
    assert "bank accounts" in instructions
    assert "upi ids" in instructions
    assert "email addresses" in instructions
    assert not state["initial_cycle_complete"]


def test_phase2_transition():
    """When all fields have ≥1, should transition to cycling mode."""
    from src.persona import _build_priority_instructions
    counts = {
        "phone_numbers": 1,
        "bank_accounts": 1,
        "upi_ids": 1,
        "urls": 1,
        "email_addresses": 1,
        "ifsc_codes": 1,
        "case_ids": 1,
        "policy_numbers": 1,
        "order_numbers": 1,
    }
    instructions, state = _build_priority_instructions(counts, {})
    assert "URGENT" not in instructions
    assert state["initial_cycle_complete"]
    assert "ADDITIONAL" in instructions or "additional" in instructions.lower()


# ---------------------------------------------------------------------------
# Field exhaustion after max asks
# ---------------------------------------------------------------------------

def test_field_exhaustion_after_max_asks():
    """After 3 asks without new data, field should be auto-exhausted."""
    from src.persona import _build_priority_instructions, _MAX_ASKS_BEFORE_EXHAUST

    counts = {
        "phone_numbers": 1,
        "bank_accounts": 1,
        "upi_ids": 1,
        "urls": 1,
        "email_addresses": 1,
        "ifsc_codes": 1,
        "case_ids": 1,
        "policy_numbers": 1,
        "order_numbers": 1,
    }

    state = {"initial_cycle_complete": True}

    # With 6 fields cycling round-robin, we need at least
    # 6 fields × MAX_ASKS iterations for the first field to pass threshold
    # plus extra iterations for the exhaustion check to trigger on next pass
    total_iterations = 6 * (_MAX_ASKS_BEFORE_EXHAUST) + 1
    for i in range(total_iterations):
        instructions, state = _build_priority_instructions(counts, state)

    assert len(state["exhausted_fields"]) > 0, "At least one field should be exhausted"


def test_all_exhausted_general_engagement():
    """When all fields are exhausted, should get general engagement instructions."""
    from src.persona import _build_priority_instructions

    counts = {
        "phone_numbers": 1,
        "bank_accounts": 1,
        "upi_ids": 1,
        "urls": 1,
        "email_addresses": 1,
        "ifsc_codes": 1,
        "case_ids": 1,
        "policy_numbers": 1,
        "order_numbers": 1,
    }

    state = {
        "initial_cycle_complete": True,
        "exhausted_fields": [
            "phone_numbers", "bank_accounts", "upi_ids",
            "urls", "email_addresses", "ifsc_codes",
            "case_ids", "policy_numbers", "order_numbers",
        ],
    }

    instructions, state = _build_priority_instructions(counts, state)
    assert "exhausted" in instructions.lower() or "engaged" in instructions.lower()
    assert "URGENT" not in instructions


# ---------------------------------------------------------------------------
# Exhausted fields from denials feed into cycling
# ---------------------------------------------------------------------------

def test_denied_fields_skip_in_cycling():
    """Exhausted fields should not be targeted during cycling."""
    from src.persona import _build_priority_instructions

    counts = {
        "phone_numbers": 1,
        "bank_accounts": 1,
        "upi_ids": 1,
        "urls": 1,
        "email_addresses": 1,
        "ifsc_codes": 1,
        "case_ids": 1,
        "policy_numbers": 1,
        "order_numbers": 1,
    }

    state = {
        "initial_cycle_complete": True,
        "exhausted_fields": ["phone_numbers", "bank_accounts"],
    }

    # Run several cycling turns and check that exhausted fields are never targeted
    targeted = set()
    for _ in range(10):
        instructions, state = _build_priority_instructions(counts, state)
        for field in ["phone numbers", "bank accounts"]:
            # The exhausted fields should not appear in the target instruction
            # (unless in the "all exhausted" message)
            if "exhausted" not in instructions.lower() and "engaged" not in instructions.lower():
                assert field not in instructions.lower(), \
                    f"Exhausted field '{field}' should not be targeted"


# ---------------------------------------------------------------------------
# New data resets ask count
# ---------------------------------------------------------------------------

def test_new_data_resets_ask_count():
    """If new data appears for a field, its ask count should reset."""
    from src.persona import _build_priority_instructions

    counts_t1 = {
        "phone_numbers": 1,
        "bank_accounts": 1,
        "upi_ids": 1,
        "urls": 1,
        "email_addresses": 1,
        "ifsc_codes": 1,
        "case_ids": 1,
        "policy_numbers": 1,
        "order_numbers": 1,
    }

    state = {"initial_cycle_complete": True}

    # Ask twice
    _, state = _build_priority_instructions(counts_t1, state)
    _, state = _build_priority_instructions(counts_t1, state)

    # Simulate new phone number extracted
    counts_t2 = dict(counts_t1)
    counts_t2["phone_numbers"] = 2

    _, state = _build_priority_instructions(counts_t2, state)

    # phone_numbers ask count should have been reset
    assert state["field_ask_counts"]["phone_numbers"] <= 1


# ---------------------------------------------------------------------------
# Expanded denial pattern tests
# ---------------------------------------------------------------------------

def test_denial_url_implicit_link():
    """'Cannot provide a link' should detect urls denial."""
    from src.extractor import detect_denials
    result = detect_denials("We cannot provide a link for security reasons.")
    assert "urls" in result


def test_denial_url_portal():
    """'No portal available' should detect urls denial."""
    from src.extractor import detect_denials
    result = detect_denials("Sorry, there is no portal available for this.")
    assert "urls" in result


def test_denial_email_security():
    """'For security reasons we cannot email' should detect email denial."""
    from src.extractor import detect_denials
    result = detect_denials("For security reasons we cannot email you the details.")
    assert "email_addresses" in result


def test_denial_no_false_positive():
    """'Please send the OTP' should NOT trigger any denial."""
    from src.extractor import detect_denials
    result = detect_denials("Please send the OTP you received right now.")
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Approach categoriser tests
# ---------------------------------------------------------------------------

def test_approach_categoriser_link():
    import asyncio
    from src.persona import _summarise_approach
    result = asyncio.get_event_loop().run_until_complete(
        _summarise_approach("Can you send me a link to the official SBI portal?")
    )
    assert result == "ask-for-verification"


def test_approach_categoriser_confusion():
    import asyncio
    from src.persona import _summarise_approach
    result = asyncio.get_event_loop().run_until_complete(
        _summarise_approach("I'm so confused by this. What do you mean by OTP?")
    )
    assert result == "express-confusion"


def test_approach_categoriser_delay():
    import asyncio
    from src.persona import _summarise_approach
    result = asyncio.get_event_loop().run_until_complete(
        _summarise_approach("Hold on, let me just check my other accounts first.")
    )
    assert result == "delay-tactic"

