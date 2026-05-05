from __future__ import annotations

import base64
import os
from pathlib import Path

from epubgen.logsetup import get_logger
from epubgen.workdir import atomic_write_bytes

log = get_logger("images")

DEFAULT_SIZE = "1024x1024"
COVER_SIZE = "1024x1536"


def has_openai_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def has_openai_sdk() -> bool:
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return True


def is_available() -> bool:
    return has_openai_key() and has_openai_sdk()


def generate_image(prompt: str, out_path: Path, *, size: str = DEFAULT_SIZE) -> bool:
    """Generate an image via OpenAI gpt-image-1. Returns True on success.

    Logs and returns False on any failure — callers should fall back gracefully.
    """
    if not is_available():
        log.warning(
            "image gen unavailable (OPENAI_API_KEY=%s, openai SDK=%s)",
            "set" if has_openai_key() else "unset",
            has_openai_sdk(),
        )
        return False
    try:
        from openai import OpenAI

        client = OpenAI()
        result = client.images.generate(model="gpt-image-1", prompt=prompt, size=size)
        b64 = result.data[0].b64_json
        if not b64:
            log.warning("openai returned no image data for prompt %r", prompt[:80])
            return False
        atomic_write_bytes(out_path, base64.b64decode(b64))
        log.info("image written: %s", out_path)
        return True
    except Exception as e:
        log.warning("openai image generation failed: %s", e)
        return False
