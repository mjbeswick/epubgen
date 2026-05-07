from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

_FMT = "%(asctime)s %(levelname)-5s %(name)s: %(message)s"
_DATEFMT = "%H:%M:%S"


def default_log_path() -> Path:
    return Path.cwd() / f"epubgen-{time.strftime('%Y%m%d-%H%M%S')}.log"


def resolve_log_file(*, log: bool, log_file: Path | None) -> Path | None:
    if log_file is not None:
        return log_file
    if log:
        return default_log_path()
    return None


def configure_logging(*, verbose: bool, log_file: Path | None) -> None:
    root = logging.getLogger("epubgen")
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    if sys.stderr.isatty():
        # RichHandler cooperates with Live/status displays so spinners aren't torn.
        try:
            from rich.logging import RichHandler

            from epubgen.progress import _console as _stderr_console

            rich_handler = RichHandler(
                console=_stderr_console,
                show_path=False,
                show_time=False,
                markup=False,
                rich_tracebacks=True,
            )
            rich_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
            root.addHandler(rich_handler)
        except ImportError:
            stderr = logging.StreamHandler(sys.stderr)
            stderr.setLevel(logging.DEBUG if verbose else logging.INFO)
            stderr.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
            root.addHandler(stderr)
    else:
        stderr = logging.StreamHandler(sys.stderr)
        stderr.setLevel(logging.DEBUG if verbose else logging.INFO)
        stderr.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
        root.addHandler(stderr)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
        root.addHandler(fh)

    if verbose:
        # SDK + transport: surface request lifecycle but not full bodies by default.
        logging.getLogger("anthropic").setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.INFO)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
    else:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("anthropic").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"epubgen.{name}")
