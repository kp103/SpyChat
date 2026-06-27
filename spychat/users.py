"""Multi-user accounts and per-user profile storage.

Each account has a salted password hash (via Werkzeug, which ships with Flask)
stored in ``<data_dir>/users.json``; each user's SpyChat data lives in its own
``<data_dir>/profiles/<username>.json`` so accounts never share or clobber one
another. Writes to ``users.json`` are atomic.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Union

from werkzeug.security import check_password_hash, generate_password_hash

from .storage import ProfileStore

PathLike = Union[str, Path]

USERNAME_RE = re.compile(r"^[a-z0-9_-]{3,32}$")
MIN_PASSWORD_LEN = 8


class UserError(Exception):
    """Raised for invalid registration or login input."""


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


class UserStore:
    """Account registry plus a :class:`ProfileStore` factory per user."""

    def __init__(self, data_dir: PathLike) -> None:
        self.data_dir = Path(data_dir)
        self.users_path = self.data_dir / "users.json"
        self.profiles_dir = self.data_dir / "profiles"

    # -- persistence ---------------------------------------------------------

    def _load(self) -> dict:
        if not self.users_path.exists():
            return {}
        try:
            with self.users_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, ValueError):
            return {}

    def _save(self, users: dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.data_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(users, fh, indent=2)
            os.replace(tmp, self.users_path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # -- accounts ------------------------------------------------------------

    def exists(self, username: str) -> bool:
        return normalize_username(username) in self._load()

    def register(self, username: str, password: str) -> str:
        """Create an account; returns the normalized username."""
        username = normalize_username(username)
        if not USERNAME_RE.match(username):
            raise UserError(
                "Username must be 3-32 characters: lowercase letters, digits, "
                "'_' or '-'."
            )
        if len(password or "") < MIN_PASSWORD_LEN:
            raise UserError(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
        users = self._load()
        if username in users:
            raise UserError("That username is already taken.")
        users[username] = {"password_hash": generate_password_hash(password)}
        self._save(users)
        return username

    def verify(self, username: str, password: str) -> bool:
        username = normalize_username(username)
        user = self._load().get(username)
        if not user:
            # Run a dummy check to reduce username-enumeration timing signal.
            check_password_hash(
                generate_password_hash("x"), password or ""
            )
            return False
        return check_password_hash(user["password_hash"], password or "")

    # -- per-user data -------------------------------------------------------

    def profile_store(self, username: str) -> ProfileStore:
        username = normalize_username(username)
        if not USERNAME_RE.match(username):
            raise UserError("Invalid username.")
        return ProfileStore(self.profiles_dir / f"{username}.json")
