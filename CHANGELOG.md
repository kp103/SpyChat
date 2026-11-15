# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Multi-user accounts: register/login/logout with hashed passwords (Werkzeug)
  and a fully isolated profile per user.
- Web hardening: CSRF header check on mutating requests, upload size limit
  (`MAX_CONTENT_LENGTH`) with a 413 handler, Pillow decompression-bomb guard,
  `HttpOnly`/`SameSite` session cookies, and a `/healthz` endpoint.
- Cross-process write locking (`ProfileStore.lock()`) to prevent lost updates
  across server workers.
- Optional passphrase encryption for messages (AES/Fernet + scrypt).
- Ultra-modern Flask web UI (hide/reveal/friends/chats/identity) and a login
  screen, with accessibility improvements (ARIA labels, keyboard-accessible
  dropzones, associated form labels).
- Production deployment: `Dockerfile`, `docker-compose.yml`, WSGI entry point.
- Ruff linting and coverage reporting in CI; tests for the interactive CLI menu.

### Changed
- Complete rewrite from the Python 2 prototype to a Python 3 package with a
  self-contained steganography engine (Pillow only), JSON persistence, input
  validation, and a CLI (`spychat`) plus web entry point (`spychat-web`).
- Server now takes `--data-dir` / `SPYCHAT_DATA_DIR` (was a single profile path).

### Removed
- Committed `get-pip.py` and the legacy `new.py` / `xyz.py` prototype files.
- The unmaintained, Python 2-only `steganography` dependency.

### Fixed
- Carried-over bugs: quoted-string status print, never-firing special-message
  check, dropped first character on plain messages, and bare `except:` blocks.

## [1.0.0] — initial modernization
- First runnable Python 3 release with steganography engine, CLI, and tests.
