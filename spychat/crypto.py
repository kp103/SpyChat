"""Optional passphrase encryption for SpyChat messages.

Steganography hides that a message *exists*; it does not make it secret. This
module adds authenticated encryption so that, even if someone extracts the
hidden bytes, they cannot read them without the passphrase.

A random 16-byte salt is generated per message and a key is derived with
scrypt; the message is sealed with Fernet (AES-128-CBC + HMAC-SHA256). The
salt travels with the ciphertext so decryption needs only the passphrase.

Token format (all ASCII, safe to embed as text)::

    ENC1:<base64url salt>:<fernet token>
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

PREFIX = "ENC1:"
_SALT_LEN = 16
# scrypt cost parameters (interactive-use defaults).
_N, _R, _P = 2 ** 15, 8, 1


class CryptoError(Exception):
    """Raised when encryption or decryption fails."""


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=_N, r=_R, p=_P)
    raw = kdf.derive(passphrase.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def is_encrypted(token: str) -> bool:
    return token.startswith(PREFIX)


def encrypt(plaintext: str, passphrase: str, *, salt: bytes | None = None) -> str:
    """Return an ``ENC1:`` token sealing ``plaintext`` with ``passphrase``.

    ``salt`` is injectable for deterministic testing; production calls leave it
    ``None`` so a fresh random salt is generated.
    """
    if not passphrase:
        raise CryptoError("A passphrase is required to encrypt.")
    if salt is None:
        salt = _random_salt()
    key = _derive_key(passphrase, salt)
    token = Fernet(key).encrypt(plaintext.encode("utf-8"))
    b64_salt = base64.urlsafe_b64encode(salt).decode("ascii")
    return f"{PREFIX}{b64_salt}:{token.decode('ascii')}"


def decrypt(token: str, passphrase: str) -> str:
    """Reverse :func:`encrypt`. Raises :class:`CryptoError` on a bad passphrase."""
    if not is_encrypted(token):
        raise CryptoError("This message is not encrypted.")
    try:
        _, b64_salt, fernet_token = token.split(":", 2)
        salt = base64.urlsafe_b64decode(b64_salt)
    except (ValueError, base64.binascii.Error) as exc:
        raise CryptoError("Malformed encrypted message.") from exc

    key = _derive_key(passphrase, salt)
    try:
        plaintext = Fernet(key).decrypt(fernet_token.encode("ascii"))
    except InvalidToken as exc:
        raise CryptoError("Wrong passphrase or corrupted message.") from exc
    return plaintext.decode("utf-8")


def _random_salt() -> bytes:
    # os.urandom is fine; isolated here so tests can monkeypatch if needed.
    import os

    return os.urandom(_SALT_LEN)
