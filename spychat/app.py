"""Core SpyChat business logic, decoupled from console I/O.

Keeping the rules here (separate from the CLI prompts in :mod:`spychat.cli`)
makes them unit-testable and keeps validation in one place.
"""

from __future__ import annotations

from pathlib import Path

from .crypto import CryptoError, decrypt, encrypt, is_encrypted
from .models import ChatMessage, Profile, Spy
from .steganography import PathLike, decode, encode

MIN_SPY_AGE = 12
MAX_SPY_AGE = 50
MIN_FRIEND_AGE = 12
# Messages longer than this (in words) get the friend "terminated" — a rule
# carried over from the original game, now off by default and configurable.
MAX_FRIEND_WORDS = 100

SPECIAL_MESSAGES = {"hi all"}


class ValidationError(Exception):
    """Raised when user-supplied data fails a SpyChat rule."""


class SpyChatApp:
    """Stateful façade over a :class:`Profile`."""

    def __init__(self, profile: Profile | None = None) -> None:
        self.profile = profile or Profile()

    # -- spy / authentication ------------------------------------------------

    @staticmethod
    def validate_spy(name: str, salutation: str, age: int, rating: float) -> None:
        if not name or not name.strip():
            raise ValidationError("A spy must have a name.")
        if not salutation or not salutation.strip():
            raise ValidationError("A spy must have a salutation (Mr. or Ms.).")
        if not (MIN_SPY_AGE < age < MAX_SPY_AGE):
            raise ValidationError(
                f"A spy's age must be between {MIN_SPY_AGE + 1} and {MAX_SPY_AGE - 1}."
            )
        if rating < 0:
            raise ValidationError("Rating cannot be negative.")

    def register_spy(self, name: str, salutation: str, age: int, rating: float) -> Spy:
        self.validate_spy(name, salutation, age, rating)
        spy = Spy(name=name.strip(), salutation=salutation.strip(), age=age, rating=rating)
        self.profile.spy = spy
        return spy

    @property
    def spy(self) -> Spy | None:
        return self.profile.spy

    @property
    def friends(self) -> list[Spy]:
        return self.profile.friends

    # -- friends -------------------------------------------------------------

    def add_friend(self, name: str, salutation: str, age: int, rating: float) -> Spy:
        if not name or not name.strip():
            raise ValidationError("A friend must have a name.")
        if not salutation or not salutation.strip():
            raise ValidationError("A friend must have a salutation.")
        if age <= MIN_FRIEND_AGE:
            raise ValidationError(f"A friend must be older than {MIN_FRIEND_AGE}.")
        if self.spy and rating < self.spy.rating:
            raise ValidationError(
                "You can only befriend spies rated at least as high as you "
                f"({self.spy.rating:.2f})."
            )
        friend = Spy(name=name.strip(), salutation=salutation.strip(), age=age, rating=rating)
        self.profile.friends.append(friend)
        return friend

    def remove_friend(self, index: int) -> Spy:
        self._check_friend_index(index)
        return self.profile.friends.pop(index)

    def _check_friend_index(self, index: int) -> None:
        if not 0 <= index < len(self.profile.friends):
            raise ValidationError("No friend at that position.")

    # -- status messages -----------------------------------------------------

    def add_status_message(self, message: str) -> str:
        if not message or not message.strip():
            raise ValidationError("Status message cannot be empty.")
        message = message.strip()
        if message not in self.profile.status_messages:
            self.profile.status_messages.append(message)
        if self.profile.spy:
            self.profile.spy.current_status_message = message
        return message

    def remove_status_message(self, index: int) -> str:
        if not 0 <= index < len(self.profile.status_messages):
            raise ValidationError("No status message at that position.")
        return self.profile.status_messages.pop(index)

    # -- messaging -----------------------------------------------------------

    def send_message(
        self,
        friend_index: int,
        carrier_image: PathLike,
        output_image: PathLike,
        text: str,
        passphrase: str = "",
    ) -> Path:
        """Encode ``text`` into ``carrier_image`` and log it against a friend.

        If ``passphrase`` is given, the message is encrypted before hiding, so
        it cannot be read from the image without the same passphrase.
        """
        self._check_friend_index(friend_index)
        if not text or not text.strip():
            raise ValidationError("Cannot send an empty message.")
        inner = "#" + text  # "#" marks direction (sent by me)
        payload = encrypt(inner, passphrase) if passphrase else inner
        out = encode(carrier_image, output_image, payload)
        self.profile.friends[friend_index].chats.append(
            ChatMessage(message=text, is_sent_by_me=True)
        )
        return out

    def read_message(
        self, sender_index: int, image_path: PathLike, passphrase: str = ""
    ) -> dict:
        """Decode a message from ``image_path`` and log it against a sender.

        Returns a dict describing the outcome, including whether the message
        was special and whether the sender was "terminated" for talking too
        much (the original game's rule, preserved). Raises
        :class:`~spychat.crypto.CryptoError` if the message is encrypted and
        the passphrase is missing or wrong.
        """
        self._check_friend_index(sender_index)
        raw = decode(image_path)

        if is_encrypted(raw):
            if not passphrase:
                raise CryptoError("This message is encrypted; a passphrase is required.")
            raw = decrypt(raw, passphrase)

        sent_by_me = raw.startswith("#")
        text = raw[1:] if sent_by_me else raw

        self.profile.friends[sender_index].chats.append(
            ChatMessage(message=text, is_sent_by_me=sent_by_me)
        )

        is_special = text.strip().lower() in SPECIAL_MESSAGES
        terminated = len(text.split()) > MAX_FRIEND_WORDS
        sender_name = self.profile.friends[sender_index].name
        if terminated:
            del self.profile.friends[sender_index]

        return {
            "text": text,
            "is_special": is_special,
            "terminated": terminated,
            "sender_name": sender_name,
            "sent_by_me": sent_by_me,
        }
