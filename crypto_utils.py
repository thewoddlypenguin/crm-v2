"""
Token encryption utilities for Gmail OAuth tokens at rest.

Uses Fernet (symmetric authenticated encryption) from the cryptography package.
The encryption key is loaded from the TOKEN_ENCRYPTION_KEY environment variable.

Generate a key:  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import os
import base64

from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    """Load the Fernet key from TOKEN_ENCRYPTION_KEY env var.

    Raises RuntimeError if the key is missing or invalid.
    """
    raw = os.environ.get("TOKEN_ENCRYPTION_KEY") or os.environ.get("GMAIL_TOKEN_ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY environment variable is not set. "
            "Generate one with: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    # Allow both raw bytes and base64-encoded strings
    try:
        key = raw.encode("utf-8")
        # Validate key length (Fernet keys are 32 bytes base64-encoded = 44 chars)
        decoded = base64.urlsafe_b64decode(key + b"==")  # padding tolerant
        if len(decoded) != 32:
            raise ValueError(f"Invalid key length: {len(decoded)} bytes (expected 32)")
        return Fernet(key)
    except Exception as exc:
        raise RuntimeError(f"Invalid TOKEN_ENCRYPTION_KEY: {exc}")


def encrypt_token(plaintext: str) -> str:
    """Encrypt a plaintext token and return a base64-encoded ciphertext string."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a ciphertext token back to plaintext.

    If the value does not look like a Fernet token (not encrypted), returns
    it as-is for backward compatibility with existing plaintext tokens.
    """
    if not ciphertext:
        return ""

    # Fernet tokens are base64-encoded and always start with "gAAAAA"
    if not ciphertext.startswith("gAAAAA"):
        return ciphertext  # legacy plaintext — return unchanged

    try:
        f = _get_fernet()
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Not a valid Fernet token — treat as plaintext (legacy)
        return ciphertext