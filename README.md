# epubgen

Generate professional EPUB books from a topic + style using your choice of LLM provider (Anthropic, OpenAI, Google Gemini, DeepSeek, or any model via OpenRouter). Resumable, prompt-cached, and ready for Kindle.

```
epubgen generate "Python performance optimization" --style oreilly --out book.epub
epubgen wizard
```

## Features

- **10 publishing-voice styles** — `oreilly`, `manning`, `pragprog`, `nostarch`, `apress`, `for-dummies`, `cheatsheet`, `pocket-reference`, plus `academic` and `penguin-classics` as extras.
- **Interactive wizard** — `questionary` flow that picks a style, brainstorms three title framings (with hint-driven regeneration), drafts a back-cover description, and threads everything into the outline.
- **Rich content** — code (highlighted), tables, math (`$...$` / `$$...$$` → MathML), Mermaid diagrams, Vega-Lite charts, and AI-generated images, all from fenced blocks the model emits.
- **E-reader mode** — `--ereader` (default **on**) tunes for ~6" reflowable screens (Kindle/Kobo/KOReader/Pocketbook): code lines ≤60 chars, monochrome syntax theme, AZW3 output if `kindlepreviewer` is present. Pass `--no-ereader` for tablet/desktop output. The Kindle-specific PNG figure conversion is gone — SVG works on every modern reader.
- **Prompt caching** — style guide, optional source bundle, and outline cached at three breakpoints. Anthropic uses explicit `cache_control`; OpenAI/DeepSeek use automatic prefix caching; Gemini uses explicit `caches.create` for the chapter hot path. Per-chapter calls reuse the prefix at ~10% token cost.
- **Source grounding** — pass `--source PATH` (repeatable, accepts files/dirs/globs) to inject reference material into every prompt. Outline scope and chapter facts are tied to your sources instead of model priors. PDFs/.docx/.epub/.html convert via pandoc; plain `.md`/`.txt` read directly.
- **Resumable** — chapters written atomically to `<out>.work/ch-NN.md`; re-running picks up where it left off. `options.json` is frozen on first run; mismatches refuse to resume unless `--force`.
- **Concurrent** — async chapter generation with a small pool (default 3).
- **Cover** — Style-matched full-bleed covers (1600×2400px for Kindle) with AI-generated illustrations via Google Gemini. Graceful fallback to SVG if APIs unavailable. Override with `--cover-prompt` or skip with `--no-cover`.
- **Shell completions** — Bash, Zsh, and Fish completions for all commands, flags, and choices (styles, models, amend operations). Install with `./scripts/install-completions.sh`.
- **Doctor preflight** — checks every dependency at startup; clear errors instead of mid-pipeline explosions.
- **Structured logging** — `--verbose` and `--log[--log-file PATH]` capture full traces and per-chapter timings/token usage.

## Install

```bash
git clone https://github.com/mjbeswick/epubgen
cd epubgen
uv tool install --editable .          # global `epubgen` command, edits picked up live
brew install pandoc                    # required
```

Set at least one provider API key in your env. Run `epubgen doctor` to verify.

| Provider | Env var | Notes |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | Native client; full prompt caching via `cache_control`. Default. |
| OpenAI | `OPENAI_API_KEY` | Auto prefix caching. Also used for cover images. |
| Google Gemini | `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) | Explicit context caching for chapter hot path. |
| DeepSeek | `DEEPSEEK_API_KEY` | OpenAI-compat; auto prefix caching. Cheapest credible option. |
| OpenRouter | `OPENROUTER_API_KEY` | Catch-all gateway — pass any `vendor/model` tail. |

Pick a model with `--model <provider>/<model>` (or persisted via wizard). Legacy bare `claude-*` ids still work.

### Optional dependencies

| Tool | Purpose | Install |
|---|---|---|
| `pandoc` | EPUB assembly | `brew install pandoc` (required) |
| `mmdc` | Render Mermaid diagrams | `npm i -g @mermaid-js/mermaid-cli` |
| `kindlepreviewer` | Emit `.azw3` alongside `.epub` | [Amazon Kindle Previewer](https://www.amazon.com/Kindle-Previewer/b?node=21381691011) |
| `GOOGLE_API_KEY` | Cover illustrations via Gemini 2.0 | env var (for enhanced cover generation) |
| `OPENAI_API_KEY` | Content images via gpt-image-1 | env var (for `image` fenced blocks) |

`vl-convert` (Vega-Lite charts) is bundled — no install needed. Covers gracefully degrade to SVG-only if Gemini API is unavailable.

If anything is missing, `epubgen doctor` shows the status:

```
✓ python ≥ 3.12        3.14.4
✓ LLM provider         3 key(s) configured: ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPSEEK_API_KEY
✓ ANTHROPIC_API_KEY    sk-ant-…abcd
✓ OPENAI_API_KEY       sk-…wxyz
! GOOGLE_API_KEY       not set (optional — Google Gemini provider)
! GEMINI_API_KEY       not set (optional — Google Gemini (alt env))
✓ DEEPSEEK_API_KEY     sk-…1234
! OPENROUTER_API_KEY   not set (optional — OpenRouter gateway)
✓ pandoc               /opt/homebrew/bin/pandoc
! mmdc (mermaid-cli)   not on PATH (optional)
✓ vl-convert (charts)  available
! kindlepreviewer      not on PATH (optional; needed only for .azw3)
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
-m, --model TEXT           Model id `provider/model` (default: persisted, else
                           `anthropic/claude-sonnet-4-6`). Legacy bare `claude-*` accepted.
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

## Covers

Every book gets a professional cover, styled to match the chosen preset. The cover is 1600×2400px (full-bleed Kindle format) with:

- **AI illustration** — Topic-aware image generated via Google Gemini, styled to match the book's voice (e.g., scientific engravings for O'Reilly, friendly icons for For Dummies)
- **Branding** — Each style has a distinct template: header color, typography, layout
- **Fallbacks** — If Gemini API is unavailable, the cover degrades gracefully to a clean SVG layout (still branded, no illustration)

**Disable or customize:**

```bash
epubgen generate "Topic" --style oreilly --out book.epub               # auto-generated cover
epubgen generate "Topic" --style oreilly --no-cover --out book.epub    # skip cover entirely
epubgen generate "Topic" --style oreilly \
  --cover-prompt "A futuristic city at sunset" \
  --out book.epub                                                      # custom illustration prompt
```

**Regenerate an existing cover:**

```bash
epubgen amend recover mybook.epub                # regenerate with default prompt
epubgen amend recover mybook.epub --cover-prompt "A mountain landscape"  # custom prompt
```

## How it works

1. **Outline** — one model call with a cache breakpoint on the style guide. Model returns structured JSON via tool-use; pydantic validates with one repair retry.
2. **Chapters** — async pool (default concurrency 3). On Anthropic, each call has two `cache_control` breakpoints (style guide stable across all books, outline JSON stable within this run). On OpenAI/DeepSeek, automatic prefix caching does the equivalent. On Gemini, an explicit `caches.create` is used for the chapter hot path (falls back gracefully if the prefix is below the model's minimum cacheable size). Only the user message ("write chapter N") is volatile per call.
3. **Figures** — post-pass scans every chapter for fenced `mermaid` / `vegalite` / `image` blocks, renders each, rewrites the markdown to image references.
4. **Cover** — Style-specific SVG template with topic-aware Gemini-generated illustration (1024×1024px, embedded as base64). Falls back to SVG-only layout if Gemini unavailable. Final cover is rasterized to 1600×2400px PNG for full-bleed Kindle display.
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
