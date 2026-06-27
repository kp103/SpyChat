"""WSGI entry point for production servers (gunicorn, waitress, uWSGI).

Example::

    gunicorn spychat.wsgi:app --bind 0.0.0.0:8000

Configuration via environment variables:

- ``SPYCHAT_DATA_DIR``    — directory for accounts + per-user profiles
                            (default ``~/.spychat``); mount a volume here.
- ``SPYCHAT_SECRET_KEY``  — Flask session signing key (set this in production).
- ``SPYCHAT_MAX_UPLOAD_MB`` — max upload size in MB (default 16).
- ``SPYCHAT_SECURE_COOKIES=1`` — mark session cookies Secure (behind HTTPS).
"""

from __future__ import annotations

import os

from .server import DEFAULT_DATA_DIR, create_app

app = create_app(os.environ.get("SPYCHAT_DATA_DIR", str(DEFAULT_DATA_DIR)))
