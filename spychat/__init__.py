"""SpyChat — hide secret messages inside images, spy-style."""

from .app import SpyChatApp, ValidationError
from .crypto import CryptoError, decrypt, encrypt
from .models import ChatMessage, Profile, Spy
from .steganography import (
    MessageTooLargeError,
    NoHiddenMessageError,
    SteganographyError,
    decode,
    encode,
)

__version__ = "1.0.0"

__all__ = [
    "SpyChatApp",
    "ValidationError",
    "ChatMessage",
    "Profile",
    "Spy",
    "encode",
    "decode",
    "encrypt",
    "decrypt",
    "CryptoError",
    "SteganographyError",
    "MessageTooLargeError",
    "NoHiddenMessageError",
    "__version__",
]
