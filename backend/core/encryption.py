"""
Symmetric encryption for connector credentials using Fernet (AES-128-CBC + HMAC-SHA256).

Usage:
    from backend.core.encryption import encrypt, decrypt, mask

    stored = encrypt('{"password": "s3cr3t"}')   # bytes → store in DB as text
    plain  = decrypt(stored)                       # back to original string
    shown  = mask("postgresql://user:s3cr3t@host") # "postgresql://user:***@host"

Key management:
    Set ENCRYPTION_KEY env var to a Fernet key (generate once with `python -m backend.core.encryption`).
    If missing, a deterministic key derived from SECRET_KEY is used — fine for dev, NOT for prod.
    In prod: generate a real key and inject via Kubernetes secret / Vault.
"""
import base64
import hashlib
import logging
import os
import re

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    logger.warning("cryptography package not installed — credentials stored as plaintext. Run: pip install cryptography")


def _get_key() -> bytes:
    """Return a 32-byte Fernet key. Reads ENCRYPTION_KEY env var or derives from SECRET_KEY."""
    raw = os.getenv("ENCRYPTION_KEY", "")
    if raw:
        try:
            return raw.encode() if isinstance(raw, str) else raw
        except Exception:
            pass

    # Derive from SECRET_KEY (dev fallback — deterministic so decryption works across restarts)
    secret = os.getenv("SECRET_KEY", "orchestrai-dev-secret-change-in-prod")
    derived = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(derived)  # Fernet needs URL-safe base64 of 32 bytes


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns base64 ciphertext string."""
    if not plaintext:
        return plaintext
    if not _CRYPTO_AVAILABLE:
        return plaintext  # graceful degradation

    try:
        f = Fernet(_get_key())
        return f.encrypt(plaintext.encode()).decode()
    except Exception as e:
        logger.error("encrypt failed: %s", e)
        return plaintext


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet ciphertext string. Returns original plaintext."""
    if not ciphertext:
        return ciphertext
    if not _CRYPTO_AVAILABLE:
        return ciphertext

    try:
        f = Fernet(_get_key())
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # Not encrypted (legacy plaintext in DB) — return as-is
        return ciphertext
    except Exception as e:
        logger.error("decrypt failed: %s", e)
        return ciphertext


def mask(value: str) -> str:
    """Redact passwords and secrets from a credential string for display.

    Examples:
        "postgresql://user:s3cr3t@host:5432/db"  →  "postgresql://user:***@host:5432/db"
        "Bearer ghp_abc123xyz"                    →  "Bearer ghp_***"
        "s3cr3t_value"                            →  "***"
    """
    if not value:
        return value

    # Mask URL passwords: scheme://user:PASSWORD@host
    value = re.sub(r"(://[^:@/]+:)[^@]+(@)", r"\1***\2", value)

    # Mask Bearer tokens: keep first 4 chars
    value = re.sub(r"(Bearer\s+\w{4})\w+", r"\1***", value, flags=re.IGNORECASE)

    return value


def mask_dict(creds: dict) -> dict:
    """Return a copy of a credentials dict with sensitive fields masked."""
    SENSITIVE = {"password", "secret", "token", "key", "api_key", "private_key",
                 "client_secret", "access_token", "refresh_token", "passwd"}
    out = {}
    for k, v in creds.items():
        if any(s in k.lower() for s in SENSITIVE) and v:
            shown = str(v)[:4] + "***" if len(str(v)) > 4 else "***"
            out[k] = shown
        else:
            out[k] = v
    return out


# ── CLI helper: generate a fresh key ─────────────────────────────────────────

if __name__ == "__main__":
    if not _CRYPTO_AVAILABLE:
        print("Install cryptography first: pip install cryptography")
    else:
        key = Fernet.generate_key().decode()
        print("Generated Fernet key — add to your .env:")
        print(f"ENCRYPTION_KEY={key}")
