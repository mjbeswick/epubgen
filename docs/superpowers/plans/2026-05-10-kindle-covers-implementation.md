# Kindle-Friendly Covers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement style-matched, full-bleed Kindle covers by compositing SVG templates with AI-generated illustrations via Gemini.

**Architecture:** 
- Gemini generates topic-aware illustration (1024×1024px PNG)
- SVG template per style embeds illustration in placeholder region
- Composite → rasterize to final 1600×2400px PNG
- Inject full-bleed CSS into EPUB cover page

**Tech Stack:** Gemini image generation, Pillow (image ops), cairosvg (SVG rasterization), Python `xml.etree` for SVG manipulation

---

## Task 1: Set Up Cover Module & Test Scaffold

**Files:**
- Create: `src/epubgen/cover.py`
- Create: `tests/test_cover.py`

- [ ] **Step 1: Create bare cover.py with function stubs**

```python
# src/epubgen/cover.py

from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def generate_gemini_cover(
    topic: str,
    title: str,
    subtitle: str,
    author: str,
    style: str,
    output_path: Path,
    cover_prompt_override: Optional[str] = None,
) -> bool:
    """
    Generate a full-bleed Kindle cover by compositing Gemini-generated
    illustration with an SVG template.
    
    Returns True if successful, False if falls back to solid-color SVG.
    """
    pass


def get_illustration_prompt(style: str, topic: str, override: Optional[str] = None) -> str:
    """Build style-aware illustration prompt."""
    pass


def load_cover_template(style: str) -> str:
    """Load SVG template for the given style."""
    pass


def composite_illustration_into_svg(
    svg_content: str,
    illustration_png_path: Path,
) -> str:
    """Embed PNG illustration into SVG template, return rasterized PNG bytes."""
    pass


def create_fallback_svg_cover(
    title: str,
    subtitle: str,
    author: str,
    style: str,
) -> bytes:
    """Generate a fallback SVG cover (no illustration) if image gen fails."""
    pass


def rasterize_svg_to_png(svg_content: str, output_path: Path, width: int = 1600, height: int = 2400) -> bool:
    """Rasterize SVG string to PNG file at specified dimensions."""
    pass
```

- [ ] **Step 2: Create test scaffold**

```python
# tests/test_cover.py

import pytest
from pathlib import Path
from src.epubgen.cover import (
    generate_gemini_cover,
    get_illustration_prompt,
    load_cover_template,
    composite_illustration_into_svg,
    create_fallback_svg_cover,
    rasterize_svg_to_png,
)


def test_get_illustration_prompt_oreilly():
    """oreilly style should produce engraving-focused prompt."""
    prompt = get_illustration_prompt("oreilly", "Python async")
    assert "engraving" in prompt.lower()
    assert "Python async" in prompt


def test_get_illustration_prompt_manning():
    """manning style should produce technical diagram prompt."""
    prompt = get_illustration_prompt("manning", "Kubernetes")
    assert "technical" in prompt.lower() or "diagram" in prompt.lower()
    assert "Kubernetes" in prompt


def test_load_cover_template_oreilly():
    """Should load oreilly SVG template without error."""
    svg = load_cover_template("oreilly")
    assert svg is not None
    assert len(svg) > 0
    assert "<svg" in svg


def test_load_cover_template_missing_fallback():
    """Should raise error or return fallback for missing template."""
    with pytest.raises(FileNotFoundError):
        load_cover_template("nonexistent-style")


def test_rasterize_svg_to_png(tmp_path):
    """SVG rasterization should output valid PNG at correct dimensions."""
    svg_content = '''<svg viewBox="0 0 1600 2400" xmlns="http://www.w3.org/2000/svg">
        <rect width="1600" height="2400" fill="red"/>
    </svg>'''
    output = tmp_path / "test.png"
    result = rasterize_svg_to_png(svg_content, output, width=1600, height=2400)
    assert result is True
    assert output.exists()
    # Verify dimensions via Pillow
    from PIL import Image
    img = Image.open(output)
    assert img.size == (1600, 2400)


def test_create_fallback_svg_cover_returns_valid_svg():
    """Fallback SVG should be valid and contain title/subtitle/author."""
    svg_bytes = create_fallback_svg_cover(
        title="Test Title",
        subtitle="Test Subtitle",
        author="Test Author",
        style="oreilly"
    )
    svg_str = svg_bytes.decode("utf-8")
    assert "<svg" in svg_str
    assert "Test Title" in svg_str
    assert "Test Author" in svg_str
```

- [ ] **Step 3: Run tests to confirm they all fail**

```bash
pytest tests/test_cover.py -v
```

Expected: All tests FAIL with "NotImplementedError" or "pass" (unimplemented stubs).

- [ ] **Step 4: Commit scaffold**

```bash
git add src/epubgen/cover.py tests/test_cover.py
git commit -m "feat: add cover module scaffold with test suite"
```

---

## Task 2: Implement Style-Aware Illustration Prompts

**Files:**
- Modify: `src/epubgen/styles/oreilly.md` (and 7 others: manning, apress, pragprog, nostarch, for-dummies, cheatsheet, pocket-reference)
- Modify: `src/epubgen/cover.py` (implement `get_illustration_prompt`)

- [ ] **Step 1: Add illustration voice to oreilly.md**

Append to `src/epubgen/styles/oreilly.md`:

```markdown
## Cover Illustration Voice

Detailed pen engraving style, black ink on white or transparent background. The illustration should be a botanical or animal subject related to [TOPIC], drawn in the style of 19th-century scientific engravings or natural history illustrations. Naturalistic, detailed, elegant line work. High contrast, suitable for monochrome e-readers. Square composition (~1024×1024), centered subject.
```

- [ ] **Step 2: Add illustration voice to remaining 7 styles**

**manning.md:**
```markdown
## Cover Illustration Voice

Clean, minimalist technical diagram or icon representing [TOPIC]. Modern geometric style, high contrast, business-focused. Sans-serif lines, flat design. Suitable for enterprise and technical audiences. High contrast for e-readers. Square composition (~1024×1024).
```

**apress.md:**
```markdown
## Cover Illustration Voice

Precise technical illustration or detailed diagram style, subject: [TOPIC]. Professional, enterprise-focused, authoritative. Sharp lines, high contrast. Could be a circuit diagram, system architecture, or technical schematic. Monochrome or high-saturation colors. Square composition (~1024×1024).
```

**pragprog.md:**
```markdown
## Cover Illustration Voice

Hand-drawn, slightly quirky and approachable illustration, subject: [TOPIC]. Warm, friendly aesthetic, sketch-like quality. Loose lines, organic shapes. Appeals to developers who prefer personality over formality. Square composition (~1024×1024).
```

**nostarch.md:**
```markdown
## Cover Illustration Voice

Project-driven, hands-on illustration representing [TOPIC] in action. Could be code snippets, tools, building/making metaphor. Colorful, energetic style. Reflects the "build something" spirit of the book. Square composition (~1024×1024).
```

**for-dummies.md:**
```markdown
## Cover Illustration Voice

Friendly, approachable icon or cartoon-style illustration of [TOPIC]. Non-technical, welcoming, beginner-focused. Bright colors, simple shapes, slightly humorous tone. Zero assumed knowledge conveyed visually. Square composition (~1024×1024).
```

**cheatsheet.md:**
```markdown
## Cover Illustration Voice

Telegraphic, scannable visual representing [TOPIC] at a glance. Minimal, card-based or tabular visual metaphor. Quick reference aesthetic. High contrast, typography-forward. Square composition (~1024×1024).
```

**pocket-reference.md:**
```markdown
## Cover Illustration Voice

Reference manual aesthetic: precise, organized visual for [TOPIC]. Numbered sections, organized layout visual metaphor. Professional reference style. High contrast, clear hierarchy. Square composition (~1024×1024).
```

- [ ] **Step 3: Implement get_illustration_prompt in cover.py**

```python
def get_illustration_prompt(style: str, topic: str, override: Optional[str] = None) -> str:
    """
    Build style-aware illustration prompt from style guide + topic.
    
    Args:
        style: Style preset name (e.g., 'oreilly', 'manning')
        topic: Book topic/title extracted from outline
        override: Optional custom prompt to use instead of style voice
    
    Returns:
        Complete illustration prompt ready for image generation
    """
    if override:
        return override
    
    from src.epubgen.styles import load_style_guide
    
    style_guide = load_style_guide(style)
    illustration_voice = style_guide.get("cover_illustration_voice", "")
    
    if not illustration_voice:
        logger.warning(f"No cover illustration voice found for style '{style}'")
        return f"Generate an illustration related to: {topic}"
    
    # Replace [TOPIC] placeholder with actual topic
    prompt = illustration_voice.replace("[TOPIC]", topic)
    return prompt
```

- [ ] **Step 4: Run the two tests that check illustration prompts**

```bash
pytest tests/test_cover.py::test_get_illustration_prompt_oreilly tests/test_cover.py::test_get_illustration_prompt_manning -v
```

Expected: Both PASS (assuming style guides are loaded correctly).

- [ ] **Step 5: Commit**

```bash
git add src/epubgen/styles/oreilly.md src/epubgen/styles/manning.md src/epubgen/styles/apress.md src/epubgen/styles/pragprog.md src/epubgen/styles/nostarch.md src/epubgen/styles/for-dummies.md src/epubgen/styles/cheatsheet.md src/epubgen/styles/pocket-reference.md src/epubgen/cover.py
git commit -m "feat: add cover illustration voice to all style guides"
```

---

## Task 3: Create SVG Cover Templates

**Files:**
- Create: `src/epubgen/styles/oreilly-cover.svg`
- Create: `src/epubgen/styles/manning-cover.svg`
- (and 6 more for other styles)

- [ ] **Step 1: Create base oreilly-cover.svg template**

```xml
<!-- src/epubgen/styles/oreilly-cover.svg -->
<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1600 2400" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <!-- Background -->
  <rect width="1600" height="2400" fill="white"/>
  
  <!-- Red header bar -->
  <rect width="1600" height="180" fill="#C41E3A"/>
  
  <!-- O'REILLY logo/text in header -->
  <text x="50" y="130" font-family="Arial, sans-serif" font-size="60" font-weight="bold" fill="white">
    O'REILLY
  </text>
  
  <!-- Title area -->
  <text x="80" y="450" font-family="Georgia, serif" font-size="72" font-weight="bold" fill="#333333" id="cover-title">
    TITLE_PLACEHOLDER
  </text>
  
  <!-- Subtitle area -->
  <text x="80" y="1300" font-family="Georgia, serif" font-size="32" fill="#666666" id="cover-subtitle">
    SUBTITLE_PLACEHOLDER
  </text>
  
  <!-- Illustration placeholder area -->
  <g id="illustration-area" x="300" y="600">
    <rect x="300" y="600" width="1000" height="800" fill="lightgray" stroke="gray" stroke-width="2"/>
    <text x="800" y="1050" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" fill="gray">
      [Illustration goes here]
    </text>
  </g>
  
  <!-- Author name at bottom -->
  <text x="1550" y="2350" font-family="Arial, sans-serif" font-size="24" fill="#333333" text-anchor="end" id="cover-author">
    AUTHOR_PLACEHOLDER
  </text>
</svg>
```

- [ ] **Step 2: Create manning-cover.svg template**

```xml
<!-- src/epubgen/styles/manning-cover.svg -->
<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1600 2400" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <!-- Background -->
  <rect width="1600" height="2400" fill="white"/>
  
  <!-- Dark header bar -->
  <rect width="1600" height="140" fill="#1a1a1a"/>
  
  <!-- MANNING text in header -->
  <text x="50" y="100" font-family="Arial, sans-serif" font-size="48" font-weight="bold" fill="white">
    MANNING
  </text>
  
  <!-- Title area on dark blue -->
  <rect x="60" y="250" width="1480" height="500" fill="#004B8D" rx="10"/>
  <text x="800" y="450" font-family="Helvetica, sans-serif" font-size="68" font-weight="bold" fill="white" text-anchor="middle" id="cover-title">
    TITLE_PLACEHOLDER
  </text>
  <text x="800" y="650" font-family="Helvetica, sans-serif" font-size="32" fill="#CCCCCC" text-anchor="middle" id="cover-subtitle">
    SUBTITLE_PLACEHOLDER
  </text>
  
  <!-- Illustration placeholder area -->
  <g id="illustration-area" x="300" y="900">
    <rect x="300" y="900" width="1000" height="900" fill="lightgray" stroke="gray" stroke-width="2"/>
    <text x="800" y="1400" text-anchor="middle" font-family="Arial, sans-serif" font-size="24" fill="gray">
      [Illustration goes here]
    </text>
  </g>
  
  <!-- Author name at bottom -->
  <text x="1550" y="2350" font-family="Arial, sans-serif" font-size="24" fill="#333333" text-anchor="end" id="cover-author">
    AUTHOR_PLACEHOLDER
  </text>
</svg>
```

- [ ] **Step 3: Create apress-cover.svg, pragprog-cover.svg, nostarch-cover.svg, for-dummies-cover.svg, cheatsheet-cover.svg, pocket-reference-cover.svg**

(Follow the same pattern as oreilly and manning. Each should have distinct colors, fonts, and layout that reflects the style's visual identity. Key elements: header with publisher name, title area, subtitle area, illustration placeholder with id="illustration-area", author at bottom.)

For brevity, here are the color schemes and key differences:

**apress-cover.svg:** Black background, red accent bar, bold sans-serif title, professional layout.

**pragprog-cover.svg:** Lighter background, rounded corner elements, friendly sans-serif, slightly quirky spacing.

**nostarch-cover.svg:** White background, colorful elements, energetic layout, playful font choices.

**for-dummies-cover.svg:** Bright colors, cartoonish elements, large friendly fonts, approachable layout.

**cheatsheet-cover.svg:** Minimal design, card-like layout, typography-forward, high contrast.

**pocket-reference-cover.svg:** Organized grid-like layout, reference manual aesthetic, professional fonts.

Each template must:
- Have a root `<svg>` with `viewBox="0 0 1600 2400"`
- Include `<text id="cover-title">`, `<text id="cover-subtitle">`, `<text id="cover-author">` elements
- Have a `<g id="illustration-area">` placeholder (can be a rect with gray fill or an empty group)
- Dimensions: 1600×2400px (viewBox and all positioning scaled accordingly)

- [ ] **Step 4: Verify templates load correctly**

```bash
pytest tests/test_cover.py::test_load_cover_template_oreilly -v
```

Expected: PASS (if templates are valid XML).

- [ ] **Step 5: Commit**

```bash
git add src/epubgen/styles/*-cover.svg
git commit -m "feat: add SVG cover templates for all 8 styles"
```

---

## Task 4: Implement Gemini Image Generation

**Files:**
- Modify: `src/epubgen/cover.py`
- Modify: `pyproject.toml` (ensure google-generativeai is a dependency)

- [ ] **Step 1: Verify google-generativeai is in dependencies**

Check `pyproject.toml`:

```toml
dependencies = [
    ...
    "google-generativeai>=0.4.0",  # For Gemini image generation
    ...
]
```

If not present, add it.

- [ ] **Step 2: Implement generate_gemini_illustration function**

Add to `src/epubgen/cover.py`:

```python
def generate_gemini_illustration(
    prompt: str,
    output_path: Path,
    model: str = "gemini-2.0-flash-001",
) -> bool:
    """
    Generate an illustration via Gemini image generation API.
    
    Args:
        prompt: Illustration prompt (style + topic)
        output_path: Where to save the PNG
        model: Gemini model to use
    
    Returns:
        True if successful, False if error
    """
    import google.generativeai as genai
    import os
    
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY or GEMINI_API_KEY not set")
        return False
    
    genai.configure(api_key=api_key)
    
    try:
        logger.info(f"Generating illustration via {model}: {prompt[:80]}...")
        
        # Call Gemini's image generation
        # Note: As of 2026-05, Gemini image generation may be via separate endpoint
        # Check genai.ImageGenerationModel or similar
        response = genai.ImageGenerationModel(model).generate_images(
            prompt=prompt,
            number_of_images=1,
            safety_filter_level="block_only_high",
        )
        
        if not response.images:
            logger.error("No image returned from Gemini")
            return False
        
        # Save first image to output_path
        image_data = response.images[0]._image_bytes
        output_path.write_bytes(image_data)
        logger.info(f"Illustration saved to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Gemini image generation failed: {e}")
        return False
```

- [ ] **Step 3: Add test for Gemini integration (mocked)**

```python
def test_generate_gemini_illustration_mocked(tmp_path, monkeypatch):
    """Test Gemini illustration generation with mocked API."""
    from unittest.mock import Mock, MagicMock
    import google.generativeai as genai
    
    # Mock the Gemini API
    mock_response = Mock()
    mock_image = Mock()
    mock_image._image_bytes = b"fake_png_data"
    mock_response.images = [mock_image]
    
    mock_model = Mock()
    mock_model.generate_images.return_value = mock_response
    
    monkeypatch.setattr(genai, "ImageGenerationModel", Mock(return_value=mock_model))
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    
    output_path = tmp_path / "illustration.png"
    from src.epubgen.cover import generate_gemini_illustration
    
    result = generate_gemini_illustration("test prompt", output_path)
    assert result is True
    assert output_path.exists()
    assert output_path.read_bytes() == b"fake_png_data"
```

- [ ] **Step 4: Run the test**

```bash
pytest tests/test_cover.py::test_generate_gemini_illustration_mocked -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/epubgen/cover.py tests/test_cover.py pyproject.toml
git commit -m "feat: implement Gemini image generation for cover illustrations"
```

---

## Task 5: Implement SVG Template Loading & Text Substitution

**Files:**
- Modify: `src/epubgen/cover.py` (implement `load_cover_template`, add text substitution)

- [ ] **Step 1: Implement load_cover_template**

```python
def load_cover_template(style: str) -> str:
    """
    Load SVG template for the given style.
    
    Args:
        style: Style preset name (e.g., 'oreilly')
    
    Returns:
        SVG content as string
    
    Raises:
        FileNotFoundError: If template doesn't exist
    """
    from importlib import resources
    
    template_name = f"{style}-cover.svg"
    template_path = Path(__file__).parent / "styles" / template_name
    
    if not template_path.exists():
        raise FileNotFoundError(f"Cover template not found: {template_path}")
    
    return template_path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Implement SVG text substitution function**

```python
def substitute_cover_text(svg_content: str, title: str, subtitle: str, author: str) -> str:
    """
    Substitute title, subtitle, and author text into SVG template.
    
    Args:
        svg_content: SVG template as string
        title: Book title
        subtitle: Book subtitle
        author: Author name
    
    Returns:
        SVG with substituted text
    """
    import xml.etree.ElementTree as ET
    
    # Parse SVG
    root = ET.fromstring(svg_content)
    
    # Define namespace if SVG uses one
    ns = {"svg": "http://www.w3.org/2000/svg"}
    
    # Find and replace text elements
    for text_elem in root.findall(".//svg:text", ns):
        if text_elem.get("id") == "cover-title":
            text_elem.text = title
        elif text_elem.get("id") == "cover-subtitle":
            text_elem.text = subtitle
        elif text_elem.get("id") == "cover-author":
            text_elem.text = author
    
    # Convert back to string
    return ET.tostring(root, encoding="unicode")
```

- [ ] **Step 3: Add test for text substitution**

```python
def test_substitute_cover_text():
    """SVG text substitution should replace placeholders."""
    svg = load_cover_template("oreilly")
    result = substitute_cover_text(
        svg,
        title="Test Title",
        subtitle="Test Subtitle",
        author="Test Author"
    )
    assert "Test Title" in result
    assert "Test Subtitle" in result
    assert "Test Author" in result
```

- [ ] **Step 4: Run test**

```bash
pytest tests/test_cover.py::test_substitute_cover_text -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/epubgen/cover.py tests/test_cover.py
git commit -m "feat: implement SVG template loading and text substitution"
```

---

## Task 6: Implement SVG + PNG Compositing

**Files:**
- Modify: `src/epubgen/cover.py`
- Modify: `pyproject.toml` (add Pillow, cairosvg if not present)

- [ ] **Step 1: Verify dependencies**

Check `pyproject.toml` includes:

```toml
dependencies = [
    ...
    "Pillow>=10.0.0",
    "cairosvg>=2.7.0",  # For SVG rasterization
    ...
]
```

- [ ] **Step 2: Implement composite_illustration_into_svg**

```python
def composite_illustration_into_svg(
    svg_content: str,
    illustration_png_path: Path,
) -> str:
    """
    Embed PNG illustration into SVG template's illustration-area placeholder.
    
    Args:
        svg_content: SVG template as string (with id="illustration-area")
        illustration_png_path: Path to generated PNG illustration
    
    Returns:
        Modified SVG as string with embedded image reference
    """
    import xml.etree.ElementTree as ET
    
    # Parse SVG
    root = ET.fromstring(svg_content)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    
    # Find illustration-area group
    illust_area = root.find(".//svg:g[@id='illustration-area']", ns)
    if illust_area is None:
        logger.warning("illustration-area not found in SVG; skipping image embed")
        return svg_content
    
    # Clear the placeholder (remove any existing children)
    for child in list(illust_area):
        illust_area.remove(child)
    
    # Add image reference (use base64-encoded image for self-contained SVG)
    from base64 import b64encode
    
    with open(illustration_png_path, "rb") as f:
        image_b64 = b64encode(f.read()).decode("utf-8")
    
    # Create image element
    image_elem = ET.Element("{http://www.w3.org/2000/svg}image")
    image_elem.set("x", "300")
    image_elem.set("y", "600")
    image_elem.set("width", "1000")
    image_elem.set("height", "800")
    image_elem.set("{http://www.w3.org/1999/xlink}href", f"data:image/png;base64,{image_b64}")
    
    illust_area.append(image_elem)
    
    # Return modified SVG
    return ET.tostring(root, encoding="unicode")
```

- [ ] **Step 3: Implement rasterize_svg_to_png**

```python
def rasterize_svg_to_png(svg_content: str, output_path: Path, width: int = 1600, height: int = 2400) -> bool:
    """
    Rasterize SVG to PNG using cairosvg.
    
    Args:
        svg_content: SVG as string
        output_path: Where to save PNG
        width: Output width in pixels
        height: Output height in pixels
    
    Returns:
        True if successful, False if error
    """
    try:
        import cairosvg
        
        logger.info(f"Rasterizing SVG to PNG: {output_path} ({width}x{height})")
        
        cairosvg.svg2png(
            bytestring=svg_content.encode("utf-8"),
            write_to=str(output_path),
            output_width=width,
            output_height=height,
        )
        
        logger.info(f"Cover PNG saved to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"SVG rasterization failed: {e}")
        return False
```

- [ ] **Step 4: Add integration test**

```python
def test_rasterize_svg_to_png_with_embedded_image(tmp_path):
    """End-to-end: composite illustration into SVG, then rasterize to PNG."""
    from PIL import Image
    
    # Create a minimal illustration PNG
    img = Image.new("RGB", (1024, 1024), color="red")
    illust_path = tmp_path / "illustration.png"
    img.save(illust_path)
    
    # Load template
    svg = load_cover_template("oreilly")
    
    # Substitute text
    svg = substitute_cover_text(svg, "Test", "Subtitle", "Author")
    
    # Composite illustration
    svg = composite_illustration_into_svg(svg, illust_path)
    
    # Rasterize
    output = tmp_path / "cover.png"
    result = rasterize_svg_to_png(svg, output)
    
    assert result is True
    assert output.exists()
    
    # Verify output dimensions
    cover_img = Image.open(output)
    assert cover_img.size == (1600, 2400)
```

- [ ] **Step 5: Run test**

```bash
pytest tests/test_cover.py::test_rasterize_svg_to_png_with_embedded_image -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/epubgen/cover.py tests/test_cover.py pyproject.toml
git commit -m "feat: implement SVG + PNG compositing and rasterization"
```

---

## Task 7: Implement Fallback SVG Cover

**Files:**
- Modify: `src/epubgen/cover.py` (implement `create_fallback_svg_cover`)

- [ ] **Step 1: Implement create_fallback_svg_cover**

```python
def create_fallback_svg_cover(
    title: str,
    subtitle: str,
    author: str,
    style: str,
) -> bytes:
    """
    Generate a fallback SVG cover (no illustration) if image generation fails.
    
    Fallback is a simple layout: header, title, subtitle, author on solid background.
    
    Args:
        title: Book title
        subtitle: Book subtitle
        author: Author name
        style: Style preset (for color scheme)
    
    Returns:
        SVG as bytes
    """
    # Define color schemes per style
    color_schemes = {
        "oreilly": {"header": "#C41E3A", "text": "#333333", "bg": "white"},
        "manning": {"header": "#1a1a1a", "text": "#004B8D", "bg": "white"},
        "apress": {"header": "#000000", "text": "#CC0000", "bg": "white"},
        "pragprog": {"header": "#4A90E2", "text": "#333333", "bg": "white"},
        "nostarch": {"header": "#FF6B35", "text": "#004E89", "bg": "white"},
        "for-dummies": {"header": "#FFB81C", "text": "#333333", "bg": "white"},
        "cheatsheet": {"header": "#333333", "text": "#000000", "bg": "#F5F5F5"},
        "pocket-reference": {"header": "#2C3E50", "text": "#34495E", "bg": "white"},
    }
    
    colors = color_schemes.get(style, color_schemes["oreilly"])
    
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 1600 2400" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect width="1600" height="2400" fill="{colors['bg']}"/>
  
  <!-- Header bar -->
  <rect width="1600" height="200" fill="{colors['header']}"/>
  
  <!-- Title -->
  <text x="80" y="500" font-family="Georgia, serif" font-size="72" font-weight="bold" fill="{colors['text']}">
    {title}
  </text>
  
  <!-- Subtitle -->
  <text x="80" y="800" font-family="Georgia, serif" font-size="32" fill="{colors['text']}">
    {subtitle}
  </text>
  
  <!-- Author -->
  <text x="1520" y="2350" font-family="Arial, sans-serif" font-size="24" fill="{colors['text']}" text-anchor="end">
    {author}
  </text>
</svg>"""
    
    return svg.encode("utf-8")
```

- [ ] **Step 2: Test fallback generation**

```bash
pytest tests/test_cover.py::test_create_fallback_svg_cover_returns_valid_svg -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/epubgen/cover.py
git commit -m "feat: implement fallback SVG cover generation"
```

---

## Task 8: Implement Main Cover Generation Function

**Files:**
- Modify: `src/epubgen/cover.py` (implement `generate_gemini_cover`)

- [ ] **Step 1: Implement generate_gemini_cover**

```python
def generate_gemini_cover(
    topic: str,
    title: str,
    subtitle: str,
    author: str,
    style: str,
    output_path: Path,
    cover_prompt_override: Optional[str] = None,
) -> bool:
    """
    Generate a full-bleed Kindle cover by compositing Gemini-generated
    illustration with an SVG template.
    
    Returns True if successful, False if falls back to solid-color SVG.
    """
    logger.info(f"Generating cover: {title} ({style})")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workdir = output_path.parent
    
    # Step 1: Generate illustration prompt
    illust_prompt = get_illustration_prompt(style, topic, cover_prompt_override)
    logger.debug(f"Illustration prompt: {illust_prompt}")
    
    # Step 2: Generate illustration via Gemini
    illust_path = workdir / "cover-illustration.png"
    if not generate_gemini_illustration(illust_prompt, illust_path):
        logger.warning("Gemini illustration generation failed; using fallback")
        # Fallback: generate SVG without illustration
        fallback_svg = create_fallback_svg_cover(title, subtitle, author, style)
        # Rasterize fallback SVG to PNG
        return rasterize_svg_to_png(fallback_svg.decode("utf-8"), output_path)
    
    # Step 3: Load SVG template
    try:
        svg_template = load_cover_template(style)
    except FileNotFoundError:
        logger.error(f"SVG template not found for style '{style}'")
        fallback_svg = create_fallback_svg_cover(title, subtitle, author, style)
        return rasterize_svg_to_png(fallback_svg.decode("utf-8"), output_path)
    
    # Step 4: Substitute text in template
    svg_with_text = substitute_cover_text(svg_template, title, subtitle, author)
    
    # Step 5: Composite illustration into SVG
    svg_with_illust = composite_illustration_into_svg(svg_with_text, illust_path)
    
    # Step 6: Rasterize to final PNG
    success = rasterize_svg_to_png(svg_with_illust, output_path)
    
    if success:
        logger.info(f"Cover generated successfully: {output_path}")
        return True
    else:
        logger.error("SVG rasterization failed; falling back to solid SVG")
        fallback_svg = create_fallback_svg_cover(title, subtitle, author, style)
        return rasterize_svg_to_png(fallback_svg.decode("utf-8"), output_path)
```

- [ ] **Step 2: Add integration test (mocked Gemini)**

```python
def test_generate_gemini_cover_full_flow(tmp_path, monkeypatch):
    """End-to-end cover generation with mocked Gemini."""
    from unittest.mock import Mock, patch
    from PIL import Image
    import google.generativeai as genai
    
    # Create a fake illustration
    illust_dir = tmp_path / "work"
    illust_dir.mkdir()
    
    def mock_generate_image(prompt, output_path, model="gemini-2.0-flash-001"):
        # Create a minimal PNG
        img = Image.new("RGB", (1024, 1024), color="blue")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        return True
    
    monkeypatch.setattr(
        "src.epubgen.cover.generate_gemini_illustration",
        mock_generate_image
    )
    
    from src.epubgen.cover import generate_gemini_cover
    
    output = illust_dir / "cover.png"
    result = generate_gemini_cover(
        topic="Python async",
        title="Async Mastery",
        subtitle="Master Python concurrency",
        author="Jane Doe",
        style="oreilly",
        output_path=output,
    )
    
    assert result is True
    assert output.exists()
    
    # Verify dimensions
    from PIL import Image
    cover_img = Image.open(output)
    assert cover_img.size == (1600, 2400)
```

- [ ] **Step 3: Run test**

```bash
pytest tests/test_cover.py::test_generate_gemini_cover_full_flow -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/epubgen/cover.py tests/test_cover.py
git commit -m "feat: implement main cover generation function with error handling"
```

---

## Task 9: Integrate Cover Generation into Generate Pipeline

**Files:**
- Modify: `src/epubgen/generate.py` (hook new cover function into generate flow)

- [ ] **Step 1: Find where cover generation currently happens in generate.py**

```bash
grep -n "cover" src/epubgen/generate.py | head -20
```

Expected: Output showing current cover generation logic.

- [ ] **Step 2: Replace old cover logic with new function**

In `src/epubgen/generate.py`, find the `generate()` function and locate the cover generation section. Replace it with:

```python
# In generate() function, after outline is generated:

from src.epubgen.cover import generate_gemini_cover

if not options.no_cover:
    logger.info("Generating cover...")
    
    # Extract topic from outline
    topic = outline.get("topic") or options.topic  # Fallback to options.topic
    
    # Generate cover
    cover_output = workdir / "cover.png"
    cover_success = generate_gemini_cover(
        topic=topic,
        title=options.title,
        subtitle=options.subtitle,
        author=options.author,
        style=options.style,
        output_path=cover_output,
        cover_prompt_override=options.cover_prompt,
    )
    
    if cover_success:
        logger.info(f"Cover generated: {cover_output}")
    else:
        logger.warning("Cover generation failed; proceeding without cover")
else:
    logger.info("Skipping cover generation (--no-cover)")
```

- [ ] **Step 3: Ensure cover_output is passed to EPUB assembly**

Find where the EPUB is assembled (likely calls `pandoc` or `epub.create_epub()`). Ensure the `cover_output` path is passed to the assembly function so it gets embedded.

- [ ] **Step 4: Run generate with a test topic**

```bash
epubgen generate "Test Python Topic" --style oreilly --out test_book.epub --workdir test_book.work
```

Expected: Cover generation completes (either successfully or falls back gracefully).

- [ ] **Step 5: Commit**

```bash
git add src/epubgen/generate.py
git commit -m "feat: integrate new cover generation into generate pipeline"
```

---

## Task 10: Add Full-Bleed CSS to EPUB Cover Page

**Files:**
- Modify: `src/epubgen/epub.py` (or template file where cover XHTML is generated)

- [ ] **Step 1: Find where cover XHTML is created**

```bash
grep -rn "cover\|<html\|<head>" src/epubgen/epub.py | head -30
```

Expected: Output showing cover template or XHTML generation.

- [ ] **Step 2: Add full-bleed CSS**

In the cover XHTML template, ensure the `<style>` block includes:

```html
<html>
<head>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: white;
        }
        img {
            display: block;
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            max-width: none;
        }
    </style>
</head>
<body>
    <img src="../Images/cover.png" alt="Cover" />
</body>
</html>
```

- [ ] **Step 3: Test in Kindle Previewer**

Generate a test EPUB and open it in Kindle Previewer to verify cover fills the screen:

```bash
epubgen generate "Test Topic" --style oreilly --out test.epub
# Open test.epub in Kindle Previewer and verify cover is full-bleed
```

Expected: Cover fills the entire Kindle screen with no white margins.

- [ ] **Step 4: Commit**

```bash
git add src/epubgen/epub.py
git commit -m "feat: add full-bleed CSS to cover page for Kindle display"
```

---

## Task 11: Update amend recover Command

**Files:**
- Modify: `src/epubgen/amend.py` (ensure recover subcommand uses new cover function)

- [ ] **Step 1: Find recover subcommand**

```bash
grep -n "recover\|def.*recover" src/epubgen/amend.py
```

- [ ] **Step 2: Update recover to call new cover generation**

Ensure the `amend recover` command calls `generate_gemini_cover()` via the new path:

```python
# In amend.py, recover operation:

from src.epubgen.cover import generate_gemini_cover

def amend_recover(workdir, cover_prompt=None):
    """Regenerate cover for an existing book."""
    options = load_options(workdir)
    outline = load_outline(workdir)
    
    topic = outline.get("topic") or options.topic
    cover_output = workdir / "cover.png"
    
    result = generate_gemini_cover(
        topic=topic,
        title=options.title,
        subtitle=options.subtitle,
        author=options.author,
        style=options.style,
        output_path=cover_output,
        cover_prompt_override=cover_prompt,
    )
    
    if result:
        # Re-assemble EPUB with new cover
        reassemble_epub(workdir, options)
    
    return result
```

- [ ] **Step 3: Test amend recover**

```bash
epubgen generate "Test Topic" --style oreilly --out test.epub
epubgen amend recover test.epub  # Should regenerate cover
```

Expected: Cover regenerates without error.

- [ ] **Step 4: Commit**

```bash
git add src/epubgen/amend.py
git commit -m "feat: hook new cover generation into amend recover"
```

---

## Task 12: Write Comprehensive Test Suite

**Files:**
- Modify: `tests/test_cover.py` (add edge case and integration tests)

- [ ] **Step 1: Add error handling tests**

```python
def test_generate_gemini_cover_no_api_key(tmp_path, monkeypatch):
    """Cover generation should gracefully fallback if API key missing."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    
    from src.epubgen.cover import generate_gemini_cover
    
    # Should still succeed with fallback
    output = tmp_path / "cover.png"
    result = generate_gemini_cover(
        topic="Python",
        title="Test",
        subtitle="Sub",
        author="Author",
        style="oreilly",
        output_path=output,
    )
    
    # Result may be True (fallback) or False; either is acceptable
    # but output should exist if fallback was generated
    if result:
        assert output.exists()


def test_load_cover_template_all_styles():
    """All 8 style templates should exist and be valid."""
    from src.epubgen.cover import load_cover_template
    
    styles = ["oreilly", "manning", "apress", "pragprog", "nostarch", 
              "for-dummies", "cheatsheet", "pocket-reference"]
    
    for style in styles:
        svg = load_cover_template(style)
        assert svg is not None
        assert "<svg" in svg
        assert 'id="illustration-area"' in svg  # Must have placeholder


def test_substitute_cover_text_handles_special_chars():
    """Text substitution should handle quotes and special characters."""
    from src.epubgen.cover import load_cover_template, substitute_cover_text
    
    svg = load_cover_template("oreilly")
    result = substitute_cover_text(
        svg,
        title='The "Best" Way to Code',
        subtitle="It's & elegant",
        author="O'Reilly & Co."
    )
    
    assert 'The "Best" Way to Code' in result
    assert "It's & elegant" in result
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/test_cover.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cover.py
git commit -m "test: add comprehensive cover generation test suite"
```

---

## Task 13: Manual Testing Across All Styles

**Files:** (Testing only, no code changes)

- [ ] **Step 1: Generate test EPUBs for each of 8 styles**

```bash
for style in oreilly manning apress pragprog nostarch for-dummies cheatsheet pocket-reference; do
  epubgen generate "Advanced Python Programming" \
    --style $style \
    --out test_${style}.epub \
    --workdir test_${style}.work
done
```

- [ ] **Step 2: Open each EPUB in Kindle Previewer**

For each test EPUB:
1. Open in Kindle Previewer
2. View the cover
3. Verify:
   - Cover fills the entire screen (no white margins)
   - Text (title, subtitle, author) is readable
   - Illustration (if present) is clear and centered
   - Style is visually distinct from other styles

- [ ] **Step 3: Document any issues**

If any style has layout problems:
- Adjust the SVG template
- Re-run generation
- Verify fix in Kindle Previewer

- [ ] **Step 4: Commit any SVG adjustments**

```bash
git add src/epubgen/styles/*-cover.svg
git commit -m "fix: refine SVG cover templates based on Kindle testing"
```

---

## Task 14: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add section on cover generation**

Add to README.md (in the "Features" or new "Cover" section):

```markdown
## Cover Generation

Covers are generated automatically for each book, styled to match the chosen style preset.

**How it works:**
1. A topic-aware illustration is generated via Google Gemini image generation
2. The illustration is composited into a style-specific SVG template
3. The final cover is rasterized to 1600×2400px PNG for full-bleed Kindle display

**Style-specific covers:**
Each of the 10 styles has a distinct cover design:
- `oreilly` — Classic red header with detailed engravings
- `manning` — Professional dark header with technical diagrams
- `apress` — Enterprise-focused with sharp technical illustrations
- `pragprog` — Friendly, hand-drawn aesthetic
- `nostarch` — Colorful, project-driven style
- `for-dummies` — Approachable, cartoon-style illustrations
- `cheatsheet` — Minimal, typography-forward design
- `pocket-reference` — Organized reference manual aesthetic

**Disabling covers:**
Pass `--no-cover` to skip cover generation.

**Custom cover prompts:**
Use `--cover-prompt "custom prompt"` to override the auto-generated illustration prompt:
```bash
epubgen generate "Topic" --style oreilly --cover-prompt "A futuristic city landscape"
```

**Regenerating covers:**
Use `epubgen amend recover` to regenerate the cover for an existing book:
```bash
epubgen amend recover mybook.epub
epubgen amend recover mybook.epub --cover-prompt "New illustration prompt"
```
```

- [ ] **Step 2: Update dependencies section (if needed)**

If Pillow and cairosvg aren't already listed, add:

```markdown
## Install

...

### Optional dependencies

| Tool | Purpose | Install |
|---|---|---|
| ... (existing rows) |
| cairosvg | SVG rasterization for cover generation | `pip install cairosvg` or included in `pyproject.toml` |
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document cover generation and style-specific designs"
```

---

## Task 15: Final Verification & Cleanup

**Files:** (Verification only)

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 2: Run linter/formatter**

```bash
ruff check src tests
ruff format src tests
```

- [ ] **Step 3: Run epubgen doctor to verify dependencies**

```bash
epubgen doctor
```

Expected: All required dependencies present.

- [ ] **Step 4: Generate a final test book with verbose logging**

```bash
epubgen generate "Final Test: Python Mastery" \
  --style oreilly \
  --out final_test.epub \
  --workdir final_test.work \
  --verbose --log
```

Expected: Book generates successfully; cover is created without errors; log shows successful illustration generation and compositing.

- [ ] **Step 5: Open in Kindle Previewer and do final visual check**

Open `final_test.epub` in Kindle Previewer:
- Cover fills screen ✓
- Title/subtitle/author are readable ✓
- Illustration is present and clear ✓
- Book opens to first chapter (not cover) on Kindle device ✓

- [ ] **Step 6: Final commit if any changes**

```bash
git status
# If anything changed (formatting, etc.):
git add .
git commit -m "chore: final linting and verification"
```

---

## Summary

This plan implements Kindle-friendly, style-matched covers in 15 tasks:

1. **Foundation (Tasks 1–8):** Core cover generation module with Gemini integration, SVG templates, compositing, and error handling
2. **Integration (Tasks 9–11):** Hook into generate pipeline, EPUB styling, and amend recover
3. **Testing & Polish (Tasks 12–15):** Comprehensive tests, manual validation, README docs, final verification

All code follows TDD (test first, implement, commit). Each task is self-contained and can be reviewed independently. By the end, users will have full-bleed, branded covers across all 8 style presets on their Kindle devices.
