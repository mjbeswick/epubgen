from __future__ import annotations

from epubgen.schema import Outline
from epubgen.styles import Style


def build_cover_image_prompt(style: Style, outline: Outline, override: str | None = None) -> str:
    if override:
        return override
    return (
        f'Book cover for "{outline.title}". '
        f"Subject: {outline.topic}. "
        f"Style aesthetic: {style.name} (technical book cover). "
        "Composition: title and author legible, single strong central motif, "
        "high-contrast, no embedded text artifacts. Portrait 1600x2400."
    )
