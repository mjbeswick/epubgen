from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from epubgen import pipeline
from epubgen.costs import get_tally
from epubgen.doctor import fatal_checks, format_checks, run_checks
from epubgen.errors import (
    ApiError,
    ConfigError,
    EpubgenError,
    FsError,
    OutlineError,
    PandocError,
)
from epubgen.logsetup import configure_logging, get_logger, resolve_log_file
from epubgen.schema import Options
from epubgen.styles import list_all_styles, load_style
from epubgen.workdir import default_workdir, slugify

app = typer.Typer(
    add_completion=True,
    help="Generate EPUB books from a topic + style via the Anthropic API.",
    no_args_is_help=False,
)
styles_app = typer.Typer(help="Inspect available style presets.")
app.add_typer(styles_app, name="styles")
amend_app = typer.Typer(help="Modify an existing book's workdir in place.", no_args_is_help=True)
app.add_typer(amend_app, name="amend")

EXIT_USER = 1
EXIT_API = 2
EXIT_PANDOC = 3
EXIT_FS = 4
EXIT_OUTLINE = 5


_PREFLIGHT_SKIP = {"doctor", "styles", "amend"}


def _validate_model(model: str) -> str:
    """Normalize the model id and offer a did-you-mean on typos.

    Unknown ids aren't fatal — OpenRouter accepts arbitrary `vendor/model` tails,
    and provider catalogs change. We just warn and pass through.
    """
    import difflib

    from epubgen.costs import RATES
    from epubgen.llm import normalize_model

    normalized = normalize_model(model)
    if normalized in RATES:
        return normalized
    # Allow openrouter pass-through for any tail.
    if normalized.startswith("openrouter/"):
        return normalized
    suggestions = difflib.get_close_matches(normalized, list(RATES.keys()), n=3, cutoff=0.5)
    if suggestions:
        typer.secho(
            f"unknown model {model!r} — did you mean: {', '.join(suggestions)}?",
            fg=typer.colors.YELLOW, err=True,
        )
    else:
        typer.secho(
            f"unknown model {model!r} (proceeding; will fail at API call if invalid)",
            fg=typer.colors.YELLOW, err=True,
        )
    return normalized


def _preflight() -> None:
    checks = run_checks()
    fatal = fatal_checks(checks)
    if fatal:
        typer.secho("preflight failed:", fg=typer.colors.RED, err=True)
        typer.echo(format_checks(checks), err=True)
        typer.secho("\nrun `epubgen doctor` for full report", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_USER)


_PROVIDER_KEYS = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
}


def _check_provider_key(model: str) -> None:
    """Fail fast if the chosen model's provider key isn't set."""
    import os

    from epubgen.llm import provider_of

    provider = provider_of(model)
    envs = _PROVIDER_KEYS.get(provider, ())
    if envs and not any(os.environ.get(e) for e in envs):
        env_list = " or ".join(envs)
        typer.secho(
            f"model {model!r} needs {env_list} (none set)",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(EXIT_USER)


def _run(opts: Options) -> None:
    log = get_logger("cli")
    log.debug("resolved options: %s", opts.model_dump_json())
    _check_provider_key(opts.model)
    try:
        out = pipeline.run(opts)
        typer.secho(f"✓ wrote {out}", fg=typer.colors.GREEN, err=True)
        for line in get_tally().summary_lines():
            typer.secho(line, err=True)
    except ConfigError as e:
        log.error("config error: %s", e, exc_info=True)
        typer.secho(f"config: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER) from e
    except OutlineError as e:
        log.error("outline error: %s", e, exc_info=True)
        typer.secho(f"outline: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_OUTLINE) from e
    except ApiError as e:
        # If we have a clear hint, the failure is well-understood — skip the
        # traceback dump (still recorded to --log-file at DEBUG).
        log.error("api error: %s", e, exc_info=e.hint is None)
        typer.secho(f"api: {e}", fg=typer.colors.RED, err=True)
        if e.hint:
            typer.secho(f"  → {e.hint}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_API) from e
    except PandocError as e:
        log.error("pandoc error: %s", e, exc_info=True)
        typer.secho(f"pandoc: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_PANDOC) from e
    except FsError as e:
        log.error("fs error: %s", e, exc_info=True)
        typer.secho(f"fs: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_FS) from e
    except EpubgenError as e:
        log.error("error: %s", e, exc_info=True)
        typer.secho(f"error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER) from e
    except Exception as e:
        log.exception("unexpected error")
        typer.secho(f"unexpected: {type(e).__name__}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER) from e


@app.command()
def generate(
    topic: Annotated[str, typer.Argument(help="Book topic")],
    style: Annotated[str, typer.Option("--style", "-s", help="Style preset")] = "oreilly",
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Output .epub path")] = None,
    workdir: Annotated[Path | None, typer.Option("--workdir", "-w", help="Work dir")] = None,
    chapters: Annotated[int | None, typer.Option("--chapters", "-c")] = None,
    words: Annotated[
        int | None,
        typer.Option(
            "--words", "-W",
            help="Force a uniform target words per chapter (default: model picks per chapter)",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model", "-m",
            help="Anthropic model (default: persisted user preference, else claude-sonnet-4-6)",
        ),
    ] = None,
    concurrency: Annotated[int, typer.Option("--concurrency")] = 3,
    ereader: Annotated[
        bool,
        typer.Option(
            "--ereader/--no-ereader",
            "--kindle/--no-kindle",  # backward-compat alias
            help="Tune for ~6\" e-readers — Kindle/Kobo/KOReader (default: on). "
            "Tighter code lines, monochrome highlight, AZW3 if kindlepreviewer present. "
            "Use --no-ereader for tablet/desktop output.",
        ),
    ] = True,
    no_cover: Annotated[bool, typer.Option("--no-cover", help="Skip cover generation")] = False,
    no_diagrams: Annotated[
        bool,
        typer.Option("--no-diagrams", help="Skip all figure rendering (mermaid+chart+image)"),
    ] = False,
    no_images: Annotated[
        bool, typer.Option("--no-images", help="Skip generated images only (keep mermaid/charts)")
    ] = False,
    sources: Annotated[
        list[Path] | None,
        typer.Option(
            "--source",
            help="Reference source (file, dir, or glob). Repeatable. "
            "Supports .md/.txt/.html/.docx/.epub/.pdf and other text formats. "
            "Sources ground the outline + every chapter via prompt caching.",
        ),
    ] = None,
    cover_prompt: Annotated[str | None, typer.Option("--cover-prompt")] = None,
    author: Annotated[str, typer.Option("--author")] = "epubgen",
    force: Annotated[bool, typer.Option("--force", help="Override options.json mismatch")] = False,
    refine: Annotated[
        bool, typer.Option("--refine", help="Interactively refine title/subtitle (TTY required)")
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    log: Annotated[
        bool, typer.Option("--log", help="Write debug log to ./epubgen-<ts>.log")
    ] = False,
    log_file: Annotated[
        Path | None, typer.Option("--log-file", help="Write a debug log to this path")
    ] = None,
) -> None:
    """Generate an EPUB from a topic."""
    resolved_log = resolve_log_file(log=log, log_file=log_file)
    configure_logging(verbose=verbose, log_file=resolved_log)
    if resolved_log is not None:
        typer.secho(f"📝 logging to {resolved_log}", fg=typer.colors.CYAN, err=True)
    get_logger("cli").info("epubgen generate: topic=%r style=%s", topic, style)
    from epubgen import userprefs

    if model is None:
        model = userprefs.get_default_model()
    model = _validate_model(model)
    out_path = out or Path(f"./{slugify(topic)}.epub")
    preferred_title = None
    preferred_subtitle = None
    if refine:
        if not sys.stdin.isatty():
            typer.secho("--refine requires a TTY", fg=typer.colors.RED, err=True)
            raise typer.Exit(EXIT_USER)
        from epubgen.wizard import _interactive_refine

        chosen = _interactive_refine(style, topic, model=model)
        if chosen is not None:
            preferred_title = chosen.title
            preferred_subtitle = chosen.subtitle
            if out is None:
                out_path = Path(f"./{slugify(chosen.title)}.epub")
    opts = Options(
        topic=topic,
        style=style,
        out=out_path,
        workdir=workdir or default_workdir(out_path),
        chapters=chapters,
        words=words,
        model=model,
        concurrency=concurrency,
        ereader=ereader,
        no_cover=no_cover,
        no_diagrams=no_diagrams,
        no_images=no_images,
        cover_prompt=cover_prompt,
        sources=sources or [],
        author=author,
        preferred_title=preferred_title,
        preferred_subtitle=preferred_subtitle,
        force=force,
        dry_run=dry_run,
        verbose=verbose,
    )
    if dry_run:
        typer.echo(opts.model_dump_json(indent=2))
        return
    # Up-front cost hint so spend isn't a surprise post-run.
    from epubgen.costs import estimate_book_cost

    est = estimate_book_cost(opts.model, chapters=opts.chapters or 12)
    typer.secho(
        f"estimated cost: ~${est:.2f}  (model: {opts.model})",
        fg=typer.colors.CYAN, err=True,
    )
    _run(opts)


@app.command()
def wizard(
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    log: Annotated[bool, typer.Option("--log")] = False,
    log_file: Annotated[Path | None, typer.Option("--log-file")] = None,
) -> None:
    """Interactive prompt-driven generation."""
    resolved_log = resolve_log_file(log=log, log_file=log_file)
    configure_logging(verbose=verbose, log_file=resolved_log)
    if resolved_log is not None:
        typer.secho(f"📝 logging to {resolved_log}", fg=typer.colors.CYAN, err=True)
    from epubgen.wizard import run_wizard

    opts = run_wizard()
    if opts is None:
        typer.secho("cancelled", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_USER)
    _run(opts)


def _resolve_resume_workdir(arg: Path | None) -> Path | None:
    """Find a workdir to resume from a flexible argument.

    Accepts: a workdir path, an .epub path (workdir derived as <epub>.work),
    a directory to search, or None (search cwd). Prompts interactively if
    multiple candidates are found. Returns None on user cancel; raises typer.Exit
    if no candidates exist.
    """
    # Direct .epub path → derive its workdir.
    if arg is not None and arg.suffix == ".epub":
        derived = Path(str(arg) + ".work")
        if (derived / "options.json").exists():
            return derived
        typer.secho(
            f"no options.json in {derived} (derived from {arg})",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(EXIT_USER)

    # Direct workdir hit.
    direct = arg or Path(".")
    if (direct / "options.json").exists():
        return direct

    # Otherwise treat the argument as a directory to search for *.work/.
    search_root = direct if direct.is_dir() else Path(".")
    candidates = sorted(
        p for p in search_root.glob("*.work") if (p / "options.json").exists()
    )
    if not candidates:
        typer.secho(
            f"no resumable workdir found at {direct} "
            f"(looked for options.json or *.work/options.json)",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(EXIT_USER)
    if len(candidates) == 1:
        typer.secho(f"resuming {candidates[0]}", fg=typer.colors.CYAN, err=True)
        return candidates[0]
    # Multiple — pick interactively if we have a TTY, otherwise list and bail.
    if not sys.stdin.isatty():
        typer.secho(
            f"multiple resumable workdirs in {search_root}; specify one:",
            fg=typer.colors.RED, err=True,
        )
        for c in candidates:
            typer.echo(f"  {c}", err=True)
        raise typer.Exit(EXIT_USER)
    import questionary

    picked = questionary.select(
        "Multiple resumable workdirs — which one?",
        choices=[questionary.Choice(title=str(c), value=c) for c in candidates],
    ).ask()
    return picked


@app.command()
def resume(
    workdir: Annotated[
        Path | None,
        typer.Argument(
            help="Work dir, .epub path, or a directory to search (default: cwd)",
        ),
    ] = None,
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
    sources: Annotated[
        list[Path] | None,
        typer.Option(
            "--source",
            help="Re-pass source paths used in the original run. "
            "Digests are verified against the frozen options.json.",
        ),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    log: Annotated[bool, typer.Option("--log")] = False,
    log_file: Annotated[Path | None, typer.Option("--log-file")] = None,
) -> None:
    """Resume an interrupted run from its workdir."""
    resolved_log = resolve_log_file(log=log, log_file=log_file)
    configure_logging(verbose=verbose, log_file=resolved_log)
    if resolved_log is not None:
        typer.secho(f"📝 logging to {resolved_log}", fg=typer.colors.CYAN, err=True)
    import json

    resolved = _resolve_resume_workdir(workdir)
    if resolved is None:
        typer.secho("cancelled", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_USER)

    frozen = json.loads((resolved / "options.json").read_text())
    out_path = out or Path(f"./{slugify(frozen['topic'])}.epub")
    opts = Options(out=out_path, workdir=resolved, sources=sources or [], **frozen)
    _run(opts)


@app.command()
def doctor() -> None:
    """Check the runtime environment for required and optional dependencies."""
    checks = run_checks()
    typer.echo(format_checks(checks))
    if fatal_checks(checks):
        raise typer.Exit(EXIT_USER)


def _amend_run(fn, /, *args, **kwargs) -> None:
    """Wrap an amend operation with the standard error mapping."""
    log = get_logger("cli.amend")
    try:
        result = fn(*args, **kwargs)
    except ConfigError as e:
        log.error("config error: %s", e)
        typer.secho(f"config: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER) from e
    except ApiError as e:
        log.error("api error: %s", e, exc_info=e.hint is None)
        typer.secho(f"api: {e}", fg=typer.colors.RED, err=True)
        if e.hint:
            typer.secho(f"  → {e.hint}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_API) from e
    except PandocError as e:
        log.error("pandoc error: %s", e)
        typer.secho(f"pandoc: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_PANDOC) from e
    except FsError as e:
        log.error("fs error: %s", e)
        typer.secho(f"fs: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_FS) from e
    except EpubgenError as e:
        log.error("error: %s", e)
        typer.secho(f"error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER) from e
    if isinstance(result, Path):
        typer.secho(f"✓ wrote {result}", fg=typer.colors.GREEN, err=True)


@amend_app.command("rebuild")
def amend_rebuild(
    workdir: Annotated[
        Path | None,
        typer.Argument(help="Work dir, .epub path, or a directory to search"),
    ] = None,
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
    regen_cover: Annotated[
        bool,
        typer.Option("--regen-cover", help="Re-generate the cover (otherwise reuse existing)"),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Re-render figures and reassemble the EPUB from current workdir state."""
    configure_logging(verbose=verbose, log_file=None)
    resolved = _resolve_resume_workdir(workdir)
    if resolved is None:
        typer.secho("cancelled", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_USER)
    from epubgen.amend_pipeline import rebuild

    _amend_run(rebuild, resolved, out=out, regen_cover=regen_cover)


@amend_app.command("retitle")
def amend_retitle(
    workdir: Annotated[Path | None, typer.Argument()] = None,
    title: Annotated[str | None, typer.Option("--title")] = None,
    subtitle: Annotated[str | None, typer.Option("--subtitle")] = None,
    clear_subtitle: Annotated[bool, typer.Option("--clear-subtitle")] = False,
    rebuild: Annotated[bool, typer.Option("--rebuild/--no-rebuild")] = True,
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
) -> None:
    """Change book title and/or subtitle. No model calls."""
    if title is None and subtitle is None and not clear_subtitle:
        typer.secho("nothing to change (pass --title / --subtitle / --clear-subtitle)",
                    fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_USER)
    resolved = _resolve_resume_workdir(workdir)
    if resolved is None:
        raise typer.Exit(EXIT_USER)
    from epubgen import amend as amend_mod

    def _do() -> Path | None:
        outline, frozen = amend_mod.load_workdir(resolved)
        if clear_subtitle:
            sub_arg: object = None
        elif subtitle is not None:
            sub_arg = subtitle
        else:
            sub_arg = ...
        new_outline = amend_mod.retitle(outline, title=title, subtitle=sub_arg)  # type: ignore[arg-type]
        amend_mod.save(resolved, new_outline)
        typer.secho(f"✓ retitled → {new_outline.title!r}", fg=typer.colors.GREEN, err=True)
        if rebuild:
            from epubgen.amend_pipeline import rebuild as rebuild_fn
            return rebuild_fn(resolved, out=out)
        return None

    _amend_run(_do)


@amend_app.command("remove")
def amend_remove(
    workdir: Annotated[Path | None, typer.Argument()] = None,
    n: Annotated[int, typer.Argument(help="Chapter number to remove")] = 0,
    rebuild: Annotated[bool, typer.Option("--rebuild/--no-rebuild")] = True,
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
) -> None:
    """Remove a chapter and renumber the rest."""
    if n <= 0:
        typer.secho("chapter number required (e.g. `epubgen amend remove . 5`)",
                    fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER)
    resolved = _resolve_resume_workdir(workdir)
    if resolved is None:
        raise typer.Exit(EXIT_USER)
    from epubgen import amend as amend_mod

    def _do() -> Path | None:
        outline, _ = amend_mod.load_workdir(resolved)
        new_outline = amend_mod.remove_chapter(resolved, outline, n)
        amend_mod.save(resolved, new_outline)
        typer.secho(
            f"✓ removed chapter {n}; {len(new_outline.chapters)} chapters remain",
            fg=typer.colors.GREEN, err=True,
        )
        if rebuild:
            from epubgen.amend_pipeline import rebuild as rebuild_fn
            return rebuild_fn(resolved, out=out)
        return None

    _amend_run(_do)


@amend_app.command("reorder")
def amend_reorder(
    workdir: Annotated[Path | None, typer.Argument()] = None,
    frm: Annotated[int, typer.Argument(metavar="FROM", help="Current chapter number")] = 0,
    to: Annotated[int, typer.Argument(help="Target position")] = 0,
    rebuild: Annotated[bool, typer.Option("--rebuild/--no-rebuild")] = True,
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
) -> None:
    """Move a chapter to a new position."""
    if frm <= 0 or to <= 0:
        typer.secho("FROM and TO required (e.g. `epubgen amend reorder . 5 2`)",
                    fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER)
    resolved = _resolve_resume_workdir(workdir)
    if resolved is None:
        raise typer.Exit(EXIT_USER)
    from epubgen import amend as amend_mod

    def _do() -> Path | None:
        outline, _ = amend_mod.load_workdir(resolved)
        new_outline = amend_mod.reorder_chapter(resolved, outline, frm, to)
        amend_mod.save(resolved, new_outline)
        typer.secho(f"✓ moved chapter {frm} → position {to}",
                    fg=typer.colors.GREEN, err=True)
        if rebuild:
            from epubgen.amend_pipeline import rebuild as rebuild_fn
            return rebuild_fn(resolved, out=out)
        return None

    _amend_run(_do)


@amend_app.command("edit")
def amend_edit(
    workdir: Annotated[Path | None, typer.Argument()] = None,
    n: Annotated[int, typer.Argument(help="Chapter number to edit")] = 0,
    rebuild: Annotated[bool, typer.Option("--rebuild/--no-rebuild")] = True,
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
) -> None:
    """Open a chapter in $EDITOR. After save, optionally reassemble."""
    if n <= 0:
        typer.secho("chapter number required", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER)
    resolved = _resolve_resume_workdir(workdir)
    if resolved is None:
        raise typer.Exit(EXIT_USER)
    import os
    import subprocess

    from epubgen.workdir import chapter_path as ch_path

    path = ch_path(resolved, n)
    if not path.exists():
        typer.secho(f"chapter file not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER)
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    rc = subprocess.run([editor, str(path)]).returncode
    if rc != 0:
        typer.secho(f"editor exited {rc}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_USER)

    def _do() -> Path | None:
        if rebuild:
            from epubgen.amend_pipeline import rebuild as rebuild_fn
            return rebuild_fn(resolved, out=out)
        return None

    _amend_run(_do)


@amend_app.command("revise")
def amend_revise(
    workdir: Annotated[Path | None, typer.Argument()] = None,
    n: Annotated[int, typer.Argument(help="Chapter number to revise")] = 0,
    instruction: Annotated[
        str | None,
        typer.Option(
            "--instruction", "-i",
            help="What to change. Examples: "
            "'add a section on retries', 'tighten section 2', "
            "'fix the example that calls os.fork on Windows'.",
        ),
    ] = None,
    rebuild: Annotated[bool, typer.Option("--rebuild/--no-rebuild")] = True,
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Modify an existing chapter according to a freeform instruction."""
    if n <= 0:
        typer.secho("chapter number required", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER)
    if not instruction:
        typer.secho("--instruction is required", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER)
    configure_logging(verbose=verbose, log_file=None)
    _preflight()  # this op calls the API
    resolved = _resolve_resume_workdir(workdir)
    if resolved is None:
        raise typer.Exit(EXIT_USER)
    from epubgen.amend_pipeline import revise

    _amend_run(revise, resolved, n, instruction, out=out, rebuild_after=rebuild)


@amend_app.command("recover")
def amend_recover(
    workdir: Annotated[Path | None, typer.Argument()] = None,
    cover_prompt: Annotated[str | None, typer.Option("--cover-prompt")] = None,
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
) -> None:
    """Regenerate the cover and reassemble."""
    _preflight()  # uses OPENAI_API_KEY; rebuild may regen
    resolved = _resolve_resume_workdir(workdir)
    if resolved is None:
        raise typer.Exit(EXIT_USER)
    from epubgen.amend_pipeline import rebuild

    if cover_prompt:
        # Persist as the cover_prompt for this rebuild via a side-channel:
        # update frozen options so future rebuilds use it too.
        from epubgen import amend as amend_mod

        outline, frozen = amend_mod.load_workdir(resolved)
        frozen["cover_prompt"] = cover_prompt
        amend_mod.save(resolved, outline, frozen=frozen)
    _amend_run(rebuild, resolved, out=out, regen_cover=True)


@styles_app.command("list")
def styles_list() -> None:
    for name, desc in list_all_styles():
        typer.echo(f"{name:<18}{desc}")


@styles_app.command("show")
def styles_show(name: str) -> None:
    style = load_style(name)
    typer.echo(style.guide)


def _version_callback(value: bool) -> None:
    if value:
        from epubgen import __version__

        typer.echo(f"epubgen {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    log: Annotated[bool, typer.Option("--log")] = False,
    log_file: Annotated[Path | None, typer.Option("--log-file")] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version", "-V", callback=_version_callback, is_eager=True, help="Print version"
        ),
    ] = False,
) -> None:
    if ctx.invoked_subcommand is not None:
        if ctx.invoked_subcommand not in _PREFLIGHT_SKIP:
            _preflight()
        return
    if not sys.stdin.isatty():
        typer.echo(ctx.get_help())
        raise typer.Exit(EXIT_USER)
    # Bare invocation in a TTY: drop into the wizard.
    _preflight()
    resolved_log = resolve_log_file(log=log, log_file=log_file)
    configure_logging(verbose=verbose, log_file=resolved_log)
    if resolved_log is not None:
        typer.secho(f"📝 logging to {resolved_log}", fg=typer.colors.CYAN, err=True)
    from epubgen.wizard import run_wizard

    opts = run_wizard()
    if opts is None:
        typer.secho("cancelled", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_USER)
    _run(opts)


if __name__ == "__main__":
    app()
