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
    try:
        out = pipeline.run(opts)
        typer.secho(f"✓ wrote {out}", fg=typer.colors.GREEN, err=True)
    except ConfigError as e:
        typer.secho(f"config: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_USER) from e
    except OutlineError as e:
        typer.secho(f"outline: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_OUTLINE) from e
    except ApiError as e:
        typer.secho(f"api: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_API) from e
    except PandocError as e:
        typer.secho(f"pandoc: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_PANDOC) from e
    except FsError as e:
        typer.secho(f"fs: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(EXIT_FS) from e
    except EpubgenError as e:
        typer.secho(f"error: {e}", fg=typer.colors.RED, err=True)
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
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Generate an EPUB from a topic."""
    out_path = out or Path(f"./{slugify(topic)}.epub")
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
        force=force,
        dry_run=dry_run,
        verbose=verbose,
    )
    if dry_run:
        typer.echo(opts.model_dump_json(indent=2))
        return
    _run(opts)


@app.command()
def wizard() -> None:
    """Interactive prompt-driven generation."""
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
) -> None:
    """Resume an interrupted run from its workdir."""
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
    from epubgen.wizard import run_wizard

    opts = run_wizard()
    if opts is None:
        typer.secho("cancelled", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(EXIT_USER)
    _run(opts)


if __name__ == "__main__":
    app()
