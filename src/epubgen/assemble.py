from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

from epubgen.errors import PandocError
from epubgen.logsetup import get_logger
from epubgen.schema import Options, Outline
from epubgen.styles import Style
from epubgen.workdir import atomic_write_text, chapter_path

log = get_logger("assemble")


def has_pandoc() -> bool:
    return shutil.which("pandoc") is not None


def has_kindlepreviewer() -> bool:
    return shutil.which("kindlepreviewer") is not None


def metadata_yaml(outline: Outline, opts: Options) -> str:
    md: dict = {
        "title": outline.title,
        "author": outline.author,
        "lang": "en-US",
        "rights": f"© {outline.author}",
    }
    if outline.subtitle:
        md["subtitle"] = outline.subtitle
    md.update(opts.metadata)
    return yaml.safe_dump(md, sort_keys=False)


def write_metadata(outline: Outline, opts: Options, workdir: Path) -> Path:
    path = workdir / "metadata.yaml"
    atomic_write_text(path, metadata_yaml(outline, opts))
    return path


def write_css(style: Style, workdir: Path) -> Path:
    path = workdir / "style.css"
    atomic_write_text(path, style.css)
    return path


def build_pandoc_args(
    *,
    out: Path,
    metadata_file: Path,
    css: Path,
    cover: Path | None,
    chapter_files: list[Path],
    kindle: bool,
) -> list[str]:
    highlight = "monochrome" if kindle else "pygments"
    args = [
        "pandoc",
        "--from=markdown",
        "--to=epub3",
        f"--output={out}",
        f"--metadata-file={metadata_file}",
        f"--css={css}",
        "--toc",
        "--toc-depth=2",
        "--split-level=1",
        f"--highlight-style={highlight}",
    ]
    if cover is not None:
        args.append(f"--epub-cover-image={cover}")
    args.extend(str(p) for p in chapter_files)
    return args


def assemble(
    *,
    outline: Outline,
    style: Style,
    opts: Options,
    workdir: Path,
    cover: Path | None,
) -> Path:
    if not has_pandoc():
        raise PandocError("pandoc not found on PATH (try: brew install pandoc)")
    metadata_file = write_metadata(outline, opts, workdir)
    css = write_css(style, workdir)
    chapter_files = [chapter_path(workdir, ch.number) for ch in outline.chapters]
    missing = [str(p) for p in chapter_files if not p.exists()]
    if missing:
        raise PandocError(f"missing chapter files: {missing}")

    opts.out.parent.mkdir(parents=True, exist_ok=True)
    args = build_pandoc_args(
        out=opts.out,
        metadata_file=metadata_file,
        css=css,
        cover=cover,
        chapter_files=chapter_files,
        kindle=opts.kindle,
    )
    log.debug("pandoc argv: %s", args)
    result = subprocess.run(args, capture_output=True, text=True)
    log_path = workdir / "assembled.log"
    atomic_write_text(
        log_path,
        f"$ {' '.join(args)}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n",
    )
    if result.stderr:
        log.debug("pandoc stderr:\n%s", result.stderr)
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-20:]
        raise PandocError(f"pandoc exited {result.returncode}:\n" + "\n".join(tail))
    log.info("pandoc ok: %s", opts.out)
    return opts.out


def maybe_make_azw3(epub: Path) -> Path | None:
    if not has_kindlepreviewer():
        return None
    out_dir = epub.parent
    result = subprocess.run(
        ["kindlepreviewer", str(epub), "-convert", "-locale", "en", "-output", str(out_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    azw3 = epub.with_suffix(".azw3")
    return azw3 if azw3.exists() else None
