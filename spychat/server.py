"""Flask web server exposing SpyChat through a REST API + single-page UI.

Reuses the exact same engine as the CLI (:mod:`spychat.app`,
:mod:`spychat.steganography`, :mod:`spychat.storage`) so the web and terminal
front-ends never diverge.
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file
from PIL import Image, UnidentifiedImageError

from .app import MAX_FRIEND_WORDS, SPECIAL_MESSAGES, SpyChatApp, ValidationError
from .crypto import CryptoError, decrypt, encrypt, is_encrypted
from .models import ChatMessage, Profile
from .steganography import (
    NoHiddenMessageError,
    SteganographyError,
    _capacity_bytes,
    _HEADER_LEN,
    embed,
    extract,
)
from .storage import DEFAULT_PATH, ProfileStore

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent


def _spy_to_json(spy) -> dict:
    return {
        "name": spy.name,
        "salutation": spy.salutation,
        "display_name": spy.display_name,
        "age": spy.age,
        "rating": spy.rating,
        "current_status_message": spy.current_status_message,
        "chats": [
            {
                "message": c.message,
                "is_sent_by_me": c.is_sent_by_me,
                "time": c.time.isoformat(),
            }
            for c in spy.chats
        ],
    }


def _profile_to_json(app: SpyChatApp) -> dict:
    return {
        "spy": _spy_to_json(app.spy) if app.spy else None,
        "friends": [_spy_to_json(f) for f in app.friends],
        "status_messages": app.profile.status_messages,
    }


def create_app(profile_path: str | Path = DEFAULT_PATH) -> Flask:
    flask_app = Flask(
        __name__,
        static_folder=str(_HERE / "web" / "static"),
        template_folder=str(_HERE / "web" / "templates"),
        static_url_path="/static",
    )
    store = ProfileStore(profile_path)

    def load() -> SpyChatApp:
        try:
            return SpyChatApp(store.load())
        except Exception:  # noqa: BLE001
            return SpyChatApp(Profile())

    def save(app: SpyChatApp) -> None:
        try:
            store.save(app.profile)
        except OSError as exc:
            logger.warning("Could not save profile: %s", exc)

    # -- pages ---------------------------------------------------------------

    @flask_app.get("/")
    def index():
        return send_file(_HERE / "web" / "templates" / "index.html")

    # -- profile -------------------------------------------------------------

    @flask_app.get("/api/profile")
    def get_profile():
        return jsonify(_profile_to_json(load()))

    @flask_app.post("/api/spy")
    def register_spy():
        data = request.get_json(force=True, silent=True) or {}
        app = load()
        try:
            app.register_spy(
                data.get("name", ""),
                data.get("salutation", ""),
                _as_int(data.get("age")),
                _as_float(data.get("rating")),
            )
        except (ValidationError, ValueError) as exc:
            return _err(exc)
        save(app)
        return jsonify(_profile_to_json(app))

    # -- friends -------------------------------------------------------------

    @flask_app.post("/api/friends")
    def add_friend():
        data = request.get_json(force=True, silent=True) or {}
        app = load()
        try:
            app.add_friend(
                data.get("name", ""),
                data.get("salutation", ""),
                _as_int(data.get("age")),
                _as_float(data.get("rating")),
            )
        except (ValidationError, ValueError) as exc:
            return _err(exc)
        save(app)
        return jsonify(_profile_to_json(app))

    @flask_app.delete("/api/friends/<int:index>")
    def remove_friend(index: int):
        app = load()
        try:
            app.remove_friend(index)
        except ValidationError as exc:
            return _err(exc)
        save(app)
        return jsonify(_profile_to_json(app))

    # -- status --------------------------------------------------------------

    @flask_app.post("/api/status")
    def add_status():
        data = request.get_json(force=True, silent=True) or {}
        app = load()
        try:
            app.add_status_message(data.get("message", ""))
        except ValidationError as exc:
            return _err(exc)
        save(app)
        return jsonify(_profile_to_json(app))

    # -- steganography (stateless image in/out) ------------------------------

    @flask_app.post("/api/capacity")
    def capacity():
        """Report how many message bytes an uploaded image can hold."""
        file = request.files.get("image")
        if not file:
            return jsonify({"error": "No image uploaded."}), 400
        try:
            with Image.open(file.stream) as img:
                w, h = img.size
        except UnidentifiedImageError:
            return jsonify({"error": "Not a valid image."}), 400
        return jsonify({"capacity_bytes": max(0, _capacity_bytes(w, h) - _HEADER_LEN),
                        "width": w, "height": h})

    @flask_app.post("/api/encode")
    def api_encode():
        """Hide a message in an uploaded image; return the PNG and log the chat."""
        file = request.files.get("image")
        text = request.form.get("message", "")
        passphrase = request.form.get("passphrase", "")
        friend_index = request.form.get("friend_index", "")
        if not file:
            return jsonify({"error": "No image uploaded."}), 400
        if not text.strip():
            return jsonify({"error": "Message cannot be empty."}), 400

        app = load()
        inner = "#" + text  # "#" marks direction (sent by me)
        payload = encrypt(inner, passphrase) if passphrase else inner
        try:
            with Image.open(io.BytesIO(file.read())) as img:
                result_img = embed(img, payload)
        except (SteganographyError, CryptoError) as exc:
            return _err(exc)
        except UnidentifiedImageError:
            return jsonify({"error": "Not a valid image."}), 400

        # Optionally log against a friend (mirrors send_message bookkeeping).
        idx = _as_int(friend_index) if friend_index not in ("", None) else None
        if idx is not None and 0 <= idx < len(app.friends):
            app.friends[idx].chats.append(ChatMessage(message=text, is_sent_by_me=True))
            save(app)

        out_buf = io.BytesIO()
        result_img.save(out_buf, format="PNG")
        out_buf.seek(0)
        return send_file(
            out_buf, mimetype="image/png", as_attachment=True,
            download_name="secret_message.png",
        )

    @flask_app.post("/api/decode")
    def api_decode():
        file = request.files.get("image")
        passphrase = request.form.get("passphrase", "")
        friend_index = request.form.get("friend_index", "")
        if not file:
            return jsonify({"error": "No image uploaded."}), 400

        app = load()
        idx = _as_int(friend_index) if friend_index not in ("", None) else None
        try:
            with Image.open(io.BytesIO(file.read())) as img:
                raw_text = extract(img)
            result = _interpret(raw_text, passphrase)
        except (NoHiddenMessageError, CryptoError) as exc:
            return _err(exc)
        except UnidentifiedImageError:
            return jsonify({"error": "Not a valid image."}), 400

        if idx is not None and 0 <= idx < len(app.friends):
            app.friends[idx].chats.append(
                ChatMessage(message=result["text"], is_sent_by_me=result["sent_by_me"])
            )
            if result["terminated"]:
                del app.friends[idx]
            save(app)
        return jsonify(result)

    return flask_app


# -- helpers ----------------------------------------------------------------


def _interpret(raw_text: str, passphrase: str) -> dict:
    """Turn a raw extracted payload into a decoded-message result dict."""
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


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError("Expected a whole number.")


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("Expected a number.")


def _err(exc: Exception):
    return jsonify({"error": str(exc)}), 400


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="spychat-web", description="SpyChat web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--profile", default=str(DEFAULT_PATH))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    app = create_app(args.profile)
    print(f"\n  🕵️  SpyChat is live at  http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
