# epubgen — Implementation Plan

Standalone Python CLI: topic + style → `.epub` (optionally `.azw3` for Kindle). Direct Anthropic SDK, pandoc assembly, prompt caching, resumable on disk.

## Goal

```
epubgen generate "Python performance optimization" --style oreilly --out book.epub
epubgen generate "..." --style oreilly --kindle --out book.epub
epubgen wizard
```

Produces a valid EPUB3 with cover, TOC, chapters, metadata, style-matched CSS. Resumable: re-run picks up missing chapters from the work dir. With `--kindle`, prompts and CSS tune for Kindle reflow; `.azw3` is produced alongside if `kindlepreviewer` is on PATH.

---

## Stack

- **Python 3.12+**
- **uv** for env + deps; `pyproject.toml` is source of truth
- **ruff** for lint + format
- **pytest** + **pytest-asyncio** for tests
- **anthropic** Python SDK (async client) — model `claude-opus-4-7`
- **typer** for CLI subcommands; **questionary** for the interactive wizard; **rich** for progress
- **pydantic** v2 for the outline schema (replaces Zod)
- **pandoc** (subprocess) for EPUB assembly; **ebooklib** as a documented pure-Python fallback (worse output, kept off the hot path)
- **httpx** comes via the SDK; SDK retries handle transient errors
- Concurrency: `asyncio.Semaphore(3)` over async SDK calls

Rationale: every choice is the obvious one for a Python CLI in 2026. No frameworks beyond CLI ergonomics. No DI.

---

## Repo layout

Small, focused modules. `src/` layout so installs are clean and tests run against the installed package.

```
epubgen/
  pyproject.toml
  README.md
  PLAN.md
  src/epubgen/
    __init__.py
    __main__.py                  # python -m epubgen → cli.app()
    cli.py                       # typer app; subcommands: generate, wizard, styles, resume
    wizard.py                    # questionary flow; builds the same options object generate uses
    pipeline.py                  # orchestrator: outline → chapters (pool) → cover → assemble
    config.py                    # Options model (pydantic), env load (ANTHROPIC_API_KEY), defaults
    anthropic_client.py          # async client factory, model constant, error classification
    prompts/
      __init__.py
      outline.py                 # build_outline_prompt(style, topic, opts) → system blocks + user
      chapter.py                 # build_chapter_prompt(style, outline, n, kindle) → cached system + user
      cover.py                   # build_cover_prompt(style, topic, outline)
    outline.py                   # generate_outline(): SDK call + pydantic validation + one repair retry
    chapters.py                  # generate_chapter(n): SDK call, atomic write, semaphore-gated pool
    cover.py                     # generate_cover(): image API or SVG fallback → cover.png|svg
    assemble.py                  # pandoc subprocess, metadata.yaml, css selection, optional azw3
    styles/
      __init__.py                # load_style(name), list_styles()
      oreilly.md
      oreilly.css
      manning.md
      manning.css
      pragprog.md
      pragprog.css
      nostarch.md
      nostarch.css
      apress.md
      apress.css
      for-dummies.md
      for-dummies.css
      extras/
        academic.md
        academic.css
        penguin-classics.md
        penguin-classics.css
    workdir.py                   # resolve work dir, atomic writes, options.json freeze/compare
    progress.py                  # rich Progress wrapper; plain logger fallback when not a TTY
    schema.py                    # pydantic models: Outline, Chapter, Beat, Options
    errors.py                    # ApiError, PandocError, FsError, OutlineError, CoverError
  tests/
    test_prompts.py              # cache breakpoint placement, prompt assembly determinism
    test_outline.py              # JSON parse + pydantic validation + repair path (mocked client)
    test_styles.py               # all default styles load; CSS exists; required sections present
    test_assemble.py             # pandoc arg construction + metadata.yaml shape (no shell-out)
    test_workdir.py              # atomic writes, options.json mismatch detection
    test_integration.py          # mocked async client end-to-end → real pandoc → valid epub
    fixtures/
      mock_outline.json
      mock_chapter.md
      fake_anthropic.py          # async fake matching the SDK surface we use
```

Rationale: `pipeline.py` is the only orchestrator. `wizard.py` and `cli.py` both produce the same `Options` and call `pipeline.run(opts)` — single downstream code path. Styles are data, not code; default-shipped under `styles/`, opinionated extras under `styles/extras/`.

---

## Prompt caching layout

Caching is the difference between affordable and not. With N chapters, naive cost is N × (style + outline) input tokens. With caching, that prefix reads at ~10% rate after the first call.

Per-call structure for **chapter generation** (the hot path):

```python
await client.messages.create(
    model="claude-opus-4-7",
    system=[
        {"type": "text", "text": STYLE_GUIDE_TEXT,
         "cache_control": {"type": "ephemeral"}},   # breakpoint 1: stable across runs/books
        {"type": "text", "text": OUTLINE_JSON_TEXT,
         "cache_control": {"type": "ephemeral"}},   # breakpoint 2: stable within a book run
    ],
    messages=[
        {"role": "user",
         "content": f'Write chapter {n}: "{title}". Beats:\n{beats}\nCode examples:\n{code_examples}'}
    ],
    max_tokens=8000,
)
```

Two breakpoints, ordered stable→volatile:

1. **Style guide** — same for every book using that style. SDK uses content hash, so identical text re-hits across runs and across books.
2. **Full outline JSON** — stable within one book run, volatile across books.

The user message is the only volatile per-chapter content (~150 tokens including the code-example beats). Output is the chapter.

Outline generation is one call — cache the style guide only (breakpoint 1). Cover prompt is one call — no caching.

5-minute TTL is fine: the chapter pool keeps calls dense. A resumed run hours later pays the miss on the first chapter, then re-warms. Acceptable.

**Do not** put the topic in cached blocks — it changes per run and would invalidate the style cache. Topic lives in the user message of outline gen and is implicit in the outline JSON for chapter gen.

Determinism: prompt builder canonicalizes the outline JSON (sorted keys, fixed whitespace) so the cache key is stable across runs. Snapshot test on the assembled prompt.

Asserting cache works: integration smoke test inspects `usage.cache_creation_input_tokens` / `cache_read_input_tokens` on the response and fails if reads are zero after the first chapter.

---

## Outline schema (pydantic v2)

```python
from pydantic import BaseModel, Field

class Beat(BaseModel):
    summary: str = Field(min_length=10)
    word_target: int | None = Field(default=None, gt=0)

class Chapter(BaseModel):
    number: int = Field(gt=0)
    title: str = Field(min_length=1)
    synopsis: str = Field(min_length=20)
    beats: list[Beat] = Field(min_length=2, max_length=12)
    code_examples: list[str] = Field(default_factory=list, max_length=20)
    word_target: int = Field(gt=0)

class Outline(BaseModel):
    title: str = Field(min_length=1)
    subtitle: str | None = None
    author: str = "epubgen"
    topic: str
    style: str
    chapters: list[Chapter] = Field(min_length=3, max_length=40)
```

`code_examples` is a list of short natural-language descriptions ("a generator that streams CSV rows", "a contextmanager wrapping a Postgres transaction"). The chapter prompt instructs the model to produce runnable, self-contained snippets matching those beats, in fenced code blocks with a language tag. With `--kindle`, the prompt additionally constrains code lines to ≤60 chars (Kindle reflow mangles longer lines).

Validation flow: model returns JSON via a `tool_use` block (single `emit_outline` tool — more reliable than asking for raw JSON). Parse → `Outline.model_validate()`. On `ValidationError`, **one** repair call appending the error; second failure raises `OutlineError`. No silent fallbacks.

Persisted to `<workdir>/outline.json`; resumed runs skip outline regen.

---

## Pipeline

```
1. resolve options + load style                          (sync, <1ms)
2. ensure workdir exists; freeze/compare options.json
3. if outline.json exists → load + validate; else generate_outline → write
4. fan out chapters with asyncio.Semaphore(3):
     for each ch: if <workdir>/ch-NN.md exists → skip
                  else generate_chapter(n) → atomic write
5. generate_cover if no cover.* present                  (best-effort; SVG fallback never fails)
6. assemble: write metadata.yaml, copy css, run pandoc → out.epub
7. if --kindle and kindlepreviewer on PATH → also produce out.azw3
8. (optional) epubcheck if installed — warn-only
```

Concurrency: a single `asyncio.Semaphore(3)` guards `client.messages.create` calls. The SDK's built-in retries handle 429 / 5xx / network transients (configured via `max_retries=5`). Anything else (400, auth) raises immediately — let it propagate to the CLI top level.

---

## Resumability

Work dir layout (default: `<out>.work/` next to `--out`, or `--workdir`):

```
<workdir>/
  options.json     # frozen options for this run; mismatch on resume → error unless --force
  outline.json
  ch-01.md
  ch-02.md
  ...
  cover.png|svg
  assembled.log
```

`options.json` contains topic, style, model, chapter count, word targets, kindle flag. On resume, mismatched fields → fail loud unless `--force`. Granularity is the chapter file; atomic writes (`write to ch-NN.md.tmp`, `os.fsync`, `os.replace`) prevent half-written files from being mistaken for done.

---

## CLI UX

`typer` subcommands. Bare `epubgen` with a TTY → wizard. Non-TTY without args → usage error.

```
$ epubgen --help

Usage: epubgen [OPTIONS] COMMAND [ARGS]...

Commands:
  generate   Generate an EPUB from a topic
  wizard     Interactive prompt-driven generation
  styles     Inspect available style presets
  resume     Resume an interrupted run from its workdir

$ epubgen generate --help

Usage: epubgen generate [OPTIONS] TOPIC

Arguments:
  TOPIC                       Book topic [required]

Options:
  -s, --style TEXT            Style preset [default: oreilly]
  -o, --out PATH              Output .epub path [default: ./<slug>.epub]
  -w, --workdir PATH          Work dir [default: <out>.work]
  -c, --chapters INTEGER      Target chapter count (model decides if unset)
  -W, --words INTEGER         Target words per chapter [default: 3000]
  -m, --model TEXT            Anthropic model [default: claude-opus-4-7]
      --concurrency INTEGER   Parallel chapters [default: 3]
      --kindle                Tune prompts/CSS for Kindle; also emit .azw3 if kindlepreviewer present
      --no-cover              Skip cover generation
      --cover-prompt TEXT     Override cover image prompt
      --force                 Ignore options.json mismatch on resume
      --dry-run               Print plan + token estimate, do nothing
  -v, --verbose               Debug logging to stderr

$ epubgen styles list
oreilly       O'Reilly technical — pragmatic, code-forward
manning       Manning In Action — scenario-driven, conversational
pragprog      Pragmatic Programmers — opinionated, "Tip N" callouts
nostarch      No Starch — project-driven, builds toward working code
apress        Apress — reference-leaning, thorough
for-dummies   For Dummies — friendly, lots of icons/callouts

(extras loadable by name: academic, penguin-classics)

$ epubgen styles show oreilly
# prints the style markdown

$ epubgen wizard
? Topic: Python performance optimization
? Style: (use arrow keys)
  ❯ oreilly      "Pragmatic, code-forward — assumes intermediate readers."
    manning      "In Action — drops you into a scenario before the theory."
    pragprog     "Opinionated and tip-driven; treats you like a peer."
    nostarch     "Build something. The book is a guided project."
    apress       "Reference-thorough; closer to a manual."
    for-dummies  "Friendly, icon-heavy, zero assumed knowledge."
? Target chapter count: 10
? Words per chapter: 3000
? Optimize for Kindle? No
? Output path: ./python-performance.epub
> Generating outline... ✓ (12.3s)
> Chapters [████░░░░░░] 4/10
```

The wizard builds the same `Options` object `generate` accepts, then calls `pipeline.run(opts)` directly. No duplicated validation.

Progress: rich `Progress` with one task per chapter when on a TTY. Non-TTY: one log line per state transition (`[ch 03] start`, `[ch 03] done 2847w 14.2s`). Final line: epub path + cost estimate.

Exit codes: 0 ok, 1 user error, 2 API error after retries, 3 pandoc error, 4 fs error.

---

## Kindle mode (`--kindle`)

Send-to-Kindle accepts EPUB3 directly, so this is mostly prompt + CSS tuning, not a separate format pipeline.

Effects:

1. **Prompt tuning.** Chapter prompt appends a constraint: "code blocks: lines ≤60 characters; prefer short-line idiomatic style; wrap or refactor long lines rather than truncating." Outline prompt is unchanged.
2. **CSS tuning.** Pandoc `--highlight-style=monochrome` (or `kate`) when `--kindle` is set, so syntax highlighting remains legible on grayscale e-ink. Style CSS may also branch on a `.kindle` body class for spacing/font-size tweaks.
3. **Optional AZW3.** After producing `out.epub`, if `kindlepreviewer` is on PATH, run it to produce `out.azw3` next to it. Detect-and-skip when missing — handled in `assemble.py` (the boundary where subprocess errors live). No hard dependency.

Tradeoffs: long code lines are the single biggest Kindle-readability complaint; constraining at generation time is cheaper than post-processing. Grayscale highlighting matters because most Kindle hardware is e-ink. AZW3 is a nice-to-have — Send-to-Kindle handles EPUB3 fine for most users.

---

## Style presets

Default ship list (under `src/epubgen/styles/`):

- **oreilly** — animal-book voice, sidebars/notes/warnings, dense-but-pragmatic
- **manning** — "In Action" style, scenario-driven, conversational
- **pragprog** — Pragmatic Programmers, opinionated, "Tip N" callouts
- **nostarch** — project-driven, builds toward working code
- **apress** — reference-leaning, thorough, drier
- **for-dummies** — friendly, icons/callouts, zero assumed knowledge

Extras (under `styles/extras/`, loadable by name, not in wizard list):

- **academic**
- **penguin-classics**

Each `<name>.md` has fixed sections so the prompt builder can splice them confidently:

```
# Style: O'Reilly Technical

## Voice
Pragmatic, second-person, code-forward. Assumes intermediate reader.

## Structure
- Each chapter opens with a concrete problem/scenario.
- Sidebars: "Tip", "Warning", "Note" — render as blockquote with leading bold tag.
- End every chapter with "Summary" and "Exercises".

## Formatting
- Fenced code blocks with language tags. Inline code in backticks.
- H2 for sections, H3 for subsections. No deeper.
- Code lines wrap at a sensible width; never rely on horizontal scroll.

## Length
Chapters 2500–4000 words. ~6–10 sections.
```

`<name>.css` is the EPUB stylesheet (font stack, code block styling, sidebar callouts via `blockquote.tip` etc.). Tested by loading + asserting required selectors exist.

---

## Error handling — boundaries only

- `anthropic_client.py`: thin async wrapper; classifies SDK exceptions → `ApiError(retryable=True|False)`. SDK retries handle transient errors; we re-raise terminal ones.
- `assemble.py`: `subprocess.run(...)` for pandoc; non-zero exit → `PandocError` with stderr tail. Same for `kindlepreviewer`.
- `workdir.py`: atomic write helpers raise `FsError` with path context.
- `cover.py`: image API call wrapped; failures degrade to SVG fallback (logged, not raised).
- Everywhere else (`pipeline.py`, `prompts/*`, `outline.py` parsing): let it throw. Pydantic gives structured errors; CLI top-level catches, formats, sets exit code.

No defensive `try/except` around internal code.

---

## Test strategy (pytest)

Unit:

- **test_prompts.py** — `cache_control` is on exactly the right blocks (not the user message); prompt strings stable (snapshot via `syrupy` or hand-rolled compare); outline JSON canonicalized so the cache key is byte-stable; `--kindle` adds the line-length clause and nothing else.
- **test_outline.py** — feed the fake async client canned responses (valid JSON, malformed JSON, schema-violation JSON); assert the validate→repair flow runs exactly one repair, then `OutlineError` on second failure.
- **test_styles.py** — every default + extras style loads via `load_style`; `.css` exists; markdown contains required sections (`## Voice`, `## Structure`, `## Formatting`, `## Length`).
- **test_assemble.py** — `build_pandoc_args(...)` produces the expected argv from a fixture outline; `metadata.yaml` matches expected shape; `--kindle` flips `--highlight-style` correctly. Don't actually run pandoc here.
- **test_workdir.py** — atomic writes survive a simulated crash mid-write (write to `.tmp`, never rename, recovery sees no `ch-NN.md`); `options.json` mismatch raises unless `--force`.

Integration:

- **test_integration.py** — replace the SDK client with an async fake matching the surface we use (`messages.create`), feed canned outline + canned chapters, run real `pipeline.run()` in a `tmp_path`, shell out to real pandoc (`pytest.mark.skipif(not has_pandoc())`). Assert: output `.epub` exists, is a valid zip, contains `mimetype` (uncompressed, first entry), `META-INF/container.xml`, the expected `content.opf` chapter list, and `nav.xhtml`. If `epubcheck` is on PATH, also run it and assert clean. Otherwise rely on the structural assertions.

Fake at the boundary: `tests/fixtures/fake_anthropic.py` exposes an `AsyncAnthropic`-shaped object whose `messages.create` returns a configurable response. Inject by monkeypatching `anthropic_client.get_client`.

CI note: pandoc must be installed in CI (one apt line). epubcheck optional. Document in README.

---

## EPUB assembly: pandoc vs `ebooklib`

Recommend **pandoc**. Reasons:

- Battle-tested EPUB3 output, correct nav doc, proper TOC depth, valid OPF.
- Markdown → EPUB is one shell-out with `--metadata-file`, `--css`, `--cover-image`, `--toc`, `--split-level=1`.
- `# Title` h1 per chapter file → automatic chapter splits.

Tradeoff: external binary dependency. Users `brew install pandoc` (document it; assert availability at startup with a clear error). The pure-Python alternative `ebooklib` is more capable than the JS equivalents — it produces valid EPUB3 — but: more boilerplate (manual spine, manifest, nav doc construction), no first-class CSS-per-style story without templating, and we'd own the markdown→XHTML pass ourselves (likely via `markdown-it-py`). Worth the switch only if "no native deps" becomes a hard constraint.

Pandoc invocation:

```
pandoc \
  --from=markdown \
  --to=epub3 \
  --output=<out>.epub \
  --metadata-file=<workdir>/metadata.yaml \
  --css=<style>.css \
  --cover-image=<workdir>/cover.{png,svg} \
  --toc --toc-depth=2 \
  --split-level=1 \
  --highlight-style=<pygments|monochrome|kate> \
  <workdir>/ch-01.md ... <workdir>/ch-NN.md
```

With `--kindle`: `--highlight-style=monochrome` (or `kate`), and post-step shell-out to `kindlepreviewer` if present.

---

## Cover generation

Two paths:

1. **Image API** (Anthropic does not currently offer one). Plug-point: optional env `OPENAI_API_KEY` → call `images.generate` (gpt-image-1) using the `cover.py` prompt. If unset, fall through.
2. **SVG fallback**: deterministic, always works. Template per style (title + subtitle + author + style-specific palette/typography). Rendered to `cover.svg`. Pandoc accepts SVG covers; reader support varies. If `pillow` is available, rasterize to PNG 1600×2400; otherwise ship SVG.

Recommend SVG fallback as default; image API behind `--cover-image-api` or auto-detected env. `pillow` is an optional dep with graceful detection.

---

## Open questions

1. **Author / metadata.** Default author `"epubgen"`? Add `--author` flag — cheap, do it.
2. **ISBN / publisher.** Skip by default; expose `--metadata key=val` (repeatable) escape hatch.
3. **Citation / source handling.** For non-fiction (oreilly, apress, academic), should the model invent references? Risk of hallucinated citations. Options: (a) forbid in style prompts, (b) allow but mark `[citation needed]`, (c) accept risk. Default (a); revisit per-style.
4. **Chapter count autonomy.** Model decides within 3–40, `--chapters` overrides. OK?
5. **Cost guardrails.** A 12-chapter book on opus-4-7 at 3k words/chapter is non-trivial spend. Show estimated cost in `--dry-run` and require `--yes` if estimate > $5. Probably yes for v1.
6. **Image cover provider.** Hardcode OpenAI for v1, refactor only when a second provider lands.
7. **Localization.** Pass `--lang` to pandoc + style prompt; style guides are English-only. Defer.
8. **Streaming.** Stream chapter generation to the rich progress for live word counts? Adds complexity to retry handling. Defer to v1.1.
9. **Kindle line-length enforcement.** Prompt-level only, or also a post-pass that flags/refactors >60-char code lines? Start with prompt-only; add a linter pass if violations are common in dogfooding.
10. **Kindle CSS branch.** Single CSS file with a `.kindle` body class, or sibling `<name>.kindle.css`? Start with body class; split only if files diverge.
11. **AZW3 vs EPUB3 only.** Send-to-Kindle handles EPUB3. Is `.azw3` worth the optional dep? Yes — sideloading users want it; cost is near-zero when `kindlepreviewer` is present.

---

## Risks

- **Pandoc availability** — hard dep, hard error at startup if missing. Document in README; emit a clear install hint.
- **Cache invalidation surprises** — any whitespace change in `style.md` or non-canonical outline JSON silently busts the cache. Mitigation: prompt builder normalizes whitespace deterministically; outline JSON dumped with `sort_keys=True`, fixed `indent`; snapshot test on the assembled prompt; integration test asserts `cache_read_input_tokens > 0` after the first chapter.
- **Schema drift between outline and chapter prompt** — if outline JSON shape changes, chapter prompts must update in lockstep. Single source of truth in `schema.py`; prompt builders import the model.
- **Long-context degradation** — outline JSON for a 20-chapter book is small (~5KB), style guides <2KB. Comfortably under any context limit.
- **Hallucinated factuality** — out of scope to fix; document the limitation in README.
- **Kindle preview drift** — `kindlepreviewer` versions vary in CLI flags. Pin the invocation to the documented stable subset; surface stderr verbatim on failure.

---

## First step

Spike: minimal `cli.py` `generate` subcommand + `styles/__init__.py` + `prompts/chapter.py` + a hand-written `outline.json` fixture → run a single chapter generation against the real API with caching enabled, inspect `usage.cache_creation_input_tokens` / `cache_read_input_tokens` on the response to confirm both breakpoints land where intended (style hits across runs, outline hits within a run on chapter 2). Everything else is mechanical once that's verified.
