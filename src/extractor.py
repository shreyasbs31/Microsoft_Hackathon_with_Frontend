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

# Bank account number: 9-18 digits, allow spaces/dashes in between.
# Use lookarounds so that surrounding punctuation doesn't stop matches
# and ensure we don't accidentally match longer digit runs.
_BANK_ACCOUNT_DIGITS = re.compile(r'(?<!\d)(?:\d[\s-]?){8,17}\d(?!\d)')
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
# Denial detection (explicit refusal phrases -> map to intel keys)
# ---------------------------------------------------------------------------

_DENIAL_PATTERNS: dict[str, re.Pattern] = {
    "email_addresses": re.compile(
        r"\b(no e-?mail|cannot e-?mail|we cannot email|email isn't allowed|email is not allowed|no email address|don't have an email|cannot provide an email)\b",
        re.IGNORECASE,
    ),
    "phone_numbers": re.compile(
        r"\b(no phone|can't call|cannot call|won't share number|can't share number|no phone number|don't have a phone)\b",
        re.IGNORECASE,
    ),
    "bank_accounts": re.compile(
        r"\b(no account|can't share account|cannot share account|won't share account|don't have account)\b",
        re.IGNORECASE,
    ),
    "upi_ids": re.compile(
        r"\b(no upi|can't share upi|cannot share upi|don't have upi|no vpa)\b",
        re.IGNORECASE,
    ),
    "ifsc_codes": re.compile(
        r"\b(no ifsc|can't share ifsc|cannot share ifsc|don't have ifsc)\b",
        re.IGNORECASE,
    ),
    "urls": re.compile(
        r"\b(no link|can't send link|cannot send link|no website|we cannot provide a link)\b",
        re.IGNORECASE,
    ),
}


def detect_denials(text: str) -> set[str]:
    """Return a set of intel keys the message explicitly refuses to provide.

    Conservative keyword/phrase matching to avoid false positives.
    """
    denied: set[str] = set()
    if not text:
        return denied
    for key, pattern in _DENIAL_PATTERNS.items():
        try:
            if pattern.search(text):
                denied.add(key)
        except Exception:
            # Be resilient; a failed pattern shouldn't break the pipeline
            continue
    return denied


def adjust_counts_for_denials(counts: dict[str, int], denied: set[str], sentinel: int = 999) -> dict[str, int]:
    """Return a copy of counts with denied fields set to a high sentinel so
    priority logic no longer treats them as URGENT (it checks for == 0).
    """
    out = counts.copy() if counts else {}
    for f in denied:
        if f in out:
            out[f] = sentinel
    return out


def normalise_text(text: str) -> str:
    """Strip excess whitespace and decode common URL-encoded characters."""
    import urllib.parse
    text = urllib.parse.unquote(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_intelligence_regex(text: str) -> ExtractedIntelligence:
    result = ExtractedIntelligence()

    # 1. EMAIL ADDRESSES FIRST
    # We extract these first so we can exclude them from UPI matches
    email_matches = _EMAIL_PATTERN.findall(text)
    result.email_addresses = sorted(list(set(email_matches)))
    email_set_lower = {e.lower() for e in result.email_addresses}

    # 2. UPI IDs (with Email exclusion)
    upi_matches: list[str] = []
    
    # Check both Known and General patterns
    for pattern in [_UPI_KNOWN, _UPI_GENERAL]:
        for m in pattern.finditer(text):
            candidate = m.group()
            cl = candidate.lower()
            
            # CRITICAL FIX: If this match was already caught as an email, skip it
            if cl in email_set_lower:
                continue
                
            # Context check: if "email" is mentioned nearby, skip it
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            window = text[start:end].lower()
            if "email" in window or "e-mail" in window:
                # Add to emails if not already there, then skip UPI
                if cl not in email_set_lower:
                    result.email_addresses.append(candidate)
                    email_set_lower.add(cl)
                continue
                
            upi_matches.append(candidate)

    # Clean up UPIs
    result.upi_ids = list(dict.fromkeys(upi_matches))
    result.email_addresses = sorted(list(set(result.email_addresses)))

    # ... [Rest of your extraction logic for Phones, URLs, IFSC, etc. remains the same] ...
    
    # 3. Phone numbers
    phones: set[str] = set()
    for m in _PHONE_INDIA.finditer(text):
        normalised = _normalise_phone(m.group())
        digit_count = len(re.sub(r'\D', '', normalised))
        if 10 <= digit_count <= 12: phones.add(normalised)
    for m in _PHONE_INTL.finditer(text):
        normalised = _normalise_phone(m.group())
        digit_count = len(re.sub(r'\D', '', normalised))
        if 8 <= digit_count <= 15: phones.add(normalised)
    result.phone_numbers = list(phones)

    # 4. URLs
    raw_urls = _URL_PATTERN.findall(text)
    result.urls = list(set(_deobfuscate_url(u) for u in raw_urls))

    # 5. IFSC codes
    result.ifsc_codes = list(set(_IFSC_PATTERN.findall(text)))

    # 6. Bank accounts
    result.bank_accounts = _extract_bank_accounts(text)

    # Cross-deconflict
    phone_digit_set = {re.sub(r'\D', '', p) for p in result.phone_numbers}
    upi_locals = {u.split('@')[0] for u in result.upi_ids if '@' in u}
    result.bank_accounts = [a for a in result.bank_accounts if re.sub(r'\D', '', a) not in phone_digit_set]
    result.phone_numbers = [p for p in result.phone_numbers if re.sub(r'\D', '', p) not in upi_locals]

    # 7. Keywords
    text_lower = text.lower()
    result.suspicious_keywords = [kw for kw in _SCAM_KEYWORDS if kw in text_lower]

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
    Modified to be less aggressive. 
    Only flags sequences of the exact same digit.
    """
    if len(set(digits)) == 1:
        return True  # e.g., "999999999"
    
    # We remove the ascending/descending check because 
    # scammers often use '123456789' as a placeholder 
    # that we actually want to capture in our logs.
    return False

def _extract_bank_accounts(text: str) -> list[str]:
    results: set[str] = set()
    for match in _BANK_ACCOUNT_DIGITS.finditer(text):
        raw = match.group()
        digits = re.sub(r'\D', '', raw)
        
        # Ensure length is valid
        if not (9 <= len(digits) <= 18):
            continue
            
        # Check against the relaxed boilerplate rule
        if _is_boilerplate_number(digits):
            continue
            
        # Increased window slightly to catch context in messy chats
        start = max(0, match.start() - 150)
        end = min(len(text), match.end() + 150)
        window = text[start:end]
        
        if _BANK_CONTEXT_KEYWORDS.search(window):
            results.add(digits)
            
    return sorted(results)


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
