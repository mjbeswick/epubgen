# epubgen

Generate professional EPUB books from a topic + style using the Anthropic API.

```
epubgen generate "Python performance optimization" --style oreilly --out book.epub
epubgen generate "..." --style oreilly --kindle --out book.epub
epubgen wizard
```

## Install

```
uv tool install .          # or: uv sync && uv run epubgen ...
brew install pandoc        # required
```

Set `ANTHROPIC_API_KEY` in your env.

## Styles

- `oreilly` — pragmatic, code-forward
- `manning` — In Action, scenario-driven
- `pragprog` — opinionated, tip-driven
- `nostarch` — project-driven
- `apress` — reference-leaning
- `for-dummies` — friendly, icon-heavy

Extras (loadable by name): `academic`, `penguin-classics`.

## Kindle

`--kindle` constrains code-line width, switches highlight style to a grayscale-legible theme, and emits `.azw3` alongside if `kindlepreviewer` is on PATH.

## Resumable

Each chapter is written atomically to `<out>.work/ch-NN.md`. Re-running picks up missing chapters. `options.json` is frozen on first run; mismatches refuse to resume unless `--force`.

## Plan

See `PLAN.md` for the architecture and tradeoffs.
