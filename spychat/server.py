"""Flask web server exposing SpyChat through a REST API + single-page UI.

Reuses the same engine as the CLI (:mod:`spychat.app`,
:mod:`spychat.steganography`) so the web and terminal front-ends never diverge.

Multi-user: each account authenticates with a session cookie and gets its own
isolated profile (see :mod:`spychat.users`). Hardening: upload size limits,
Pillow decompression-bomb guards, a CSRF header check on mutating requests, and
cross-process locking around per-user writes.
"""

from __future__ import annotations

import io
import logging
import os
import secrets
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, g, jsonify, request, send_file, session
from PIL import Image, UnidentifiedImageError

from .app import MAX_FRIEND_WORDS, SPECIAL_MESSAGES, SpyChatApp, ValidationError
from .crypto import CryptoError, decrypt, encrypt, is_encrypted
from .models import ChatMessage
from .steganography import (
    _HEADER_LEN,
    NoHiddenMessageError,
    SteganographyError,
    _capacity_bytes,
    embed,
    extract,
)
from .users import UserError, UserStore

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
DEFAULT_DATA_DIR = Path.home() / ".spychat"

# Mutating requests must carry this header; browsers won't send custom headers
# on cross-origin form posts without a CORS preflight, so this blocks CSRF.
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "SpyChat"


def _spy_to_json(spy) -> dict:
    return {
        "name": spy.name,
        "salutation": spy.salutation,
        "display_name": spy.display_name,
        "age": spy.age,
        "rating": spy.rating,
        "current_status_message": spy.current_status_message,
        "chats": [
            {"message": c.message, "is_sent_by_me": c.is_sent_by_me, "time": c.time.isoformat()}
            for c in spy.chats
        ],
    }


def _profile_to_json(app: SpyChatApp) -> dict:
    return {
        "spy": _spy_to_json(app.spy) if app.spy else None,
        "friends": [_spy_to_json(f) for f in app.friends],
        "status_messages": app.profile.status_messages,
    }


def create_app(data_dir: str | Path = DEFAULT_DATA_DIR) -> Flask:
    _configure_logging()
    flask_app = Flask(
        __name__,
        static_folder=str(_HERE / "web" / "static"),
        template_folder=str(_HERE / "web" / "templates"),
        static_url_path="/static",
    )

    max_mb = float(os.environ.get("SPYCHAT_MAX_UPLOAD_MB", "16"))
    flask_app.config.update(
        SECRET_KEY=_secret_key(),
        MAX_CONTENT_LENGTH=int(max_mb * 1024 * 1024),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SPYCHAT_SECURE_COOKIES", "") == "1",
        JSON_SORT_KEYS=False,
    )

    users = UserStore(data_dir)

    # -- security middleware -------------------------------------------------

    @flask_app.before_request
    def _csrf_guard():
        mutating = request.method in ("POST", "PUT", "PATCH", "DELETE")
        is_api = request.path.startswith("/api/")
        if mutating and is_api and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
            return jsonify({"error": "Missing or invalid CSRF header."}), 403
        return None

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            username = session.get("username")
            if not username:
                return jsonify({"error": "Authentication required."}), 401
            g.store = users.profile_store(username)
            g.username = username
            return view(*args, **kwargs)

        return wrapped

    # -- pages / health ------------------------------------------------------

    @flask_app.get("/")
    def index():
        return send_file(_HERE / "web" / "templates" / "index.html")

    @flask_app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    # -- auth ----------------------------------------------------------------

    @flask_app.get("/api/me")
    def whoami():
        return jsonify({"username": session.get("username")})

    @flask_app.post("/api/register")
    def register():
        data = request.get_json(force=True, silent=True) or {}
        try:
            username = users.register(data.get("username", ""), data.get("password", ""))
        except UserError as exc:
            return _err(exc)
        session.clear()
        session["username"] = username
        return jsonify({"username": username})

    @flask_app.post("/api/login")
    def login():
        data = request.get_json(force=True, silent=True) or {}
        username = data.get("username", "")
        if not users.verify(username, data.get("password", "")):
            return jsonify({"error": "Invalid username or password."}), 401
        session.clear()
        session["username"] = (username or "").strip().lower()
        return jsonify({"username": session["username"]})

    @flask_app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"ok": True})

    # -- profile -------------------------------------------------------------

    @flask_app.get("/api/profile")
    @login_required
    def get_profile():
        return jsonify(_profile_to_json(SpyChatApp(g.store.load())))

    @flask_app.post("/api/spy")
    @login_required
    def register_spy():
        data = request.get_json(force=True, silent=True) or {}
        with g.store.lock():
            app = SpyChatApp(g.store.load())
            try:
                app.register_spy(
                    data.get("name", ""), data.get("salutation", ""),
                    _as_int(data.get("age")), _as_float(data.get("rating")),
                )
            except (ValidationError, ValueError) as exc:
                return _err(exc)
            g.store.save(app.profile)
        return jsonify(_profile_to_json(app))

    # -- friends -------------------------------------------------------------

    @flask_app.post("/api/friends")
    @login_required
    def add_friend():
        data = request.get_json(force=True, silent=True) or {}
        with g.store.lock():
            app = SpyChatApp(g.store.load())
            try:
                app.add_friend(
                    data.get("name", ""), data.get("salutation", ""),
                    _as_int(data.get("age")), _as_float(data.get("rating")),
                )
            except (ValidationError, ValueError) as exc:
                return _err(exc)
            g.store.save(app.profile)
        return jsonify(_profile_to_json(app))

    @flask_app.delete("/api/friends/<int:index>")
    @login_required
    def remove_friend(index: int):
        with g.store.lock():
            app = SpyChatApp(g.store.load())
            try:
                app.remove_friend(index)
            except ValidationError as exc:
                return _err(exc)
            g.store.save(app.profile)
        return jsonify(_profile_to_json(app))

    # -- status --------------------------------------------------------------

    @flask_app.post("/api/status")
    @login_required
    def add_status():
        data = request.get_json(force=True, silent=True) or {}
        with g.store.lock():
            app = SpyChatApp(g.store.load())
            try:
                app.add_status_message(data.get("message", ""))
            except ValidationError as exc:
                return _err(exc)
            g.store.save(app.profile)
        return jsonify(_profile_to_json(app))

    # -- steganography -------------------------------------------------------

    @flask_app.post("/api/capacity")
    @login_required
    def capacity():
        file = request.files.get("image")
        if not file:
            return jsonify({"error": "No image uploaded."}), 400
        try:
            with _open_image(file.read()) as img:
                w, h = img.size
        except _ImageError as exc:
            return _err(exc)
        return jsonify({"capacity_bytes": max(0, _capacity_bytes(w, h) - _HEADER_LEN),
                        "width": w, "height": h})

    @flask_app.post("/api/encode")
    @login_required
    def api_encode():
        file = request.files.get("image")
        text = request.form.get("message", "")
        passphrase = request.form.get("passphrase", "")
        friend_index = request.form.get("friend_index", "")
        if not file:
            return jsonify({"error": "No image uploaded."}), 400
        if not text.strip():
            return jsonify({"error": "Message cannot be empty."}), 400

        inner = "#" + text  # "#" marks direction (sent by me)
        payload = encrypt(inner, passphrase) if passphrase else inner
        try:
            with _open_image(file.read()) as img:
                result_img = embed(img, payload)
        except (SteganographyError, CryptoError, _ImageError) as exc:
            return _err(exc)

        idx = _as_int(friend_index) if friend_index not in ("", None) else None
        if idx is not None:
            with g.store.lock():
                app = SpyChatApp(g.store.load())
                if 0 <= idx < len(app.friends):
                    app.friends[idx].chats.append(ChatMessage(message=text, is_sent_by_me=True))
                    g.store.save(app.profile)

        out_buf = io.BytesIO()
        result_img.save(out_buf, format="PNG")
        out_buf.seek(0)
        return send_file(out_buf, mimetype="image/png", as_attachment=True,
                         download_name="secret_message.png")

    @flask_app.post("/api/decode")
    @login_required
    def api_decode():
        file = request.files.get("image")
        passphrase = request.form.get("passphrase", "")
        friend_index = request.form.get("friend_index", "")
        if not file:
            return jsonify({"error": "No image uploaded."}), 400
        try:
            with _open_image(file.read()) as img:
                raw_text = extract(img)
            result = _interpret(raw_text, passphrase)
        except (NoHiddenMessageError, CryptoError, _ImageError) as exc:
            return _err(exc)

        idx = _as_int(friend_index) if friend_index not in ("", None) else None
        if idx is not None:
            with g.store.lock():
                app = SpyChatApp(g.store.load())
                if 0 <= idx < len(app.friends):
                    app.friends[idx].chats.append(
                        ChatMessage(message=result["text"], is_sent_by_me=result["sent_by_me"])
                    )
                    if result["terminated"]:
                        del app.friends[idx]
                    g.store.save(app.profile)
        return jsonify(result)

    # -- error handlers ------------------------------------------------------

    @flask_app.errorhandler(413)
    def too_large(_exc):
        mb = flask_app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)
        return jsonify({"error": f"Upload too large (limit {mb:.0f} MB)."}), 413

    return flask_app


# -- helpers ----------------------------------------------------------------


class _ImageError(Exception):
    """Internal: a user-facing problem opening an uploaded image."""


def _open_image(data: bytes) -> Image.Image:
    """Open uploaded bytes as an image, guarding against bombs / bad files."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()  # force decode now so bombs are caught here, not later
        return img
    except Image.DecompressionBombError as exc:
        raise _ImageError("Image is too large to process safely.") from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise _ImageError("Not a valid image.") from exc


def _interpret(raw_text: str, passphrase: str) -> dict:
    was_encrypted = is_encrypted(raw_text)
    if was_encrypted:
        if not passphrase:
            raise CryptoError("This message is encrypted; a passphrase is required.")
        raw_text = decrypt(raw_text, passphrase)

    sent_by_me = raw_text.startswith("#")
    text = raw_text[1:] if sent_by_me else raw_text
    return {
        "text": text,
        "is_special": text.strip().lower() in SPECIAL_MESSAGES,
        "terminated": len(text.split()) > MAX_FRIEND_WORDS,
        "sent_by_me": sent_by_me,
        "was_encrypted": was_encrypted,
    }


def _secret_key() -> str:
    key = os.environ.get("SPYCHAT_SECRET_KEY")
    if key:
        return key
    logger.warning(
        "SPYCHAT_SECRET_KEY not set; using a random key. Sessions will not "
        "survive a restart. Set it for production."
    )
    return secrets.token_hex(32)


def _configure_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=os.environ.get("SPYCHAT_LOG_LEVEL", "INFO"),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected a whole number.") from exc


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected a number.") from exc


def _err(exc: Exception):
    return jsonify({"error": str(exc)}), 400


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="spychat-web", description="SpyChat web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument(
        "--data-dir", default=os.environ.get("SPYCHAT_DATA_DIR", str(DEFAULT_DATA_DIR))
    )
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    app = create_app(args.data_dir)
    print(f"\n  🕵️  SpyChat is live at  http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
