"""Least-significant-bit (LSB) image steganography.

This module hides arbitrary UTF-8 text inside the pixels of an image by
overwriting the least-significant bit of each colour channel. It is
self-contained (only Pillow is required) and replaces the unmaintained,
Python 2-only ``steganography`` package the project used previously.

Format of the embedded payload::

    [ 4-byte magic "SPY1" ][ 4-byte big-endian length ][ <length> bytes UTF-8 ]

The magic lets :func:`decode` detect images that do not contain a SpyChat
message instead of returning garbage. Output images **must** be a lossless
format (PNG); saving as JPEG would re-compress the pixels and destroy the
hidden bits, so :func:`encode` enforces this.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from PIL import Image

MAGIC = b"SPY1"
_HEADER_LEN = len(MAGIC) + 4  # magic + 4-byte length
_BITS_PER_PIXEL = 3  # R, G, B

PathLike = Union[str, Path]


class SteganographyError(Exception):
    """Base class for steganography failures."""


class MessageTooLargeError(SteganographyError):
    """The carrier image does not have enough pixels for the message."""


class NoHiddenMessageError(SteganographyError):
    """The image does not contain a SpyChat payload."""


def _bytes_to_bits(data: bytes):
    for byte in data:
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1


def _capacity_bytes(width: int, height: int) -> int:
    """Maximum payload size (including header) for an image, in bytes."""
    return (width * height * _BITS_PER_PIXEL) // 8


def capacity_for_text(image_path: PathLike) -> int:
    """Return how many UTF-8 *message* bytes ``image_path`` can hold."""
    with Image.open(image_path) as img:
        width, height = img.size
    return max(0, _capacity_bytes(width, height) - _HEADER_LEN)


def encode(input_path: PathLike, output_path: PathLike, message: str) -> Path:
    """Hide ``message`` inside ``input_path`` and write it to ``output_path``.

    Returns the path written. Raises :class:`MessageTooLargeError` if the
    image is too small, and :class:`SteganographyError` if the output is not
    a lossless format.
    """
    output_path = Path(output_path)
    if output_path.suffix.lower() not in {".png", ".bmp"}:
        raise SteganographyError(
            "Output must be a lossless format (.png or .bmp); "
            f"got {output_path.suffix!r}. JPEG would destroy the hidden data."
        )

    payload = MAGIC + len(message.encode("utf-8")).to_bytes(4, "big") + message.encode("utf-8")

    with Image.open(input_path) as img:
        img = img.convert("RGB")
        width, height = img.size

        if len(payload) > _capacity_bytes(width, height):
            raise MessageTooLargeError(
                f"Message needs {len(payload)} bytes but the image only holds "
                f"{_capacity_bytes(width, height)}. Use a larger image."
            )

        pixels = list(img.getdata())
        bits = _bytes_to_bits(payload)
        new_pixels = []
        done = False
        for r, g, b in pixels:
            if done:
                new_pixels.append((r, g, b))
                continue
            channels = [r, g, b]
            for i in range(3):
                bit = next(bits, None)
                if bit is None:
                    done = True
                    break
                channels[i] = (channels[i] & ~1) | bit
            new_pixels.append(tuple(channels))

        img.putdata(new_pixels)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)

    return output_path


def decode(image_path: PathLike) -> str:
    """Extract and return the hidden message from ``image_path``.

    Raises :class:`NoHiddenMessageError` if the image holds no SpyChat
    payload (or it is corrupted).
    """
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        pixels = img.getdata()

        bits = []
        needed_bytes = _HEADER_LEN  # we learn the full size after the header
        collected = bytearray()

        for r, g, b in pixels:
            for channel in (r, g, b):
                bits.append(channel & 1)
                if len(bits) == 8:
                    collected.append(int("".join(map(str, bits)), 2))
                    bits.clear()

                    if len(collected) == len(MAGIC) and bytes(collected) != MAGIC:
                        raise NoHiddenMessageError(
                            "No SpyChat message found in this image."
                        )
                    if len(collected) == _HEADER_LEN:
                        msg_len = int.from_bytes(collected[len(MAGIC):], "big")
                        needed_bytes = _HEADER_LEN + msg_len
                    if len(collected) >= _HEADER_LEN and len(collected) == needed_bytes:
                        return collected[_HEADER_LEN:].decode("utf-8", errors="replace")

    raise NoHiddenMessageError("Image ended before the full message was read.")
