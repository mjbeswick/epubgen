"""Load user-provided source material into a single text bundle for prompt grounding.

The bundle is injected as a cached system block in outline + chapter prompts so
the model writes against the user's material instead of priors. Non-text formats
(.pdf, .docx, .epub, .html) are converted via pandoc.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from epubgen.errors import ConfigError, FsError
from epubgen.logsetup import get_logger

log = get_logger("sources")

# Plain-read extensions (no conversion needed).
_TEXT_EXTS = frozenset({".md", ".markdown", ".txt", ".rst", ".org", ".tex", ""})
# Pandoc-convertible extensions.
_PANDOC_EXTS = frozenset({".html", ".htm", ".docx", ".epub", ".odt", ".rtf"})
# PDF — pandoc can't read PDFs; needs pdftotext.
_PDF_EXTS = frozenset({".pdf"})

# Reasonable per-file ceiling so a stray giant file doesn't blow the cache budget.
# 1 MB ≈ 250k tokens — anything larger should be split by the user.
_MAX_BYTES_PER_FILE = 4 * 1024 * 1024


@dataclass
class SourceFile:
    path: Path
    text: str
    sha256: str


def _expand_arg(arg: Path) -> list[Path]:
    """Resolve a CLI --source argument (file, directory, or glob) into files."""
    s = str(arg)
    # Globs: any of *, ?, [
    if any(ch in s for ch in "*?["):
        matches = sorted(Path().glob(s))
        if not matches:
            raise ConfigError(f"--source {s!r} matched no files")
        return [m for m in matches if m.is_file()]
    if not arg.exists():
        raise ConfigError(f"--source path does not exist: {arg}")
    if arg.is_file():
        return [arg]
    if arg.is_dir():
        files = sorted(p for p in arg.rglob("*") if p.is_file() and not _ignored(p))
        if not files:
            raise ConfigError(f"--source dir {arg} contains no readable files")
        return files
    raise ConfigError(f"--source {arg} is neither file, dir, nor glob")


def _ignored(p: Path) -> bool:
    parts = set(p.parts)
    if any(part.startswith(".") and part not in {".", ".."} for part in p.parts):
        return True
    if {"node_modules", "__pycache__", "dist", "build", ".venv", "venv"} & parts:
        return True
    return False


def _read_text(path: Path) -> str:
    size = path.stat().st_size
    if size > _MAX_BYTES_PER_FILE:
        raise ConfigError(
            f"source file {path} is {size / 1e6:.1f} MB (limit "
            f"{_MAX_BYTES_PER_FILE / 1e6:.0f} MB); split it before passing"
        )
    ext = path.suffix.lower()
    if ext in _TEXT_EXTS:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise FsError(f"failed to read {path}: {e}") from e
    if ext in _PANDOC_EXTS:
        return _pandoc_to_text(path)
    if ext in _PDF_EXTS:
        return _pdf_to_text(path)
    # Unknown extension — try as text, but warn.
    log.warning("source %s has unknown extension %r; reading as text", path, ext)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError) as e:
        raise ConfigError(f"cannot read {path} as text ({e}); unsupported format") from e


def _pandoc_to_text(path: Path) -> str:
    if not shutil.which("pandoc"):
        raise ConfigError(f"pandoc required to read {path.suffix} (install: brew install pandoc)")
    try:
        out = subprocess.run(
            ["pandoc", "--from=" + _pandoc_from(path), "--to=plain", "--wrap=none", str(path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        raise ConfigError(f"pandoc failed on {path}: {e.stderr.strip() or e}") from e
    except subprocess.TimeoutExpired as e:
        raise ConfigError(f"pandoc timed out on {path}") from e
    return out.stdout


def _pandoc_from(path: Path) -> str:
    return {
        ".html": "html",
        ".htm": "html",
        ".docx": "docx",
        ".epub": "epub",
        ".odt": "odt",
        ".rtf": "rtf",
    }[path.suffix.lower()]


def _pdf_to_text(path: Path) -> str:
    tool = shutil.which("pdftotext")
    if tool:
        try:
            out = subprocess.run(
                [tool, "-layout", "-nopgbrk", str(path), "-"],
                check=True, capture_output=True, text=True, timeout=180,
            )
            return out.stdout
        except subprocess.CalledProcessError as e:
            raise ConfigError(f"pdftotext failed on {path}: {e.stderr.strip() or e}") from e
    # Fallback: try pypdf if installed.
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ConfigError(
            f"reading {path} requires pdftotext (brew install poppler) or pypdf "
            "(uv pip install pypdf)"
        ) from e
    try:
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:  # pypdf raises a wide variety
        raise ConfigError(f"pypdf failed on {path}: {e}") from e


def load_sources(args: list[Path]) -> list[SourceFile]:
    """Resolve CLI args into a flat list of loaded source files (deduplicated)."""
    seen: dict[Path, SourceFile] = {}
    for arg in args:
        for path in _expand_arg(arg):
            resolved = path.resolve()
            if resolved in seen:
                continue
            text = _read_text(path)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            seen[resolved] = SourceFile(path=path, text=text, sha256=digest)
            log.info("loaded source %s (%d chars, sha256=%s)", path, len(text), digest[:12])
    return list(seen.values())


def build_bundle(sources: list[SourceFile]) -> str:
    """Concatenate sources with filename headers for the cached system block."""
    if not sources:
        return ""
    parts = [
        "The following are reference sources provided by the user. Ground every "
        "factual claim in these sources; if a claim is not supported here, omit it "
        "rather than confabulate. Quote sparingly and paraphrase by default. "
        "Do not enumerate the sources to the reader unless asked.\n"
    ]
    for s in sources:
        parts.append(f"\n=== SOURCE: {s.path.name} ===\n{s.text.strip()}\n")
    return "".join(parts)


def freeze_digest(sources: list[SourceFile]) -> list[dict[str, str]]:
    """Stable list of (filename, sha256) for options.json."""
    return [{"name": s.path.name, "sha256": s.sha256} for s in sources]
