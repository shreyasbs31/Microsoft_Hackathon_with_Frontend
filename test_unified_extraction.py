import unittest
import asyncio
import sys
import os
import json
from unittest.mock import AsyncMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from src.extractor import extract_llm_intelligence

class TestUnifiedExtraction(unittest.TestCase):
    def test_success(self):
        asyncio.run(self._test_extract_llm_intelligence_success())

    async def _test_extract_llm_intelligence_success(self):
        # Mock response from LLM
        mock_resp = json.dumps({
            "misc_notes": "User mentioned being from Delhi.",
            "phone_numbers_denied": True,
            "bank_accounts_denied": False,
            "upi_ids_denied": False,
            "urls_denied": False,
            "email_addresses_denied": True,
            "ifsc_codes_denied": False,
            "case_ids": ["CASE-123"],
            "policy_numbers": [],
            "order_numbers": [],
            "employee_ids": ["SBI-12345"]
        })

        with patch("src.llm_client.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_resp

            # Call the function
            result = await extract_llm_intelligence("I am from Delhi. My case is CASE-123. I won't give you my phone number or email. My ID is SBI-12345.")

            # Verify results
            self.assertEqual(result["misc_notes"], "User mentioned being from Delhi.")

            self.assertIn("phone_numbers", result["denied_fields"])
            self.assertIn("email_addresses", result["denied_fields"])
            self.assertNotIn("bank_accounts", result["denied_fields"])

            # Verify reference ID extraction
            self.assertEqual(result["case_ids"], ["CASE-123"])
            self.assertEqual(result["policy_numbers"], [])
            self.assertEqual(result["order_numbers"], [])
            self.assertEqual(result["employee_ids"], ["SBI-12345"])

    def test_failure(self):
        asyncio.run(self._test_json_failure())

    async def _test_json_failure(self):
        with patch("src.llm_client.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "NOT JSON"
            result = await extract_llm_intelligence("foo")
            self.assertEqual(result["misc_notes"], "")
            self.assertEqual(len(result["denied_fields"]), 0)
            self.assertEqual(result["case_ids"], [])
            self.assertEqual(result["policy_numbers"], [])
            self.assertEqual(result["order_numbers"], [])
            self.assertEqual(result["employee_ids"], [])

    def test_employee_id_extraction(self):
        """Test that employee IDs are extracted via regex."""
        from src.extractor import extract_intelligence_regex
        result = extract_intelligence_regex("My employee ID is EMP12345 and my agent ID is AGENT-789")
        self.assertIn("EMP12345", result.employee_ids)
        self.assertIn("AGENT-789", result.employee_ids)

    def test_employee_id_sbi_format(self):
        """Test SBI-style employee IDs."""
        from src.extractor import extract_intelligence_regex
        result = extract_intelligence_regex("I'm calling from SBI fraud department. My ID is SBI-12345.")
        self.assertIn("SBI-12345", result.employee_ids)

    def test_employee_id_stopwords(self):
        """Test that common words are NOT captured as employee IDs."""
        from src.extractor import extract_intelligence_regex
        result = extract_intelligence_regex("I am an agent from the department")
        # Should NOT capture "department" or "from" as employee IDs
        for eid in result.employee_ids:
            self.assertNotIn(eid.lower(), ["department", "from", "the"])

    def test_ifsc_not_captured_as_employee_id(self):
        """Test that IFSC codes like SBIN0001234 are NOT captured as employee IDs."""
        from src.extractor import extract_intelligence_regex
        result = extract_intelligence_regex("The IFSC for your branch is SBIN0001234")
        self.assertNotIn("SBIN0001234", result.employee_ids)
        # But it SHOULD be captured as IFSC
        self.assertIn("SBIN0001234", result.ifsc_codes)

    def test_case_id_not_captured_as_employee_id(self):
        """Test that case IDs are NOT captured as employee IDs via generic id context."""
        from src.extractor import extract_intelligence_regex
        result = extract_intelligence_regex("Your case ID is 2023-4567. Please proceed.")
        self.assertNotIn("2023-4567", result.employee_ids)

    def test_bank_account_excludes_reference_ids(self):
        """Test that digits embedded in reference IDs are NOT captured as bank accounts."""
        from src.extractor import extract_intelligence_regex
        text = "Your account is blocked. Reference is REF-2023-98765. Policy is POL-2023-98765."
        result = extract_intelligence_regex(text)
        self.assertNotIn("202398765", result.bank_accounts)

    def test_upi_email_reclassification_requires_tld(self):
        """Test that UPI→email reclassification requires a TLD (dot after @)."""
        from src.extractor import extract_intelligence_regex
        text = "Send to my email scammer.fraud@fakebank for processing"
        result = extract_intelligence_regex(text)
        # No TLD → should NOT appear in emails
        self.assertNotIn("scammer.fraud@fakebank", result.email_addresses)

    def test_upi_email_reclassification_with_tld(self):
        """Test that UPI→email reclassification works when TLD is present."""
        from src.extractor import extract_intelligence_regex
        text = "Send to my email support@fakebank.com for processing"
        result = extract_intelligence_regex(text)
        self.assertIn("support@fakebank.com", result.email_addresses)

    def test_llm_employee_word_filtered(self):
        """Test that the literal word 'employee' is filtered from LLM employee_ids."""
        asyncio.run(self._test_llm_employee_word_filtered())

    async def _test_llm_employee_word_filtered(self):
        import json
        mock_resp = json.dumps({
            "misc_notes": "",
            "phone_numbers_denied": False,
            "bank_accounts_denied": False,
            "upi_ids_denied": False,
            "urls_denied": False,
            "email_addresses_denied": False,
            "ifsc_codes_denied": False,
            "case_ids": [],
            "policy_numbers": [],
            "order_numbers": [],
            "employee_ids": ["employee", "98765", "EMP-123"]
        })
        with patch("src.llm_client.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_resp
            result = await extract_llm_intelligence("test text")
            # "employee" (no digits) should be filtered out
            self.assertNotIn("employee", result["employee_ids"])
            # "98765" has no alpha, but has digits — it should pass
            # "EMP-123" has digits and is valid
            self.assertIn("EMP-123", result["employee_ids"])

    def test_merge_deconflicts_bank_vs_case_ids(self):
        """Test that merge_intelligence removes bank accounts matching reference ID digits."""
        from src.extractor import merge_intelligence, ExtractedIntelligence
        existing = {
            "phone_numbers": [], "bank_accounts": ["202398765"],
            "upi_ids": [], "urls": [], "email_addresses": [],
            "ifsc_codes": [], "suspicious_keywords": [],
            "case_ids": ["REF-2023-98765"], "policy_numbers": [],
            "order_numbers": [], "employee_ids": [],
        }
        new_intel = ExtractedIntelligence()
        merged = merge_intelligence(existing, new_intel)
        self.assertNotIn("202398765", merged["bank_accounts"])

    def test_upi_prefix_of_email_excluded(self):
        """Test that UPI candidates that are prefixes of emails are excluded.
        E.g. secure@sbi matched from secure@sbi-verify.com should NOT be a UPI."""
        from src.extractor import extract_intelligence_regex
        text = "You can email your OTP to secure@sbi-verify.com to stop the block"
        result = extract_intelligence_regex(text)
        # secure@sbi should NOT appear as UPI
        self.assertNotIn("secure@sbi", result.upi_ids)
        # But secure@sbi-verify.com SHOULD be an email
        self.assertIn("secure@sbi-verify.com", result.email_addresses)

if __name__ == "__main__":
    unittest.main()
