# epubgen

Generate professional EPUB books from a topic + style using the Anthropic API. Resumable, prompt-cached, and ready for Kindle.

```
epubgen generate "Python performance optimization" --style oreilly --out book.epub
epubgen wizard
```

## Features

- **10 publishing-voice styles** — `oreilly`, `manning`, `pragprog`, `nostarch`, `apress`, `for-dummies`, `cheatsheet`, `pocket-reference`, plus `academic` and `penguin-classics` as extras.
- **Interactive wizard** — `questionary` flow that picks a style, brainstorms three title framings (with hint-driven regeneration), drafts a back-cover description, and threads everything into the outline.
- **Rich content** — code (highlighted), tables, math (`$...$` / `$$...$$` → MathML), Mermaid diagrams, Vega-Lite charts, and AI-generated images, all from fenced blocks the model emits.
- **E-reader mode** — `--ereader` (default **on**) tunes for ~6" reflowable screens (Kindle/Kobo/KOReader/Pocketbook): code lines ≤60 chars, monochrome syntax theme, AZW3 output if `kindlepreviewer` is present. Pass `--no-ereader` for tablet/desktop output. The Kindle-specific PNG figure conversion is gone — SVG works on every modern reader.
- **Prompt caching** — style guide, optional source bundle, and outline cached at three `cache_control` breakpoints; per-chapter calls reuse the prefix at ~10% token cost.
- **Source grounding** — pass `--source PATH` (repeatable, accepts files/dirs/globs) to inject reference material into every prompt. Outline scope and chapter facts are tied to your sources instead of model priors. PDFs/.docx/.epub/.html convert via pandoc; plain `.md`/`.txt` read directly.
- **Resumable** — chapters written atomically to `<out>.work/ch-NN.md`; re-running picks up where it left off. `options.json` is frozen on first run; mismatches refuse to resume unless `--force`.
- **Concurrent** — async chapter generation with a small pool (default 3).
- **Cover** — SVG fallback (always works) or OpenAI gpt-image-1 if `OPENAI_API_KEY` is set.
- **Doctor preflight** — checks every dependency at startup; clear errors instead of mid-pipeline explosions.
- **Structured logging** — `--verbose` and `--log[--log-file PATH]` capture full traces and per-chapter timings/token usage.

## Install

```bash
git clone https://github.com/mjbeswick/epubgen
cd epubgen
uv tool install --editable .          # global `epubgen` command, edits picked up live
brew install pandoc                    # required
```

Set `ANTHROPIC_API_KEY` in your env. Run `epubgen doctor` to verify.

### Optional dependencies

| Tool | Purpose | Install |
|---|---|---|
| `pandoc` | EPUB assembly | `brew install pandoc` (required) |
| `mmdc` | Render Mermaid diagrams | `npm i -g @mermaid-js/mermaid-cli` |
| `kindlepreviewer` | Emit `.azw3` alongside `.epub` | [Amazon Kindle Previewer](https://www.amazon.com/Kindle-Previewer/b?node=21381691011) |
| `OPENAI_API_KEY` | Cover + content images via gpt-image-1 | env var |

`vl-convert` (Vega-Lite charts) is bundled — no install needed.

If anything is missing, `epubgen doctor` shows the status:

```
✓ python ≥ 3.12        3.14.4
✓ ANTHROPIC_API_KEY    sk-ant-…abcd
✓ pandoc               /opt/homebrew/bin/pandoc
! mmdc (mermaid-cli)   not on PATH (optional)
✓ vl-convert (charts)  available
! kindlepreviewer      not on PATH (optional; needed only for .azw3)
✓ OPENAI_API_KEY       set
```

## Usage

### Subcommands

```
epubgen generate <topic>     Non-interactive generation
epubgen wizard               Interactive prompt-driven flow
epubgen styles list|show     Inspect style presets
epubgen resume <workdir>     Resume an interrupted run
epubgen amend <op> <wd>      Edit an existing book (see Amending)
epubgen doctor               Preflight dependency check
```

### `generate` flags

```
-s, --style TEXT           Style preset (default: oreilly)
-o, --out PATH             Output .epub path (default: ./<slug>.epub)
-w, --workdir PATH         Work dir (default: <out>.work)
-c, --chapters INTEGER     Target chapter count (model decides if unset)
-W, --words INTEGER        Target words per chapter (default: 3000)
-m, --model TEXT           Anthropic model (default: claude-opus-4-7)
    --concurrency INTEGER  Parallel chapters (default: 3)
    --ereader/--no-ereader Tune for ~6" e-readers (default: on). --kindle is an alias.
    --no-cover             Skip cover generation
    --no-diagrams          Skip all figure rendering (mermaid+chart+image)
    --no-images            Skip generated images only (keep mermaid/charts)
    --cover-prompt TEXT    Override cover image prompt
    --source PATH          Reference source (file/dir/glob). Repeatable.
                           Grounds outline + chapters via the prompt cache.
                           Reads .md/.txt/.html/.docx/.epub/.pdf and friends.
    --author TEXT          Author metadata (default: epubgen)
    --refine               Interactively refine title/subtitle (TTY required)
    --force                Override options.json mismatch on resume
    --dry-run              Print resolved options and exit
-v, --verbose              Debug logging to stderr
    --log                  Write log to ./epubgen-<timestamp>.log
    --log-file PATH        Write log to specific path
```

### Wizard flow

The wizard chains style-aware steps so the model has full context for each:

1. **Topic** — free text from you.
2. **Style** — picker showing the 8 default styles with one-line voice samples.
3. **Title refinement** — the model proposes three distinct framings (title, subtitle, angle) in the chosen voice. You can pick one, edit any of them, regenerate, regenerate with a hint (`"punchier"`, `"focus on async"`), or skip.
4. **Description** — back-cover description drafted in the same voice. Same accept / edit / regenerate / hint loop.
5. **Length** — short (6 ch / 2500 wpc), standard (10/3000), long (16/3500).
6. **Kindle target** — yes/no.
7. **Output path** — derived from the chosen title.

The wizard builds the same `Options` object the `generate` subcommand takes, so there's a single downstream code path.

## Content types

The model populates a structured outline per chapter, then writes each chapter referring to its beats. Beyond prose and code, chapters can contain:

| Kind | Source markup | Rendered via | Output |
|---|---|---|---|
| Code | <code>```python … ```</code> | pandoc + skylighting | Inline highlighted blocks |
| Tables | GitHub-style markdown | pandoc | Native EPUB tables |
| Math | `$inline$`, `$$display$$` | pandoc `--mathml` | Native MathML |
| Diagrams | <code>```mermaid … ```</code> | `mmdc` | SVG |
| Charts | <code>```vegalite … ```</code> | `vl-convert` | SVG |
| Images | <code>```image … ```</code> | OpenAI gpt-image-1 | PNG, ~$0.04 each |

Each renderer fails open: missing dependencies leave the fenced block as code, still readable in the EPUB.

## Styles

Default presets (under `src/epubgen/styles/`):

| Name | Voice |
|---|---|
| `oreilly` | Pragmatic, code-forward — assumes intermediate readers |
| `manning` | "In Action" — drops you into a scenario before the theory |
| `pragprog` | Opinionated, tip-driven, peer-to-peer |
| `nostarch` | Project-driven; the book is one guided build |
| `apress` | Reference-thorough; closer to a manual |
| `for-dummies` | Friendly, icon-heavy, zero assumed knowledge |
| `cheatsheet` | Telegraphic cards — scan, don't read. Tables and snippets |
| `pocket-reference` | Manual entries: synopsis, params, example, see-also |

Extras (loadable by name): `academic`, `penguin-classics`.

Adding a new style is two files: `src/epubgen/styles/<name>.md` (with `## Voice`, `## Structure`, `## Formatting`, `## Length` sections) and `src/epubgen/styles/<name>.css`.

## How it works

1. **Outline** — one Anthropic call with a `cache_control` breakpoint on the style guide. Model returns structured JSON via tool-use; pydantic validates with one repair retry.
2. **Chapters** — async pool (default concurrency 3). Each call has two `cache_control` breakpoints: style guide (stable across all books in this style) and outline JSON (stable within this run). Only the user message ("write chapter N") is volatile per call.
3. **Figures** — post-pass scans every chapter for fenced `mermaid` / `vegalite` / `image` blocks, renders each, rewrites the markdown to image references.
4. **Cover** — OpenAI gpt-image-1 if `OPENAI_API_KEY` is set, otherwise a deterministic per-style SVG.
5. **Assemble** — pandoc converts the markdown chapters into a single EPUB3 with TOC, per-style CSS, embedded cover, native MathML.
6. **Optional AZW3** — if `--ereader` (default on) and `kindlepreviewer` is on PATH, also emits `.azw3` alongside.

## Resuming

If a run dies mid-way (interrupted, transient API error, etc.), just rerun with the same args. Each chapter is written atomically to `ch-NN.md`; existing files are skipped. The `options.json` freeze guards against accidental mismatches — pass `--force` to override.

```
epubgen resume <out>.work/      # picks up where it left off
```

If the API errors out mid-run (rate limit, usage cap, credit balance), epubgen prints a one-line cause + hint instead of a traceback. Already-generated chapters are saved; rerun `epubgen resume` once the underlying issue is cleared.

## Amending

Once a book exists you can edit its workdir in place. Operations that don't call the model (everything except `rewrite` / `insert`) are essentially free.

```
epubgen amend rebuild  <wd>                 # re-render figures + reassemble
epubgen amend retitle  <wd> --title "..." [--subtitle "..." | --clear-subtitle]
epubgen amend remove   <wd> N               # drop chapter N, renumber
epubgen amend reorder  <wd> FROM TO         # move chapter to new position
epubgen amend edit     <wd> N               # open ch-NN.md in $EDITOR
epubgen amend revise   <wd> N -i "..."      # model-driven edit (add / tighten / fix)
epubgen amend recover  <wd> [--cover-prompt "..."]   # regen cover
```

`<wd>` accepts the same flexible argument as `resume` — a workdir path, an `.epub` path (workdir derived as `<epub>.work`), or a directory to search interactively. Mutating commands take `--no-rebuild` to skip reassembly when chaining edits, and `--out PATH` to override the output epub. Destructive ops back up the prior file to `<wd>/.archive/`.

`revise` is the workhorse for content changes: it sends the current chapter plus your instruction to the model and writes the revised chapter back. Examples:

```
epubgen amend revise mybook.epub 5 -i "add a section on connection retries at the end"
epubgen amend revise mybook.epub 3 -i "tighten section 2 to half its length"
epubgen amend revise mybook.epub 7 -i "fix the example — os.fork doesn't exist on Windows"
```

The cached prefix (style guide + sources + outline) is reused across calls in the same run, so revisions are cheap.

## Debugging

```
epubgen generate "..." -v --log         # stderr DEBUG + epubgen-<ts>.log file
epubgen doctor                          # check dependencies
```

Logs include the request shape, per-chapter timing, cache hit/miss counts, and full tracebacks for any failure.

## Development

```bash
uv sync --extra dev          # dev dependencies
uv run pytest                # 60 tests, ~0.5s
uv run ruff check src tests  # lint
```

## License

MIT
