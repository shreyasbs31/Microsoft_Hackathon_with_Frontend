import unittest
import asyncio
import sys
import os
import json
from unittest.mock import AsyncMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from src.extractor import extract_and_detect_denials

class TestUnifiedExtraction(unittest.TestCase):
    def test_success(self):
        asyncio.run(self._test_extract_and_detect_denials_success())

    async def _test_extract_and_detect_denials_success(self):
        # Mock response from LLM
        mock_resp = json.dumps({
            "misc_notes": "User mentioned being from Delhi.",
            "phone_numbers_denied": True,
            "bank_accounts_denied": False,
            "upi_ids_denied": False,
            "urls_denied": False,
            "email_addresses_denied": True,
            "ifsc_codes_denied": False
        })

        with patch("src.llm_client.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_resp

            # Call the function
            result = await extract_and_detect_denials("I am from Delhi. My case is CASE-123. I won't give you my phone number or email.")

            # Verify results
            self.assertEqual(result["misc_notes"], "User mentioned being from Delhi.")

            self.assertIn("phone_numbers", result["denied_fields"])
            self.assertIn("email_addresses", result["denied_fields"])
            self.assertNotIn("bank_accounts", result["denied_fields"])

    def test_failure(self):
        asyncio.run(self._test_json_failure())

    async def _test_json_failure(self):
        with patch("src.llm_client.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "NOT JSON"
            result = await extract_and_detect_denials("foo")
            self.assertEqual(result["misc_notes"], "")
            self.assertEqual(len(result["denied_fields"]), 0)

if __name__ == "__main__":
    unittest.main()
