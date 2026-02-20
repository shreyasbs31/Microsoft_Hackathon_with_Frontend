def test_adjust_counts():
    from src.extractor import adjust_counts_for_denials

    denied = {"phone_numbers"}
    counts = {"phone_numbers": 1, "bank_accounts": 2, "urls": 5}
    adjusted = adjust_counts_for_denials(counts, denied)

    assert adjusted["phone_numbers"] == 999
    assert adjusted["bank_accounts"] == 2
    assert adjusted["urls"] == 5
