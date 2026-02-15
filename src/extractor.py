"""
Regex-based intelligence extractor.

Runs on every incoming scammer message to extract:
- Phone numbers (Indian & international)
- Bank account numbers (with contextual keyword matching)
- UPI IDs
- URLs / phishing links
- Email addresses
- IFSC codes
"""

import re
from dataclasses import dataclass, field


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
# Regex patterns
# ---------------------------------------------------------------------------

# Indian mobile: +91-XXXXXXXXXX or 91XXXXXXXXXX or XXXXXXXXXX (starts with 6-9)
_PHONE_INDIA = re.compile(
    r'(?:\+?91[-.\s]?)?[6-9]\d{9}\b'
)
# International: +CC-NNN-NNN-NNNN style
_PHONE_INTL = re.compile(
    r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
)

# UPI ID: user@provider  (known Indian UPI suffixes)
_UPI_SUFFIXES = (
    "upi", "paytm", "ybl", "oksbi", "okaxis", "okicici", "okhdfcbank",
    "fbl", "ibl", "axl", "sbi", "apl", "boi", "cnrb", "csbpay", "dlb",
    "federal", "idbi", "indus", "kbl", "kotak", "mahb", "pnb", "rbl",
    "uco", "union", "united", "vijb", "dbs", "fakebank", "fakeupi",
    "gpay", "amazonpay", "axisbank", "icici", "hdfcbank",
)
_UPI_PATTERN = re.compile(
    r'\b[\w.\-]+@(?:' + '|'.join(_UPI_SUFFIXES) + r')\b',
    re.IGNORECASE,
)

# URLs
_URL_PATTERN = re.compile(
    r'https?://[^\s<>"\']+|www\.[^\s<>"\']+',
    re.IGNORECASE,
)

# Email (generic)
_EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
)

# IFSC code: 4 uppercase alpha + '0' + 6 alphanumeric
_IFSC_PATTERN = re.compile(
    r'\b[A-Z]{4}0[A-Z0-9]{6}\b'
)

# Bank account number: 9-18 digits only near banking context keywords
_BANK_ACCOUNT_DIGITS = re.compile(r'\b\d{9,18}\b')
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


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def normalise_text(text: str) -> str:
    """Strip excess whitespace and decode common URL-encoded characters."""
    import urllib.parse
    text = urllib.parse.unquote(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_intelligence(text: str) -> ExtractedIntelligence:
    """
    Run all regex patterns against *text* and return structured results.
    """
    result = ExtractedIntelligence()

    # 1. UPI IDs  (extract first so we can exclude from emails)
    upi_matches = _UPI_PATTERN.findall(text)
    result.upi_ids = list(set(upi_matches))
    upi_set = set(m.lower() for m in upi_matches)

    # 2. Email addresses  (exclude UPI matches)
    email_matches = _EMAIL_PATTERN.findall(text)
    result.email_addresses = list(
        set(e for e in email_matches if e.lower() not in upi_set)
    )

    # 3. Phone numbers
    phones: set[str] = set()
    for m in _PHONE_INDIA.findall(text):
        phones.add(_normalise_phone(m))
    for m in _PHONE_INTL.findall(text):
        normalised = _normalise_phone(m)
        # Avoid capturing bank-account-length digit strings as phones
        if len(re.sub(r'\D', '', normalised)) <= 13:
            phones.add(normalised)
    result.phone_numbers = list(phones)

    # 4. URLs
    result.urls = list(set(_URL_PATTERN.findall(text)))

    # 5. IFSC codes
    result.ifsc_codes = list(set(_IFSC_PATTERN.findall(text)))

    # 6. Bank account numbers  (contextual)
    result.bank_accounts = _extract_bank_accounts(text)

    # 7. Suspicious keywords
    text_lower = text.lower()
    result.suspicious_keywords = [
        kw for kw in _SCAM_KEYWORDS if kw in text_lower
    ]

    return result


def _normalise_phone(raw: str) -> str:
    """Normalise a phone string: strip spaces/dashes, keep + prefix."""
    cleaned = re.sub(r'[().\s]', '', raw)
    # Normalise dashes: keep only one at country-code boundary
    cleaned = re.sub(r'-+', '-', cleaned)
    return cleaned


def _extract_bank_accounts(text: str) -> list[str]:
    """
    Extract digit sequences that look like bank account numbers,
    but only if banking-related keywords appear within a 80-char window.
    """
    results: set[str] = set()
    for match in _BANK_ACCOUNT_DIGITS.finditer(text):
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 80)
        window = text[start:end]
        if _BANK_CONTEXT_KEYWORDS.search(window):
            results.add(match.group())
    return list(results)


# ---------------------------------------------------------------------------
# Merge / deduplicate helpers
# ---------------------------------------------------------------------------

def merge_intelligence(
    existing: dict[str, list],
    new: ExtractedIntelligence,
) -> dict[str, list]:
    """
    Merge newly extracted intel into existing session intel.
    Returns a new dict with deduplicated lists.
    """
    merged: dict[str, list] = {}
    for key in (
        "phone_numbers", "bank_accounts", "upi_ids",
        "urls", "email_addresses", "ifsc_codes", "suspicious_keywords",
    ):
        existing_set = set(existing.get(key, []))
        new_set = set(getattr(new, key, []))
        merged[key] = list(existing_set | new_set)
    return merged
