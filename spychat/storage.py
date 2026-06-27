"""JSON-backed persistence for SpyChat profiles.

The previous version hard-coded the spy and their friends in source code and
lost all data on exit. This stores a :class:`~spychat.models.Profile` as JSON
and writes atomically (temp file + ``os.replace``) so an interrupted save can
never corrupt the existing profile.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Union

from .models import Profile

try:  # POSIX advisory locking; absent on Windows.
    import fcntl
except ImportError:  # pragma: no cover - platform-dependent
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path.home() / ".spychat" / "profile.json"

PathLike = Union[str, Path]


class ProfileStore:
    """Load and save a :class:`Profile` to a JSON file."""

    def __init__(self, path: PathLike = DEFAULT_PATH) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Hold an exclusive cross-process lock for a load-mutate-save cycle.

        Prevents lost updates when multiple workers (e.g. gunicorn) touch the
        same profile concurrently. Falls back to a no-op where ``fcntl`` is
        unavailable.
        """
        if fcntl is None:  # pragma: no cover
            yield
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with open(lock_path, "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def load(self) -> Profile:
        """Return the stored profile, or an empty one if none exists."""
        if not self.path.exists():
            return Profile()
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                return Profile.from_dict(json.load(fh))
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("Could not parse profile at %s: %s", self.path, exc)
            raise

    def save(self, profile: Profile) -> None:
        """Atomically persist ``profile`` to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(profile.to_dict(), fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
