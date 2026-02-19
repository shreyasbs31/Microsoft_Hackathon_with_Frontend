"""
Database models — SQLAlchemy ORM for session state persistence.
"""

import json
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Boolean,
    Text,
    BigInteger,
    Enum as SAEnum,
)
from sqlalchemy.orm import declarative_base, sessionmaker
import enum

from src.config import DATABASE_URL

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SessionStatus(str, enum.Enum):
    NEUTRAL = "NEUTRAL"
    HONEYPOT = "HONEYPOT"
    LEGIT = "LEGIT"


# ---------------------------------------------------------------------------
# SQLAlchemy setup
# ---------------------------------------------------------------------------

_connect_args: dict = {}
_engine_kwargs: dict = {}

if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
else:
    # PostgreSQL connection pooling for concurrent sessions
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, connect_args=_connect_args, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# Helper: store JSON lists in TEXT columns
# ---------------------------------------------------------------------------

class JSONColumn(Text):
    """Marker type — we serialise/deserialise manually."""
    pass


# ---------------------------------------------------------------------------
# Session model
# ---------------------------------------------------------------------------

class HoneypotSession(Base):
    __tablename__ = "sessions"

    # Primary key
    session_id = Column(String(255), primary_key=True, index=True)

    # Classification
    status = Column(
        SAEnum(SessionStatus),
        default=SessionStatus.NEUTRAL,
        nullable=False,
        index=True,
    )
    scam_type = Column(String(100), nullable=True)

    # Extracted intelligence  (stored as JSON-encoded lists)
    phone_numbers = Column(Text, default="[]")
    bank_accounts = Column(Text, default="[]")
    upi_ids = Column(Text, default="[]")
    urls = Column(Text, default="[]")
    email_addresses = Column(Text, default="[]")
    ifsc_codes = Column(Text, default="[]")
    case_ids = Column(Text, default="[]")
    policy_numbers = Column(Text, default="[]")
    order_numbers = Column(Text, default="[]")
    suspicious_keywords = Column(Text, default="[]")

    # Platform metadata
    channel = Column(String(50), nullable=True)
    language = Column(String(50), nullable=True)
    locale = Column(String(10), nullable=True)

    # Conversation tracking
    turn_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True, index=True)

    # Callback tracking
    final_callback_sent = Column(Boolean, default=False)
    final_callback_payload = Column(Text, nullable=True)  # JSON string

    # Confidence level from analyst
    confidence_level = Column(String(50), nullable=True)

    # Agent state
    agent_state_json = Column(Text, nullable=True)  # JSON string
    agent_notes = Column(Text, nullable=True)

    # Timestamps (epoch ms)
    first_message_timestamp = Column(BigInteger, nullable=True)
    last_message_timestamp = Column(BigInteger, nullable=True)

    # ------------------------------------------------------------------
    # Convenience helpers for JSON list columns
    # ------------------------------------------------------------------

    def _get_json_list(self, attr: str) -> list:
        raw = getattr(self, attr)
        if not raw:
            return []
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []

    def _set_json_list(self, attr: str, value: list):
        setattr(self, attr, json.dumps(value))

    def get_phone_numbers(self) -> list:
        return self._get_json_list("phone_numbers")

    def set_phone_numbers(self, v: list):
        self._set_json_list("phone_numbers", v)

    def get_bank_accounts(self) -> list:
        return self._get_json_list("bank_accounts")

    def set_bank_accounts(self, v: list):
        self._set_json_list("bank_accounts", v)

    def get_upi_ids(self) -> list:
        return self._get_json_list("upi_ids")

    def set_upi_ids(self, v: list):
        self._set_json_list("upi_ids", v)

    def get_urls(self) -> list:
        return self._get_json_list("urls")

    def set_urls(self, v: list):
        self._set_json_list("urls", v)

    def get_email_addresses(self) -> list:
        return self._get_json_list("email_addresses")

    def set_email_addresses(self, v: list):
        self._set_json_list("email_addresses", v)

    def get_ifsc_codes(self) -> list:
        return self._get_json_list("ifsc_codes")

    def set_ifsc_codes(self, v: list):
        self._set_json_list("ifsc_codes", v)

    def get_suspicious_keywords(self) -> list:
        return self._get_json_list("suspicious_keywords")

    def set_suspicious_keywords(self, v: list):
        self._set_json_list("suspicious_keywords", v)

    def get_case_ids(self) -> list:
        return self._get_json_list("case_ids")

    def set_case_ids(self, v: list):
        self._set_json_list("case_ids", v)

    def get_policy_numbers(self) -> list:
        return self._get_json_list("policy_numbers")

    def set_policy_numbers(self, v: list):
        self._set_json_list("policy_numbers", v)

    def get_order_numbers(self) -> list:
        return self._get_json_list("order_numbers")

    def set_order_numbers(self, v: list):
        self._set_json_list("order_numbers", v)

    def get_agent_state(self) -> dict:
        if not self.agent_state_json:
            return {}
        try:
            return json.loads(self.agent_state_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_agent_state(self, v: dict):
        self.agent_state_json = json.dumps(v)

    def get_callback_payload(self) -> dict | None:
        if not self.final_callback_payload:
            return None
        try:
            return json.loads(self.final_callback_payload)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_callback_payload(self, v: dict):
        self.final_callback_payload = json.dumps(v)

    def intel_counts(self) -> dict[str, int]:
        """Return a dict of intelligence field → count for priority logic."""
        return {
            "phone_numbers": len(self.get_phone_numbers()),
            "bank_accounts": len(self.get_bank_accounts()),
            "upi_ids": len(self.get_upi_ids()),
            "urls": len(self.get_urls()),
            "email_addresses": len(self.get_email_addresses()),
            "ifsc_codes": len(self.get_ifsc_codes()),
            "case_ids": len(self.get_case_ids()),
            "policy_numbers": len(self.get_policy_numbers()),
            "order_numbers": len(self.get_order_numbers()),
        }


# ---------------------------------------------------------------------------
# Create tables
# ---------------------------------------------------------------------------

def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
