# Contributing to SpyChat

Thanks for your interest in improving SpyChat! This guide covers the basics.

## Development setup

```bash
git clone https://github.com/kp103/spychat.git
cd spychat
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before opening a pull request

Run the linter and the test suite — both must pass (CI enforces them):

```bash
ruff check spychat tests
pytest
```

- Add or update tests for any behaviour you change.
- Keep production code within the 100-character line limit (`ruff` enforces it).
- Match the existing style: type hints, small focused functions, and the
  engine/app/CLI/server layering (see the layout in the README).

## Project layout

The steganography engine (`steganography.py`), encryption (`crypto.py`), and
app logic (`app.py`) are I/O-free and shared by both the CLI (`cli.py`) and the
web server (`server.py`). Prefer adding logic to the shared layers so both
front-ends benefit and stay in sync.

## Reporting bugs / requesting features

Open an issue using the templates under `.github/ISSUE_TEMPLATE`. For security
issues, please avoid filing a public issue with exploit details — describe the
impact and we'll coordinate a fix.

## Security note

Steganography hides that a message exists; it is not, by itself, encryption.
The encryption option (passphrase) is what provides confidentiality. Keep this
distinction accurate in docs and UI copy.
