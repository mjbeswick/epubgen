from __future__ import annotations

from pathlib import Path

import questionary

from epubgen.schema import Options
from epubgen.styles import list_default_styles
from epubgen.workdir import default_workdir, slugify


def run_wizard() -> Options | None:
    topic = questionary.text("Topic:").ask()
    if not topic:
        return None

    style = questionary.select(
        "Style:",
        choices=[
            questionary.Choice(title=f"{name:<14} {desc}", value=name)
            for name, desc in list_default_styles()
        ],
    ).ask()
    if not style:
        return None

    length = questionary.select(
        "Target length:",
        choices=[
            questionary.Choice(title="Short  (6 ch / 2500 wpc)", value=(6, 2500)),
            questionary.Choice(title="Standard (10 ch / 3000 wpc)", value=(10, 3000)),
            questionary.Choice(title="Long  (16 ch / 3500 wpc)", value=(16, 3500)),
        ],
        default="Standard (10 ch / 3000 wpc)",
    ).ask()
    if not length:
        return None
    chapters, words = length

    kindle = questionary.confirm("Optimize for Kindle?", default=True).ask()
    if kindle is None:
        return None

    default_out = f"./{slugify(topic)}.epub"
    out = questionary.text("Output path:", default=default_out).ask()
    if not out:
        return None

    out_path = Path(out)
    return Options(
        topic=topic,
        style=style,
        out=out_path,
        workdir=default_workdir(out_path),
        chapters=chapters,
        words=words,
        kindle=bool(kindle),
    )
