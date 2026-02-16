def test_detect_denials_and_adjust_counts():
    from src.extractor import detect_denials, adjust_counts_for_denials

    text = "We cannot email you for security reasons, please send OTP via UPI"
    denied = detect_denials(text)
    assert "email_addresses" in denied

    counts = {
        "phone_numbers": 0,
        "bank_accounts": 0,
        "upi_ids": 0,
        "urls": 0,
        "email_addresses": 0,
        "ifsc_codes": 0,
    }

    adjusted = adjust_counts_for_denials(counts, denied)
    assert adjusted["email_addresses"] == 999
    # other fields unchanged
    assert adjusted["upi_ids"] == 0
