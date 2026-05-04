from __future__ import annotations

import os
from pathlib import Path

from epubgen.errors import ConfigError
from epubgen.schema import Options
from epubgen.workdir import default_workdir, slugify


def resolve_options(opts: Options) -> Options:
    if opts.workdir is None:
        opts.workdir = default_workdir(opts.out)
    return opts


def options_from_topic(
    topic: str,
    *,
    style: str = "oreilly",
    out: Path | None = None,
    **kwargs,
) -> Options:
    if out is None:
        out = Path(f"./{slugify(topic)}.epub")
    return resolve_options(Options(topic=topic, style=style, out=out, **kwargs))


def require_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ConfigError("ANTHROPIC_API_KEY not set")
    return key
