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
            "order_numbers": []
        })

        with patch("src.llm_client.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_resp

            # Call the function
            result = await extract_llm_intelligence("I am from Delhi. My case is CASE-123. I won't give you my phone number or email.")

            # Verify results
            self.assertEqual(result["misc_notes"], "User mentioned being from Delhi.")

            self.assertIn("phone_numbers", result["denied_fields"])
            self.assertIn("email_addresses", result["denied_fields"])
            self.assertNotIn("bank_accounts", result["denied_fields"])

            # Verify reference ID extraction
            self.assertEqual(result["case_ids"], ["CASE-123"])
            self.assertEqual(result["policy_numbers"], [])
            self.assertEqual(result["order_numbers"], [])

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

    def test_employee_id_extraction(self):
        """Test that employee IDs are extracted via regex."""
        from src.extractor import extract_intelligence_regex
        result = extract_intelligence_regex("My employee ID is EMP12345 and my agent ID is AGENT-789")
        self.assertIn("EMP12345", result.employee_ids)
        self.assertIn("AGENT-789", result.employee_ids)

if __name__ == "__main__":
    unittest.main()
