"""
Test the exact analyst + persona pipeline the server uses.
Run: python test_pipeline.py
"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

async def main():
    from src.analyst import analyse_message
    from src.persona import generate_response
    from src.extractor import extract_intelligence, normalise_text

    test_msg = "URGENT: Your SBI account has been compromised. Share OTP immediately."
    
    print("=== Step 1: Regex Extraction ===")
    normalised = normalise_text(test_msg)
    intel = extract_intelligence(normalised)
    print(f"  Extracted: {intel}")
    
    intel_dict = {
        "phone_numbers": intel.phone_numbers,
        "bank_accounts": intel.bank_accounts,
        "upi_ids": intel.upi_ids,
        "urls": intel.urls,
        "email_addresses": intel.email_addresses,
        "ifsc_codes": intel.ifsc_codes,
        "suspicious_keywords": intel.suspicious_keywords,
    }

    print("\n=== Step 2: Analyst LLM ===")
    try:
        result = await analyse_message(
            current_message=normalised,
            conversation_history=[],
            extracted_intel=intel_dict,
        )
        print(f"  Status: {result.status}")
        print(f"  Scam type: {result.scam_type}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Reasoning: {result.reasoning[:200]}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("\n=== Step 3: Persona LLM ===")
    try:
        reply, approach = await generate_response(
            current_message=normalised,
            conversation_history=[],
            session_status="HONEYPOT",
            scam_type="bank_fraud",
            turn_count=1,
            intel_counts={"phone_numbers": 0, "bank_accounts": 0, "upi_ids": 0, "urls": 0, "email_addresses": 0, "ifsc_codes": 0},
            last_approach="",
            language="English",
        )
        print(f"  Reply: {reply}")
        print(f"  Approach: {approach}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("\nDone.")

asyncio.run(main())
