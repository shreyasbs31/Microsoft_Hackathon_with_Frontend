import unittest
import asyncio
import sys
import os
import json
from unittest.mock import AsyncMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from src.extractor import extract_contextual_intelligence

class TestUnifiedExtraction(unittest.TestCase):
    def test_success(self):
        asyncio.run(self._test_extract_contextual_intelligence_success())

    async def _test_extract_contextual_intelligence_success(self):
        # Mock response from LLM
        mock_resp = json.dumps({
            "misc_notes": "User mentioned being from Delhi.",
            "reference_ids": {
                "case_ids": ["CASE-123"],
                "policy_numbers": ["POL-456"],
                "order_numbers": []
            },
            "denials": {
                "phone_numbers_denied": True,
                "bank_accounts_denied": False,
                "upi_ids_denied": False,
                "urls_denied": False,
                "email_addresses_denied": True,
                "ifsc_codes_denied": False
            }
        })

        with patch("src.llm_client.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_resp

            # Call the function
            result = await extract_contextual_intelligence("I am from Delhi. My case is CASE-123. I won't give you my phone number or email.")

            # Verify results
            self.assertEqual(result["misc_notes"], "User mentioned being from Delhi.")
            self.assertIn("CASE-123", result["reference_ids"]["case_ids"])
            self.assertIn("POL-456", result["reference_ids"]["policy_numbers"])
            self.assertEqual(len(result["reference_ids"]["order_numbers"]), 0)

            self.assertIn("phone_numbers", result["denied_fields"])
            self.assertIn("email_addresses", result["denied_fields"])
            self.assertNotIn("bank_accounts", result["denied_fields"])

    def test_failure(self):
        asyncio.run(self._test_json_failure())

    async def _test_json_failure(self):
        with patch("src.llm_client.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "NOT JSON"
            result = await extract_contextual_intelligence("foo")
            self.assertEqual(result["misc_notes"], "")

if __name__ == "__main__":
    unittest.main()
