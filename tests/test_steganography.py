import pytest
from PIL import Image

from spychat.steganography import (
    MessageTooLargeError,
    NoHiddenMessageError,
    SteganographyError,
    capacity_for_text,
    decode,
    encode,
)


def _make_image(path, size=(64, 64), color=(120, 200, 50)):
    Image.new("RGB", size, color).save(path)
    return path


def test_roundtrip(tmp_path):
    src = _make_image(tmp_path / "in.png")
    out = tmp_path / "out.png"
    encode(src, out, "the eagle lands at midnight")
    assert decode(out) == "the eagle lands at midnight"


def test_roundtrip_unicode(tmp_path):
    src = _make_image(tmp_path / "in.png")
    out = tmp_path / "out.png"
    msg = "rendez-vous à 23h — café ☕ секрет"
    encode(src, out, msg)
    assert decode(out) == msg


def test_empty_message_roundtrip(tmp_path):
    src = _make_image(tmp_path / "in.png")
    out = tmp_path / "out.png"
    encode(src, out, "")
    assert decode(out) == ""


def test_message_too_large(tmp_path):
    src = _make_image(tmp_path / "in.png", size=(4, 4))
    out = tmp_path / "out.png"
    with pytest.raises(MessageTooLargeError):
        encode(src, out, "x" * 1000)


def test_rejects_lossy_output(tmp_path):
    src = _make_image(tmp_path / "in.png")
    with pytest.raises(SteganographyError):
        encode(src, tmp_path / "out.jpg", "hi")


def test_decode_no_message(tmp_path):
    plain = _make_image(tmp_path / "plain.png")
    with pytest.raises(NoHiddenMessageError):
        decode(plain)


def test_capacity_reporting(tmp_path):
    src = _make_image(tmp_path / "in.png", size=(10, 10))
    # 10*10*3 bits = 300 bits = 37 bytes; minus 8-byte header = 29.
    assert capacity_for_text(src) == 29


def test_carrier_unchanged_visually(tmp_path):
    src = _make_image(tmp_path / "in.png", color=(255, 255, 255))
    out = tmp_path / "out.png"
    encode(src, out, "tiny")
    with Image.open(out) as img:
        # LSB tweaks change a channel by at most 1.
        assert all(abs(v - 255) <= 1 for px in img.getdata() for v in px)
