# SpyChat 🕵️

Hide secret messages **inside images**, spy-style. SpyChat is a small Python 3
command-line app that conceals your text in the pixels of a picture using
least-significant-bit (LSB) steganography — the image looks unchanged, but it
carries a hidden payload only SpyChat can read back.

It keeps a roster of "friend" spies, logs your encoded/decoded conversations,
and persists everything to a local JSON profile.

> Rewritten from the original Python 2 prototype: ported to Python 3, given a
> self-contained steganography engine (no unmaintained dependencies),
> validation, persistence, a test suite, and a real CLI.

## Features

- **Hide & reveal messages** in PNG/JPEG/BMP carrier images (output is always
  lossless PNG so the hidden bits survive).
- **Interactive menu** to manage your spy identity, friends, statuses and chats.
- **One-shot subcommands** (`encode` / `decode`) for scripting.
- **Persistent profile** stored as JSON (atomic, crash-safe writes).
- **Validated rules**: age gates, rating gates, capacity checks, clear errors.
- **Tested**: full `pytest` suite covering steganography, app logic and storage.

## Requirements

- Python 3.9+
- [Pillow](https://pypi.org/project/Pillow/) ≥ 9.0 (only runtime dependency)

## Installation

```bash
git clone https://github.com/kp103/spychat.git
cd spychat

python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -e .          # installs the `spychat` command + Pillow
# or, without installing the package:
pip install -r requirements.txt
```

## Usage

### Interactive mode

```bash
spychat                       # or: python -m spychat
```

You'll set up a spy identity on first run; your profile is saved to
`~/.spychat/profile.json` (override with `--profile PATH`).

### One-shot encode / decode

```bash
# Hide a message (output MUST be .png or .bmp):
spychat encode samples/carrier.jpg secret.png "the eagle lands at midnight"

# Reveal it:
spychat decode secret.png
# -> the eagle lands at midnight
```

### From Python

```python
from spychat import encode, decode

encode("samples/carrier.jpg", "secret.png", "rendez-vous at 23h")
print(decode("secret.png"))   # rendez-vous at 23h
```

## How it works

Each pixel has three colour channels (R, G, B). SpyChat overwrites the
least-significant bit of each channel with one bit of your message, changing
every channel by at most 1 — imperceptible to the eye. A small header
(`SPY1` magic + 4-byte length) lets the decoder detect non-SpyChat images and
know exactly how many bytes to read.

**Important:** the carrier *output* must be lossless (PNG/BMP). Saving as JPEG
would re-compress the pixels and destroy the hidden data, so `encode` refuses
lossy output formats. A 64×64 image holds ~1.5 KB of text; larger images hold
more (`spychat.steganography.capacity_for_text`).

> ⚠️ Steganography hides the *existence* of a message; it is **not** encryption.
> For confidentiality, encrypt the text before hiding it.

## Development

```bash
pip install -e ".[dev]"
pytest                 # run the test suite
```

### Project layout

```
spychat/
  steganography.py   # LSB encode/decode engine (Pillow only)
  models.py          # Spy, ChatMessage, Profile dataclasses
  storage.py         # atomic JSON persistence
  app.py             # business logic + validation (I/O-free, unit-tested)
  cli.py             # argparse + interactive menu
tests/               # pytest suite
samples/carrier.jpg  # sample carrier image
```

## License

MIT — see [LICENSE](LICENSE).
