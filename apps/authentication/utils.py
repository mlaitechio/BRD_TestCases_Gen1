"""
apps/authentication/utils.py

Security utilities: JWT creation / verification, input sanitisation,
and DB-transaction logging. Ported from the Flask reference app.
"""

import html
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
from django.conf import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# DB-transaction logger
# ──────────────────────────────────────────────────────────────────────────────

db_transaction_logger = logging.getLogger("DBTransactions")
db_transaction_logger.setLevel(logging.INFO)
_db_handler = logging.FileHandler("db_transactions.log")
_db_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
db_transaction_logger.addHandler(_db_handler)


def log_db(operation: str, table: str, details: str = "", status: str = "SUCCESS", error=None) -> None:
    """Log a database operation to db_transactions.log."""
    message = f"{operation} - {table}"
    if details:
        message += f" - {details}"
    if status == "FAILED" and error:
        message += f" - ERROR: {error}"
    if status == "SUCCESS":
        db_transaction_logger.info(message)
    else:
        db_transaction_logger.error(message)


# ──────────────────────────────────────────────────────────────────────────────
# JWT utilities
# ──────────────────────────────────────────────────────────────────────────────

class Security:
    """JWT creation and verification helpers."""

    @staticmethod
    def create_jwt_token(user_data: Dict[str, Any]) -> str:
        """
        Create a signed HS256 JWT token from CyberArk user-info data.

        Expected keys (CyberArk Identity / OIDC userinfo response):
            Mail, sAMAccountName, Company, sub
        """
        now = datetime.utcnow()
        payload = {
            "sub": user_data.get("sub") or user_data.get("Mail", ""),
            "email": user_data.get("Mail", ""),
            "accountname": user_data.get("sAMAccountName", ""),
            "company": user_data.get("Company", ""),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(hours=8)).timestamp()),
            "jti": str(uuid.uuid4()),
            "iss": settings.AUTH_JWT_ISSUER,
            "aud": settings.AUTH_JWT_AUDIENCE,
        }
        print(f"Creating JWT token with payload: {payload}")  # Debugging line
        signing_key = _get_signing_key()
        return jwt.encode(payload, signing_key, algorithm=settings.AUTH_JWT_ALGORITHM)

    @staticmethod
    def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a JWT token and return its payload.

        Tries AUTH_JWT_SECRET first, then each key in AUTH_JWT_SECRETS (key rotation).
        Returns None on any failure.
        """
        candidate_keys = _get_candidate_keys()
        if not candidate_keys:
            logger.error("No JWT signing keys configured for verification")
            return None

        decode_kwargs = {
            "algorithms": [settings.AUTH_JWT_ALGORITHM],
            "issuer": settings.AUTH_JWT_ISSUER,
            "audience": settings.AUTH_JWT_AUDIENCE,
            "options": {"require_exp": True, "require_iat": True, "verify_aud": True},
        }

        for key in candidate_keys:
            try:
                return jwt.decode(token, key, **decode_kwargs)
            except jwt.ExpiredSignatureError:
                logger.warning("JWT token expired")
                return None
            except jwt.InvalidAudienceError as exc:
                logger.warning("JWT audience verification failed: %s", exc)
                return None
            except jwt.InvalidIssuerError as exc:
                logger.warning("JWT issuer verification failed: %s", exc)
                return None
            except jwt.InvalidSignatureError:
                # try next rotation key
                logger.debug("JWT signature mismatch — trying next key")
                continue
            except jwt.InvalidTokenError as exc:
                logger.warning("Invalid JWT token: %s", exc)
                return None

        logger.warning("JWT signature verification failed for all configured keys")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_signing_key() -> str:
    """Return the primary JWT signing key, falling back to an ephemeral one in dev."""
    key = getattr(settings, "AUTH_JWT_SECRET", None) or (
        getattr(settings, "AUTH_JWT_SECRETS", []) or [None]
    )[0]
    if not key:
        logger.warning("No JWT signing key configured — using ephemeral key (dev only)")
        key = secrets.token_hex(32)
    return key


def _get_candidate_keys() -> list:
    """Return all candidate JWT keys in priority order (primary first)."""
    keys = []
    primary = getattr(settings, "AUTH_JWT_SECRET", None)
    if primary:
        keys.append(primary)
    keys.extend(getattr(settings, "AUTH_JWT_SECRETS", []))
    return keys


# ──────────────────────────────────────────────────────────────────────────────
# Input sanitisation helpers
# ──────────────────────────────────────────────────────────────────────────────

def strip_tags(value: str) -> str:
    """Remove HTML tags to prevent stored XSS."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"<[^>]*?>", "", value)


def sanitize_text(value: Any, max_len: int = 200) -> str:
    """
    Sanitise a text input:
    - coerce to str, strip whitespace
    - remove HTML tags
    - remove control characters
    - HTML-encode remaining special characters
    - truncate to max_len
    """
    if value is None:
        return ""
    s = str(value).strip()
    s = strip_tags(s)
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    s = html.escape(s, quote=True)
    return s[:max_len]


# Whitelist patterns
_PATTERN_NAME = re.compile(r"^[A-Za-z0-9 .'\-]+$")
_PATTERN_GENERAL = re.compile(r"^[A-Za-z0-9 ,._\-/()&]+$")
_PATTERN_ROLE = re.compile(r"^[A-Za-z0-9_\-]+$")


def validate_field(value: str, pattern: re.Pattern, field_name: str):
    """
    Validate a field against a whitelist regex pattern.

    Returns:
        (cleaned_value, error_message)  — error_message is None when valid.
    """
    if not value:
        return value, None
    if not pattern.match(value):
        return (
            None,
            f"Invalid characters in {field_name}. "
            "Only letters, numbers, spaces, and basic punctuation are allowed.",
        )
    return value, None


def is_valid_email(email: Any) -> bool:
    """Basic email validation with reasonable length limits."""
    if not isinstance(email, str):
        return False
    e = email.strip()
    if not e or len(e) > 254:
        return False
    return bool(re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", e))
