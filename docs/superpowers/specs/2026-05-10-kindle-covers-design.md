# Kindle-Friendly, Style-Matched Cover Design

**Date:** 2026-05-10  
**Status:** Design approved, ready for implementation planning

---

## Goal

Generate professional, full-bleed covers for Kindle that match each style preset's visual identity. Covers should fill the screen on Kindle devices with no uneven margins, and feature topic-driven illustrations that align with the book's style voice.

---

## Problem Statement

Currently, epubgen covers have uneven white space around them when displayed on Kindle. Covers don't reflect the book's style identity, and the generation approach isn't scalable per-style. We need deterministic, branded cover templates with style-appropriate illustrations.

---

## Design Overview

Two-phase hybrid approach:

1. **SVG Template** (per-style, deterministic): Fixed layout with publisher branding, title/subtitle areas, illustration placeholder, author footer. 1600×2400px (standard EPUB, full-bleed on Kindle).

2. **Illustration Generation** (topic-driven, via Gemini): Single AI-generated image derived from book topic + style voice. Composited into the template → final PNG cover.

---

## Architecture

### Data Flow

```
Book options (title, subtitle, outline/topic, style)
  ↓
Extract topic/themes from outline
  ↓
Build illustration prompt (style-specific voice + topic)
  ↓
Call Gemini image generation API
  ↓
Receive ~1024×1024px PNG illustration
  ↓
Load SVG template for the chosen style
  ↓
Composite illustration into template's placeholder area
  ↓
Rasterize SVG → final 1600×2400px PNG cover
  ↓
Embed in EPUB + fix CSS for full-bleed display
```

### Components

#### 1. SVG Templates (`src/epubgen/styles/<style>-cover.svg`)

One template per style preset. Fixed structure:

- **Header region**: Publisher branding (name, logo, color bar)
- **Title area**: Book title in white, bold, large font
- **Subtitle area**: Subtitle or tagline, secondary text
- **Illustration placeholder**: Named region (`<g id="illustration-area">`) where the raster image composites
- **Footer region**: Author name, bottom-right alignment
- **Background**: Style-specific color palette

**Dimensions:** 1600×2400px (portrait, 2:3 aspect ratio, standard for EPUB and Kindle)

**Examples:**
- **oreilly**: Red header bar, white serif title, centered illustration, author baseline
- **manning**: Dark blue/gray palette, clean sans-serif title, offset illustration area
- **apress**: Professional black/red split, large technical-looking title
- **pragprog**: Approachable, slightly quirky layout with rounded elements
- (Similar distinct designs for: nostarch, for-dummies, cheatsheet, pocket-reference)

#### 2. Illustration Generation

**Prompt template per style:**

Each style guide (`src/epubgen/styles/<style>.md`) gains a new section: `## Cover Illustration Voice`

Examples:
- **oreilly**: "Detailed pen engraving style, black ink on white background, botanical or animal subject related to [TOPIC]. Classic naturalistic illustration, circa 19th-century scientific engraving."
- **manning**: "Clean, minimalist technical diagram or icon, business-focused, representing [TOPIC]. Modern, geometric style, high contrast."
- **pragprog**: "Hand-drawn, slightly quirky and approachable illustration, subject: [TOPIC]. Warm, friendly aesthetic, sketch-like quality."
- **apress**: "Technical illustration or precise diagram style, subject: [TOPIC]. Professional, detailed, enterprise-focused."

**Generation workflow:**
1. Extract primary topic/keywords from the generated outline (e.g., "Python async programming")
2. Load the style's cover illustration voice from the style guide
3. Construct prompt: `{illustration_voice} + {topic}`
4. Call `gemini-2.0-flash-001` (or configured Gemini model) image generation API
5. Request output: ~1024×1024px PNG (square, scales well on composite)
6. Cache/store illustration in workdir: `./<out>.work/cover-illustration.png`

**Provider:** Google Gemini image generation (included with `GOOGLE_API_KEY`)

#### 3. Compositing

**Process:**
1. Load SVG template for the chosen style
2. Identify the illustration placeholder region (`#illustration-area`)
3. Embed the generated PNG illustration into the SVG (as an `<image>` element or rasterization target)
4. Rasterize the composite SVG → final 1600×2400px PNG
5. Save as cover image for EPUB embedding

**Implementation:** Use a Python image library (Pillow or similar) to rasterize the SVG + composite.

#### 4. EPUB Integration & Full-Bleed CSS

**Changes to EPUB cover page styling:**

Add/modify `<style>` block in the cover XHTML:
```css
body {
  margin: 0;
  padding: 0;
}
img {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  display: block;
}
```

Ensures the cover image fills the viewport on Kindle with no white space.

---

## Integration into Existing Pipeline

### During `epubgen generate`

1. After outline is generated, extract primary topic
2. Check if cover generation is enabled (not `--no-cover`)
3. Load style's SVG template and illustration voice
4. Generate illustration via Gemini
5. Composite into template → PNG cover
6. Embed in EPUB as before
7. Apply full-bleed CSS to cover page

**No new CLI flags required.** Uses existing infrastructure:
- `--style` to select template
- `--model` to verify Gemini is available (or auto-selects Gemini if configured)
- `--no-cover` to skip cover generation

### During `epubgen amend recover`

Regenerates cover via the same pipeline:
- Loads existing outline from workdir
- Regenerates illustration + composite
- Respects `--cover-prompt` override if provided (custom illustration prompt)

No changes needed to the `recover` command structure.

---

## Error Handling & Fallbacks

### Graceful Degradation

**If Gemini image generation fails** (API error, rate limit, invalid response):
1. Log the error
2. Generate a **fallback SVG template** (no illustration):
   - Uses publisher header + title + subtitle + solid background color
   - Still branded, still readable, still 1600×2400px
   - Full-bleed on Kindle
3. Do NOT block book generation; proceed with fallback cover

**If SVG template file is missing** (e.g., new style added but template not created):
1. Use a **generic SVG template** (minimal branding, header + title + author + plain background)
2. Log a warning
3. Proceed with book; user can re-generate with corrected template later

**If Gemini API key is not configured:**
1. Skip cover generation (existing behavior)
2. Warn user in output
3. Proceed with book (no cover or fallback SVG cover)

### Illustration Quality Control

- Illustration prompt is deterministic per style + topic (reproducible, testable)
- Generated image is cached in workdir (`./<out>.work/cover-illustration.png`) for debugging and manual override
- User can manually replace illustration via `amend recover --cover-prompt "custom prompt"` if quality is unsatisfactory

---

## Testing & Validation

### Manual Testing (Per-Style)

Generate a test EPUB for each of the 8 styles with a known topic (e.g., "Python async programming"):

1. **Visual inspection:**
   - Open `.epub` in a Kindle emulator (Kindle Cloud Reader, Kindle Previewer)
   - Verify cover fills screen with no white margins
   - Verify text (title, subtitle, author) is readable and properly positioned
   - Verify illustration composites cleanly (no artifacts, blending)
   - Confirm style is visually distinct from other styles

2. **Rendering checks:**
   - Verify SVG templates render without errors
   - Confirm 1600×2400px PNG output dimensions
   - Check that CSS removes margins (inspectable via browser DevTools)

### Automated Tests

- **Template existence:** Each style's `-cover.svg` file exists and is valid XML/SVG ✓
- **Gemini integration:** Image generation call structure is correct (mocked in unit tests) ✓
- **Composite output:** Rasterized composite is a valid PNG, correct dimensions (1600×2400) ✓
- **Fallback generation:** Fallback SVG is valid and generates when image gen fails ✓
- **CSS injection:** Cover page XHTML includes full-bleed CSS rules ✓

### Iterative Template Development

1. **Start with oreilly:** Design and test the oreilly template first (most recognizable, highest bar)
2. **Validate in Kindle:** Test in actual Kindle device or Kindle Previewer
3. **Iterate:** Adjust layout, typography, color if needed
4. **Extend to other styles:** Apply learnings to remaining 7 templates

---

## Implementation Phases

### Phase 1: Foundation
- Create SVG templates for all 8 styles (design + initial layout)
- Implement Gemini image generation integration
- Implement SVG + PNG compositing logic
- Add full-bleed CSS to cover XHTML

### Phase 2: Integration & Testing
- Integrate into `cover()` function in existing pipeline
- Hook up illustration generation in `generate` flow
- Manual testing per style (Kindle Previewer, validation)
- Implement automated test suite

### Phase 3: Polish & Fallbacks
- Refine SVG templates based on Kindle testing
- Implement error handling and fallback SVGs
- Document new cover generation approach in README
- Add `amend recover` support (ensure it regenerates via new path)

---

## Files to Create/Modify

**New files:**
- `src/epubgen/styles/oreilly-cover.svg` (and 7 more per style)
- `src/epubgen/cover.py` or extend existing cover module with new `generate_gemini_cover()` function
- `tests/test_cover_generation.py` (unit tests for compositing, fallbacks)

**Modified files:**
- `src/epubgen/styles/*.md` (add `## Cover Illustration Voice` section to each)
- `src/epubgen/generate.py` (integrate new cover generation into `generate` flow)
- `src/epubgen/epub.py` or template (inject full-bleed CSS into cover XHTML)
- `README.md` (document new cover behavior, illustration styles per preset)

---

## Success Criteria

- ✓ Covers fill Kindle screen with no white margins (full-bleed display)
- ✓ Each style has a visually distinct, branded template
- ✓ Illustrations are topic-relevant and style-appropriate
- ✓ Manual Kindle testing (emulator or device) shows proper rendering
- ✓ Fallback SVG covers are generated if image gen fails (graceful degradation)
- ✓ No new CLI flags required; integrates seamlessly into existing `generate` and `amend recover`
- ✓ All 8 style templates are complete and tested

---

## Open Questions / Future Enhancements

- **Multi-language illustration prompts:** Should illustration voice vary by book language? (Deferred; start with English)
- **Custom illustration dimensions:** Should users be able to override illustration size/placement per run? (Deferred; 1024×1024 is a reasonable default)
- **Illustration caching/reuse:** If the same topic is generated twice, reuse the illustration? (Deferred; generate fresh each time for variety)
- **Print-ready covers:** Should we support a "print cover" mode (different dimensions, bleed areas)? (Out of scope; Kindle-focused)

---

## Notes

- SVG templates will be hand-designed once per style (one-time effort per style)
- Illustration generation is cheap via Gemini (included with API key)
- No breaking changes to existing CLI or pipeline
- Seamless integration with `--model` provider selection
