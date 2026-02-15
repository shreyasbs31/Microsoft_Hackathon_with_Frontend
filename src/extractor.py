"""
Intelligence extractor — regex for structured fields, LLM for misc notes.

Uses regex patterns to reliably extract structured data (phones, banks,
UPIs, URLs, emails, IFSC codes, keywords). Uses an LLM call to extract
miscellaneous contextual intelligence (names, orgs, threats, etc.) that
gets appended to agent_notes.
"""

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExtractedIntelligence:
    phone_numbers: list[str] = field(default_factory=list)
    bank_accounts: list[str] = field(default_factory=list)
    upi_ids: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    email_addresses: list[str] = field(default_factory=list)
    ifsc_codes: list[str] = field(default_factory=list)
    suspicious_keywords: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM-based misc-notes extraction
# ---------------------------------------------------------------------------

_MISC_NOTES_SYSTEM_PROMPT = """\
You are a forensic analyst reviewing a scammer's message in a honeypot investigation.

Your ONLY job is to extract **contextual intelligence** that is NOT a phone number,
bank account, UPI ID, URL, email, IFSC code, or keyword. Those are handled separately.

Focus on:
- Names of people or organisations mentioned or impersonated
- Physical addresses or locations
- App names, platform names
- Reference / transaction / case IDs
- Threats made or pressure tactics described
- Impersonated entities (banks, government bodies, companies)
- Any other notable contextual detail

Respond with a SHORT, factual, single-paragraph summary (1-3 sentences).
If there is nothing noteworthy beyond the structured fields, respond with exactly: NONE"""


async def extract_misc_notes(text: str) -> str:
    """
    Call the LLM to extract miscellaneous contextual intelligence.
    Returns a short summary string, or empty string on failure / nothing found.
    """
    from src.llm_client import call_llm

    try:
        raw = await call_llm(
            role="extractor",
            system_prompt=_MISC_NOTES_SYSTEM_PROMPT,
            user_prompt=f"Analyse this scammer message:\n\n{text}",
            json_mode=False,
        )
        raw = raw.strip()
        if raw.upper() == "NONE" or not raw:
            return ""
        return raw
    except Exception as exc:
        logger.warning("LLM misc-notes extraction failed: %s", exc)
        return ""


# =========================================================================
# REGEX FALLBACK  (original implementation)
# =========================================================================

# Indian mobile: optional +91/91 prefix, 10 digits starting with 6-9
# Allows spaces, dots, hyphens between digit groups
_PHONE_INDIA = re.compile(
    r'(?<!\d)(?:\+?91[-.\s]?)?[6-9][\d\s.\-]{8,13}\d(?!\d)'
)
# International: requires explicit + prefix, then 8-15 total digits
_PHONE_INTL = re.compile(
    r'\+\d[\d\s.\-]{5,18}\d(?!\d)'
)

# UPI ID: user@provider  (known Indian UPI suffixes + general fallback)
_UPI_SUFFIXES = (
    "upi", "paytm", "ybl", "oksbi", "okaxis", "okicici", "okhdfcbank",
    "fbl", "ibl", "axl", "sbi", "apl", "boi", "cnrb", "csbpay", "dlb",
    "federal", "idbi", "indus", "kbl", "kotak", "mahb", "pnb", "rbl",
    "uco", "union", "united", "vijb", "dbs", "fakebank", "fakeupi",
    "gpay", "amazonpay", "axisbank", "icici", "hdfcbank",
    "yesbank", "yesbankltd", "airtel", "bhim", "postbank", "jupiteraxis",
    "slice", "fam", "idfcfirst", "rblbank", "aubank", "equitas",
    "bandhan", "citi", "dbs", "hsbc", "scb", "barb", "abfspay",
    "waaxis", "wahdfcbank", "waicici", "wasbi",
)
# Known suffix pattern (high confidence)
_UPI_KNOWN = re.compile(
    r'\b[\w.\-]+@(?:' + '|'.join(_UPI_SUFFIXES) + r')\b(?!\.[a-zA-Z]{2,})',
    re.IGNORECASE,
)
# General fallback: word@word without a TLD (catches unknown UPI providers)
_UPI_GENERAL = re.compile(
    r'\b[\w.\-]+@[a-zA-Z][a-zA-Z0-9]{1,20}\b(?!\.[a-zA-Z]{2,})',
    re.IGNORECASE,
)

# URLs (normal + defanged + shorteners)
_URL_PATTERN = re.compile(
    r'(?:https?|hxxps?|h\[tt\]ps?)://[^\s<>"\']+'
    r'|www\.[^\s<>"\']+'
    r'|\b(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|is\.gd|buff\.ly|ow\.ly|rb\.gy)[/\\][^\s<>"\']+',
    re.IGNORECASE,
)
# Defanged notation normaliser: hxxp -> http, [.] -> .
def _deobfuscate_url(url: str) -> str:
    url = re.sub(r'hxxp', 'http', url, flags=re.IGNORECASE)
    url = re.sub(r'h\[tt\]p', 'http', url, flags=re.IGNORECASE)
    url = url.replace('[.]', '.').replace('[:]', ':')
    return url

# Email (generic)
_EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
)

# IFSC code: 4 uppercase alpha + '0' + 6 alphanumeric
_IFSC_PATTERN = re.compile(
    r'\b[A-Z]{4}0[A-Z0-9]{6}\b'
)

# Bank account number: 9-18 digits, allow spaces/dashes in between
_BANK_ACCOUNT_DIGITS = re.compile(r'\b(?:\d[\s-]?){9,18}\d\b')
_BANK_CONTEXT_KEYWORDS = re.compile(
    r'account|a/c|acc\b|bank|number|no\.|credit|debit|savings|current',
    re.IGNORECASE,
)

# Suspicious keywords
_SCAM_KEYWORDS = [
    "urgent", "blocked", "verify", "otp", "compromised", "suspend",
    "immediately", "expire", "penalty", "freeze", "unauthorized",
    "kyc", "update", "click here", "act now", "limited time",
    "cashback", "refund", "lottery", "prize", "winner", "claim",
    "offer", "deal", "discount", "free", "gift", "reward",
]


def normalise_text(text: str) -> str:
    """Strip excess whitespace and decode common URL-encoded characters."""
    import urllib.parse
    text = urllib.parse.unquote(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_intelligence_regex(text: str) -> ExtractedIntelligence:
    """
    Run all regex patterns against *text* and return structured results.
    Used as fallback when LLM extraction fails.
    """
    result = ExtractedIntelligence()

    # 1. UPI IDs  (extract first so we can exclude from emails)
    # Known-suffix matches (high confidence) + general fallback
    upi_matches: list[str] = _UPI_KNOWN.findall(text)
    for candidate in _UPI_GENERAL.findall(text):
        if candidate.lower() not in {m.lower() for m in upi_matches}:
            upi_matches.append(candidate)
    result.upi_ids = list(set(upi_matches))
    upi_set = set(m.lower() for m in upi_matches)

    # 2. Email addresses  (exclude UPI matches)
    email_matches = _EMAIL_PATTERN.findall(text)
    result.email_addresses = list(
        set(e for e in email_matches if e.lower() not in upi_set)
    )

    # 3. Phone numbers (Indian + international formats)
    phones: set[str] = set()
    for m in _PHONE_INDIA.finditer(text):
        normalised = _normalise_phone(m.group())
        digit_count = len(re.sub(r'\D', '', normalised))
        if 10 <= digit_count <= 12:  # Indian: 10 digits, or 12 with 91 prefix
            phones.add(normalised)
    for m in _PHONE_INTL.finditer(text):
        normalised = _normalise_phone(m.group())
        digit_count = len(re.sub(r'\D', '', normalised))
        if 8 <= digit_count <= 15:
            phones.add(normalised)
    result.phone_numbers = list(phones)

    # 4. URLs (deobfuscate defanged notation)
    raw_urls = _URL_PATTERN.findall(text)
    result.urls = list(set(_deobfuscate_url(u) for u in raw_urls))

    # 5. IFSC codes
    result.ifsc_codes = list(set(_IFSC_PATTERN.findall(text)))

    # 6. Bank account numbers  (contextual)
    result.bank_accounts = _extract_bank_accounts(text)

    # 6b. Cross-deconflict phones ↔ bank accounts ↔ UPI
    phone_digit_set = {re.sub(r'\D', '', p) for p in result.phone_numbers}
    upi_locals = {u.split('@')[0] for u in result.upi_ids if '@' in u}

    # Remove bank accounts whose digits match a phone number
    result.bank_accounts = [
        a for a in result.bank_accounts
        if re.sub(r'\D', '', a) not in phone_digit_set
    ]

    # Remove phones that are UPI local parts
    result.phone_numbers = [
        p for p in result.phone_numbers
        if re.sub(r'\D', '', p) not in upi_locals
    ]

    # 7. Suspicious keywords
    text_lower = text.lower()
    result.suspicious_keywords = [
        kw for kw in _SCAM_KEYWORDS if kw in text_lower
    ]

    return result


def _normalise_phone(raw: str) -> str:
    """Normalise a phone string to canonical format.
    Indian numbers → +91-XXXXXXXXXX
    International numbers → +CC-remaining digits
    Local numbers → digits only
    """
    raw = raw.strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r'\D', '', raw)

    # Indian number: 10 digits starting with 6-9, or 12 digits with 91 prefix
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return "+91-" + digits[2:]
    if len(digits) == 10 and digits[0] in "6789":
        return "+91-" + digits
    # International with + prefix
    if has_plus and len(digits) >= 8:
        cc = digits[:2] if len(digits) <= 12 else digits[:3]
        rest = digits[len(cc):]
        return "+" + cc + "-" + rest
    # Fallback: return digits with + if originally present
    return "+" + digits if has_plus else digits



def _is_boilerplate_number(digits: str) -> bool:
    """
    Returns True if the digit string is a boilerplate/placeholder pattern:
    - Sequential ascending (123456...)
    - Sequential descending (987654...)
    - All same digit (111111...)
    - Short repeating pattern (e.g. 12341234, period <= 4)
    """
    if len(set(digits)) == 1:
        return True  # all same digit
    # Ascending/descending sequence
    asc = ''.join(str((int(digits[0]) + i) % 10) for i in range(len(digits)))
    desc = ''.join(str((int(digits[0]) - i) % 10) for i in range(len(digits)))
    if digits == asc or digits == desc:
        return True
    # Short repeating pattern (period <= 4)
    for period in range(1, 5):
        if len(digits) % period == 0:
            pat = digits[:period]
            if pat * (len(digits) // period) == digits:
                return True
    return False

def _extract_bank_accounts(text: str) -> list[str]:
    """
    Extract digit sequences that look like bank account numbers,
    but only if banking-related keywords appear within a 80-char window.
    Rejects boilerplate/placeholder numbers (e.g. 1234567890123456).
    """
    results: set[str] = set()
    for match in _BANK_ACCOUNT_DIGITS.finditer(text):
        raw = match.group()
        digits = re.sub(r'\D', '', raw)
        if not (9 <= len(digits) <= 18):
            continue
        if _is_boilerplate_number(digits):
            continue
        start = max(0, match.start() - 120)
        end = min(len(text), match.end() + 120)
        window = text[start:end]
        if _BANK_CONTEXT_KEYWORDS.search(window):
            results.add(digits)
    return list(results)


def merge_intelligence(
    existing: dict[str, list],
    new: ExtractedIntelligence,
) -> dict[str, list]:
    """
    Merge newly extracted intel into existing session intel.
    Returns a new dict with deduplicated, sorted lists.
    """
    merged: dict[str, list] = {}
    for key in (
        "phone_numbers", "bank_accounts", "upi_ids",
        "urls", "email_addresses", "ifsc_codes", "suspicious_keywords",
    ):
        existing_set = set(existing.get(key, []))
        new_set = set(getattr(new, key, []))
        merged[key] = sorted(existing_set | new_set)
    return merged
