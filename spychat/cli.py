"""Interactive console front-end for SpyChat."""

from __future__ import annotations

import argparse
import logging
import sys
from getpass import getpass
from typing import Callable

from .app import SpyChatApp, ValidationError
from .crypto import CryptoError, decrypt, encrypt, is_encrypted
from .models import Profile
from .steganography import SteganographyError
from .storage import DEFAULT_PATH, ProfileStore

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_IMAGE = "secret_message.png"


def _prompt(text: str) -> str:
    try:
        return input(text).strip()
    except EOFError:
        return ""


def _prompt_int(text: str) -> int | None:
    raw = _prompt(text)
    try:
        return int(raw)
    except ValueError:
        print("Please enter a whole number.")
        return None


def _prompt_float(text: str) -> float | None:
    raw = _prompt(text)
    try:
        return float(raw)
    except ValueError:
        print("Please enter a number.")
        return None


class SpyChatCLI:
    """Drives the menu loop and persistence around :class:`SpyChatApp`."""

    def __init__(self, store: ProfileStore) -> None:
        self.store = store
        self.app = SpyChatApp(self._load_profile())

    def _load_profile(self) -> Profile:
        try:
            return self.store.load()
        except Exception:  # noqa: BLE001 - corrupted file shouldn't crash startup
            print("Could not read your saved profile; starting fresh.")
            return Profile()

    def _save(self) -> None:
        try:
            self.store.save(self.app.profile)
        except OSError as exc:
            print(f"Warning: could not save your profile: {exc}")

    # -- onboarding ----------------------------------------------------------

    def _ensure_spy(self) -> bool:
        spy = self.app.spy
        if spy is not None:
            keep = _prompt(f"Continue as {spy.display_name} (Y/N)? ")
            if keep[:1].upper() == "Y":
                return True

        print("\nSpyChat welcomes you. Let's set up your spy identity.")
        name = _prompt("Your spy name: ")
        salutation = _prompt("Mr. or Ms.?: ")
        age = _prompt_int("Your age: ")
        if age is None:
            return False
        rating = _prompt_float("Your spy rating: ")
        if rating is None:
            return False
        try:
            spy = self.app.register_spy(name, salutation, age, rating)
        except ValidationError as exc:
            print(f"Sorry: {exc}")
            return False
        print(f"Authentication complete. Welcome {spy.display_name}! Proud to have you onboard.")
        self._save()
        return True

    # -- menu actions --------------------------------------------------------

    def _add_status(self) -> None:
        spy = self.app.spy
        if spy and spy.current_status_message:
            print(f"Your current status: {spy.current_status_message}")
        msg = _prompt("New status message: ")
        try:
            self.app.add_status_message(msg)
            print("Status updated.")
        except ValidationError as exc:
            print(f"Sorry: {exc}")

    def _add_friend(self) -> None:
        name = _prompt("Your friend's name: ")
        salutation = _prompt("Friend's Mr. or Ms.?: ")
        age = _prompt_int("Age: ")
        if age is None:
            return
        rating = _prompt_float("Spy rating: ")
        if rating is None:
            return
        try:
            self.app.add_friend(name, salutation, age, rating)
            print(f"New friend added! You now have {len(self.app.friends)} friend(s).")
        except ValidationError as exc:
            print(f"Sorry: {exc}")

    def _list_friends(self) -> bool:
        if not self.app.friends:
            print("You have no friends yet. Add one first.")
            return False
        for i, f in enumerate(self.app.friends, 1):
            print(
                f"{i}. {f.display_name} aged {f.age} with rating {f.rating:.2f} is online"
            )
        return True

    def _select_friend(self) -> int | None:
        if not self._list_friends():
            return None
        choice = _prompt_int("Choose a friend by number: ")
        if choice is None:
            return None
        index = choice - 1
        if not 0 <= index < len(self.app.friends):
            print("That friend doesn't exist.")
            return None
        return index

    def _send_message(self) -> None:
        index = self._select_friend()
        if index is None:
            return
        carrier = _prompt("Image to hide the message in: ")
        output = _prompt(f"Output image [{DEFAULT_OUTPUT_IMAGE}]: ") or DEFAULT_OUTPUT_IMAGE
        text = _prompt("Your secret message: ")
        passphrase = getpass("Encryption passphrase (blank = none): ")
        try:
            out = self.app.send_message(index, carrier, output, text, passphrase)
            tag = " (encrypted)" if passphrase else ""
            print(f"Your secret is safe, spy!{tag} Hidden in: {out}")
        except (ValidationError, SteganographyError, CryptoError) as exc:
            print(f"Mission aborted: {exc}")
        except FileNotFoundError:
            print(f"Mission aborted: image '{carrier}' not found.")

    def _read_message(self) -> None:
        index = self._select_friend()
        if index is None:
            return
        image = _prompt("Image file containing the secret: ")
        passphrase = getpass("Passphrase (blank if not encrypted): ")
        try:
            result = self.app.read_message(index, image, passphrase)
        except (ValidationError, SteganographyError, CryptoError) as exc:
            print(f"No message: {exc}")
            return
        except FileNotFoundError:
            print(f"No message: image '{image}' not found.")
            return
        print(f"Decoded message: {result['text']}")
        if result["is_special"]:
            print(f"SPY ALERT! SPECIAL MESSAGE GENERATED: {result['text']}")
        if result["terminated"]:
            print(
                f"Spy friend {result['sender_name']} spoke too much. "
                "Their profile has been terminated!"
            )

    def _read_chats(self) -> None:
        index = self._select_friend()
        if index is None:
            return
        friend = self.app.friends[index]
        if not friend.chats:
            print("No previous chats exist.")
            return
        for chat in friend.chats:
            stamp = chat.time.strftime("%d %B %Y %H:%M")
            who = "You" if chat.is_sent_by_me else friend.name
            print(f"[{stamp}] {who}: {chat.message}")

    def _remove_friend(self) -> None:
        index = self._select_friend()
        if index is None:
            return
        removed = self.app.remove_friend(index)
        print(f"Removed {removed.display_name}.")

    def _remove_status(self) -> None:
        msgs = self.app.profile.status_messages
        if not msgs:
            print("No status messages found.")
            return
        for i, m in enumerate(msgs, 1):
            print(f"{i}. {m}")
        choice = _prompt_int("Select a status to delete: ")
        if choice is None:
            return
        try:
            self.app.remove_status_message(choice - 1)
            print("Status removed.")
        except ValidationError as exc:
            print(f"Sorry: {exc}")

    # -- main loop -----------------------------------------------------------

    MENU = (
        "\nYour Spy tools:\n"
        " 1. Add a status update\n"
        " 2. Add a friend\n"
        " 3. Send a secret message\n"
        " 4. Read a secret message\n"
        " 5. Read chats from a friend\n"
        " 6. List all friends\n"
        " 7. Read a friend's status\n"
        " 8. Remove a friend\n"
        " 9. Remove an old status\n"
        " 0. Close application\n"
    )

    def _read_friend_status(self) -> None:
        index = self._select_friend()
        if index is None:
            return
        friend = self.app.friends[index]
        print(f"{friend.display_name}'s status: {friend.current_status_message}")

    def run(self) -> int:
        if not self._ensure_spy():
            print("Goodbye, spy.")
            return 0

        actions: dict[int, Callable[[], None]] = {
            1: self._add_status,
            2: self._add_friend,
            3: self._send_message,
            4: self._read_message,
            5: self._read_chats,
            6: lambda: self._list_friends() and None,
            7: self._read_friend_status,
            8: self._remove_friend,
            9: self._remove_status,
        }

        while True:
            choice = _prompt_int(self.MENU)
            if choice is None:
                continue
            if choice == 0:
                print("Pleasure to assist a world-class spy. Goodbye!")
                self._save()
                return 0
            action = actions.get(choice)
            if action is None:
                print("Invalid choice. Be smarter, spy.")
                continue
            action()
            self._save()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spychat",
        description="Hide secret messages inside images, spy-style.",
    )
    parser.add_argument(
        "--profile",
        default=str(DEFAULT_PATH),
        help=f"Path to the profile JSON file (default: {DEFAULT_PATH}).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging."
    )
    sub = parser.add_subparsers(dest="command")

    enc = sub.add_parser("encode", help="Hide a message in an image and exit.")
    enc.add_argument("input_image")
    enc.add_argument("output_image")
    enc.add_argument("message")
    enc.add_argument("-p", "--passphrase", help="Encrypt the message before hiding it.")

    dec = sub.add_parser("decode", help="Reveal a message from an image and exit.")
    dec.add_argument("image")
    dec.add_argument("-p", "--passphrase", help="Passphrase to decrypt the message.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "encode":
        from .steganography import encode

        message = args.message
        if args.passphrase:
            message = encrypt(message, args.passphrase)
        try:
            out = encode(args.input_image, args.output_image, message)
        except (SteganographyError, CryptoError, FileNotFoundError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Message hidden in {out}")
        return 0

    if args.command == "decode":
        from .steganography import decode

        try:
            raw = decode(args.image)
            if is_encrypted(raw):
                if not args.passphrase:
                    print(
                        "Error: this message is encrypted; pass --passphrase.",
                        file=sys.stderr,
                    )
                    return 1
                raw = decrypt(raw, args.passphrase)
            print(raw)
        except (SteganographyError, CryptoError, FileNotFoundError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return 0

    try:
        return SpyChatCLI(ProfileStore(args.profile)).run()
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye, spy.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
