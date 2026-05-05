from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from epubgen import pipeline
from epubgen.errors import (
    ApiError,
    ConfigError,
    EpubgenError,
    FsError,
    OutlineError,
    PandocError,
)
from epubgen.logsetup import configure_logging, get_logger
from epubgen.schema import Options
from epubgen.styles import list_all_styles, load_style
from epubgen.workdir import default_workdir, slugify

app = typer.Typer(
    add_completion=False,
    help="Generate EPUB books from a topic + style via the Anthropic API.",
    no_args_is_help=False,
)
styles_app = typer.Typer(help="Inspect available style presets.")
app.add_typer(styles_app, name="styles")

EXIT_USER = 1
EXIT_API = 2
EXIT_PANDOC = 3
EXIT_FS = 4
EXIT_OUTLINE = 5


def _run(opts: Options) -> None:
    log = get_logger("cli")
    log.debug("resolved options: %s", opts.model_dump_json())
    try:
        out = pipeline.run(opts)
        typer.secho(f"✓ wrote {out}", fg=typer.colors.GREEN, err=True)
    except ConfigError as e:
        log.error("config error: %s", e, exc_info=True)
        typer.secho(f"config: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER) from e
    except OutlineError as e:
        log.error("outline error: %s", e, exc_info=True)
        typer.secho(f"outline: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_OUTLINE) from e
    except ApiError as e:
        log.error("api error: %s", e, exc_info=True)
        typer.secho(f"api: {e}", fg=typer.colors.RED, err=True)
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
    words: Annotated[int, typer.Option("--words", "-W", help="Target words per chapter")] = 3000,
    model: Annotated[str, typer.Option("--model", "-m")] = "claude-opus-4-7",
    concurrency: Annotated[int, typer.Option("--concurrency")] = 3,
    kindle: Annotated[
        bool, typer.Option("--kindle", help="Tune for Kindle; emit .azw3 if available")
    ] = False,
    no_cover: Annotated[bool, typer.Option("--no-cover", help="Skip cover generation")] = False,
    cover_prompt: Annotated[str | None, typer.Option("--cover-prompt")] = None,
    author: Annotated[str, typer.Option("--author")] = "epubgen",
    force: Annotated[bool, typer.Option("--force", help="Override options.json mismatch")] = False,
    refine: Annotated[
        bool, typer.Option("--refine", help="Interactively refine title/subtitle (TTY required)")
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    log_file: Annotated[
        Path | None, typer.Option("--log-file", help="Write a debug log to this file")
    ] = None,
) -> None:
    """Generate an EPUB from a topic."""
    configure_logging(verbose=verbose, log_file=log_file)
    get_logger("cli").info("epubgen generate: topic=%r style=%s", topic, style)
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
        kindle=kindle,
        no_cover=no_cover,
        cover_prompt=cover_prompt,
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
    _run(opts)


@app.command()
def wizard(
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    log_file: Annotated[Path | None, typer.Option("--log-file")] = None,
) -> None:
    """Interactive prompt-driven generation."""
    configure_logging(verbose=verbose, log_file=log_file)
    from epubgen.wizard import run_wizard

    opts = run_wizard()
    if opts is None:
        typer.secho("cancelled", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_USER)
    _run(opts)


@app.command()
def resume(
    workdir: Annotated[Path, typer.Argument(help="Work dir of an interrupted run")],
    out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
    log_file: Annotated[Path | None, typer.Option("--log-file")] = None,
) -> None:
    """Resume an interrupted run from its workdir."""
    configure_logging(verbose=verbose, log_file=log_file)
    import json

    options_path = workdir / "options.json"
    if not options_path.exists():
        typer.secho(f"no options.json in {workdir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER)
    frozen = json.loads(options_path.read_text())
    out_path = out or Path(f"./{slugify(frozen['topic'])}.epub")
    opts = Options(out=out_path, workdir=workdir, **frozen)
    _run(opts)


@styles_app.command("list")
def styles_list() -> None:
    for name, desc in list_all_styles():
        typer.echo(f"{name:<18}{desc}")


@styles_app.command("show")
def styles_show(name: str) -> None:
    style = load_style(name)
    typer.echo(style.guide)


@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if not sys.stdin.isatty():
        typer.echo(ctx.get_help())
        raise typer.Exit(EXIT_USER)
    # Bare invocation in a TTY: drop into the wizard.
    configure_logging(verbose=False, log_file=None)
    from epubgen.wizard import run_wizard

    opts = run_wizard()
    if opts is None:
        typer.secho("cancelled", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_USER)
    _run(opts)


if __name__ == "__main__":
    app()
