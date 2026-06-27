"""WSGI entry point for production servers (gunicorn, waitress, uWSGI).

Example::

    gunicorn spychat.wsgi:app --bind 0.0.0.0:8000

The profile location can be set with the ``SPYCHAT_PROFILE`` environment
variable (defaults to ``~/.spychat/profile.json``); point it at a mounted
volume so data survives container restarts.
"""

from __future__ import annotations

import os

from .server import create_app
from .storage import DEFAULT_PATH

app = create_app(os.environ.get("SPYCHAT_PROFILE", str(DEFAULT_PATH)))
