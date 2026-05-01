"""
slide_master_builder.py
=======================
Phase 3 — Slide Master Injection for the AI PPTX Pipeline.

This module does ONE thing perfectly:
Build a professional PPTX Slide Master from a theme dict so that
every slide in the deck inherits fonts, colors, and layouts automatically.

Usage:
    from slide_master_builder import build_presentation
    prs = build_presentation(theme, contract)
    prs.save("output.pptx")
"""

import io
import copy
from pathlib import Path
from typing import Optional
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
from lxml import etree
import requests
from PIL import Image


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

SLIDE_WIDTH  = Inches(13.333)   # 16:9 widescreen = 12192000 EMU
SLIDE_HEIGHT = Inches(7.5)      #                 =  6858000 EMU

# Phase 2 canvas size (must match headless browser viewport)
CANVAS_WIDTH_PX  = 1280
CANVAS_HEIGHT_PX = 720
DEVICE_SCALE_FACTOR = 2         # Playwright captures at 2x


def px_to_emu(px: float, dpi_scale: float = DEVICE_SCALE_FACTOR) -> int:
    """
    Convert Playwright pixel coordinates to EMU.

    The formula:
      logical_px  = raw_px / device_scale_factor
      slide_ratio = logical_px / canvas_px
      emu         = slide_ratio * slide_dimension_emu

    CRITICAL: Without dividing by device_scale_factor first, every element
    is half-size on high-DPI screens. This was the bug in v1.
    """
    logical_px = px / dpi_scale
    return logical_px   # Return logical pixels; multiply by ratio outside


def coord_to_emu(px: float, axis: str) -> int:
    """Convert a pixel coordinate from Phase 2 map to EMU."""
    logical = px / DEVICE_SCALE_FACTOR
    if axis == "x":
        return int((logical / CANVAS_WIDTH_PX)  * SLIDE_WIDTH)
    else:
        return int((logical / CANVAS_HEIGHT_PX) * SLIDE_HEIGHT)


def size_to_emu(px: float, axis: str) -> int:
    """Convert a pixel dimension from Phase 2 map to EMU."""
    return coord_to_emu(px, axis)


def hex_to_rgb(hex_color: str) -> RGBColor:
    """'#1A6FA8' → RGBColor(0x1A, 0x6F, 0xA8)"""
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ─────────────────────────────────────────────────────────────────────────────
# 1. THEME XML — OOXML Color + Font Scheme
# ─────────────────────────────────────────────────────────────────────────────

def build_theme_xml(theme: dict) -> bytes:
    """
    Generate a complete OOXML <a:theme> element from the theme dict.
    This is injected into prs.slide_master.element so PowerPoint's
    "Edit Theme" panel shows the correct colors and fonts.

    Structure:
        a:theme
          a:themeElements
            a:clrScheme    ← 12 semantic color slots
            a:fontScheme   ← heading + body font pair
            a:fmtScheme    ← fill/line/effect stacks (use defaults)
    """
    c = theme["colors"]
    f = theme["fonts"]

    # Helper: build a color element
    def rgb_el(tag: str, hex_val: str) -> str:
        return f'<{tag}><a:srgbClr val="{hex_val.lstrip("#")}"/></{tag}>'

    # PowerPoint's 12-slot color scheme
    xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="{theme['name']}">
  <a:themeElements>

    <a:clrScheme name="{theme['name']}">
      <!-- Background 1 & 2 -->
      {rgb_el('a:dk1', c['text_dark'])}
      {rgb_el('a:lt1', c['text_light'])}
      <!-- Text 1 & 2 -->
      {rgb_el('a:dk2', c['text_dark'])}
      {rgb_el('a:lt2', c['background'])}
      <!-- 6 Accent colors -->
      {rgb_el('a:accent1', c['primary'])}
      {rgb_el('a:accent2', c['secondary'])}
      {rgb_el('a:accent3', c['accent'])}
      {rgb_el('a:accent4', c.get('surface', '#FFFFFF'))}
      {rgb_el('a:accent5', c['primary'])}
      {rgb_el('a:accent6', c['secondary'])}
      <!-- Hyperlink colors -->
      <a:hlink><a:srgbClr val="{c['primary'].lstrip('#')}"/></a:hlink>
      <a:folHlink><a:srgbClr val="{c['secondary'].lstrip('#')}"/></a:folHlink>
    </a:clrScheme>

    <a:fontScheme name="{theme['name']}">
      <a:majorFont>
        <a:latin typeface="{f['heading']}" panose="020F0702030204040204"/>
        <a:ea typeface=""/>
        <a:cs typeface=""/>
      </a:majorFont>
      <a:minorFont>
        <a:latin typeface="{f['body']}" panose="020B0604030504040204"/>
        <a:ea typeface=""/>
        <a:cs typeface=""/>
      </a:minorFont>
    </a:fontScheme>

    <!-- Default fill/line/effect stacks (minimal — PowerPoint fills in the rest) -->
    <a:fmtScheme name="Office Theme">
      <a:fillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:gradFill rotWithShape="1">
          <a:gsLst>
            <a:gs pos="0"><a:schemeClr val="phClr"><a:lumMod val="110000"/><a:satMod val="105000"/><a:tint val="67000"/></a:schemeClr></a:gs>
            <a:gs pos="50000"><a:schemeClr val="phClr"><a:lumMod val="105000"/><a:satMod val="103000"/><a:tint val="73000"/></a:schemeClr></a:gs>
            <a:gs pos="100000"><a:schemeClr val="phClr"><a:lumMod val="105000"/><a:satMod val="109000"/><a:tint val="81000"/></a:schemeClr></a:gs>
          </a:gsLst>
          <a:lin ang="5400000" scaled="0"/>
        </a:gradFill>
        <a:gradFill rotWithShape="1">
          <a:gsLst>
            <a:gs pos="0"><a:schemeClr val="phClr"><a:satMod val="103000"/><a:lumMod val="102000"/><a:tint val="94000"/></a:schemeClr></a:gs>
            <a:gs pos="100000"><a:schemeClr val="phClr"><a:lumMod val="99000"/><a:satMod val="120000"/><a:shade val="78000"/></a:schemeClr></a:gs>
          </a:gsLst>
          <a:lin ang="5400000" scaled="0"/>
        </a:gradFill>
      </a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="6350" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>
        <a:ln w="12700" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>
        <a:ln w="19050" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle>
          <a:effectLst>
            <a:outerShdw blurRad="57150" dist="19050" dir="5400000" algn="ctr" rotWithShape="0">
              <a:srgbClr val="000000"><a:alpha val="63000"/></a:srgbClr>
            </a:outerShdw>
          </a:effectLst>
        </a:effectStyle>
      </a:effectStyleLst>
      <a:bgFillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"><a:tint val="95000"/><a:satMod val="170000"/></a:schemeClr></a:solidFill>
        <a:gradFill rotWithShape="1">
          <a:gsLst>
            <a:gs pos="0"><a:schemeClr val="phClr"><a:tint val="93000"/><a:satMod val="150000"/><a:shade val="98000"/><a:lumMod val="102000"/></a:schemeClr></a:gs>
            <a:gs pos="100000"><a:schemeClr val="phClr"><a:tint val="98000"/><a:satMod val="130000"/><a:shade val="90000"/><a:lumMod val="103000"/></a:schemeClr></a:gs>
          </a:gsLst>
          <a:lin ang="5400000" scaled="0"/>
        </a:gradFill>
      </a:bgFillStyleLst>
    </a:fmtScheme>

  </a:themeElements>
</a:theme>
"""
    return xml.encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 2. SLIDE MASTER BACKGROUND
# ─────────────────────────────────────────────────────────────────────────────

def set_master_background(slide_master, bg_color_hex: str):
    """Set a solid background color on the Slide Master."""
    bg = slide_master.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = hex_to_rgb(bg_color_hex)


# ─────────────────────────────────────────────────────────────────────────────
# 3. SLIDE LAYOUTS — 12 named layouts matching the 12 HTML templates
# ─────────────────────────────────────────────────────────────────────────────

LAYOUT_NAMES = [
    "hero",
    "learning_objectives",
    "hook",
    "content_single",
    "content_three_col",
    "visual_diagram",
    "timeline",
    "comparison_table",
    "real_world_example",
    "activity",
    "quiz_mcq",
    "summary",
]

def rename_slide_layouts(slide_master):
    """
    Rename the 12 default slide layouts to match our template names.
    This lets Phase 3 look up a layout by name instead of index.
    """
    layouts = slide_master.slide_layouts
    for i, name in enumerate(LAYOUT_NAMES):
        if i < len(layouts):
            layouts[i].name = name


def get_layout_by_name(prs: Presentation, name: str):
    """Look up a slide layout by template name."""
    slide_master = prs.slide_master
    for layout in slide_master.slide_layouts:
        if layout.name == name:
            return layout
    # Fallback to first layout if name not found
    print(f"[WARNING] Layout '{name}' not found. Using layout[0].")
    return slide_master.slide_layouts[0]


# ─────────────────────────────────────────────────────────────────────────────
# 4. MASTER TEXT STYLES — Default font settings for all placeholders
# ─────────────────────────────────────────────────────────────────────────────

def set_master_text_styles(slide_master, theme: dict):
    """
    Inject font defaults into the Slide Master's <p:txStyles> XML element.
    This sets heading font, body font, and default colors for ALL slides
    without needing to set them individually on each text frame.
    """
    fonts = theme["fonts"]
    colors = theme["colors"]
    primary_hex = colors["primary"].lstrip("#")
    dark_hex    = colors["text_dark"].lstrip("#")

    # Access the txStyles XML on the slide master
    sp_tree = slide_master.element.spTree

    # The txStyles element (contains title and body text defaults)
    tx_styles_xml = f"""
<p:txStyles xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:titleStyle>
    <a:lvl1pPr algn="l" defTabSz="914400" rtl="0" eaLnBrk="1" latinLnBrk="0" hangingPunct="1">
      <a:defRPr sz="4400" kern="1200" b="1" dirty="0">
        <a:solidFill><a:srgbClr val="{dark_hex}"/></a:solidFill>
        <a:latin typeface="{fonts['heading']}" pitchFamily="0" charset="0"/>
      </a:defRPr>
    </a:lvl1pPr>
  </p:titleStyle>
  <p:bodyStyle>
    <a:lvl1pPr algn="l" defTabSz="914400" rtl="0" eaLnBrk="1" latinLnBrk="0" hangingPunct="1">
      <a:defRPr sz="2200" kern="1200" dirty="0">
        <a:solidFill><a:srgbClr val="{dark_hex}"/></a:solidFill>
        <a:latin typeface="{fonts['body']}" pitchFamily="0" charset="0"/>
      </a:defRPr>
    </a:lvl1pPr>
  </p:bodyStyle>
  <p:otherStyle>
    <a:defPPr>
      <a:defRPr lang="en-US" dirty="0">
        <a:solidFill><a:srgbClr val="{dark_hex}"/></a:solidFill>
        <a:latin typeface="{fonts['body']}" pitchFamily="0" charset="0"/>
      </a:defRPr>
    </a:defPPr>
  </p:otherStyle>
</p:txStyles>
    """.strip()

    # Remove existing txStyles if present
    master_el = slide_master.element
    ns = "http://schemas.openxmlformats.org/presentationml/2006/main"
    existing = master_el.find(f"{{{ns}}}txStyles")
    if existing is not None:
        master_el.remove(existing)

    # Append the new txStyles
    master_el.append(parse_xml(tx_styles_xml))


# ─────────────────────────────────────────────────────────────────────────────
# 5. MASTER SHAPES — Persistent elements on every slide
# ─────────────────────────────────────────────────────────────────────────────

def add_master_bottom_bar(slide_master, theme: dict):
    """
    Add a subtle bottom bar to the Slide Master.
    It will appear on EVERY slide automatically (except those with their own bg).
    """
    from pptx.util import Pt
    primary_rgb = hex_to_rgb(theme["colors"]["primary"])

    # Bottom accent line — 4px tall, full width, primary color, 30% opacity
    sp = slide_master.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        left=0,
        top=SLIDE_HEIGHT - Pt(3),
        width=SLIDE_WIDTH,
        height=Pt(3),
    )
    sp.fill.solid()
    sp.fill.fore_color.rgb = primary_rgb
    sp.line.fill.background()
    # Set transparency via XML (python-pptx doesn't expose alpha on fills directly)
    fill_el = sp.fill._xPr
    solid_fill = fill_el.find(qn("a:solidFill"))
    if solid_fill is not None:
        srgb = solid_fill.find(qn("a:srgbClr"))
        if srgb is not None:
            alpha_el = etree.SubElement(srgb, qn("a:alpha"))
            alpha_el.set("val", "30000")  # 30% opacity = 30000 in OOXML (100% = 100000)


def add_logo_placeholder(slide_master, logo_url: Optional[str]):
    """
    Add the school logo to the Slide Master bottom-right corner.
    It appears on every slide automatically.
    Skipped if logo_url is None.
    """
    if not logo_url:
        return

    try:
        response = requests.get(logo_url, timeout=5)
        response.raise_for_status()
        img_stream = io.BytesIO(response.content)

        # Resize to max height 36px, preserve aspect ratio
        img = Image.open(io.BytesIO(response.content))
        aspect = img.width / img.height
        logo_height = Pt(27)
        logo_width  = int(logo_height * aspect)

        pic = slide_master.shapes.add_picture(
            io.BytesIO(response.content),
            left=SLIDE_WIDTH - logo_width - Inches(0.4),
            top=SLIDE_HEIGHT - logo_height - Inches(0.25),
            width=logo_width,
            height=logo_height,
        )
    except Exception as e:
        print(f"[WARNING] Could not load logo from {logo_url}: {e}")


def add_page_number_placeholder(slide_master, theme: dict):
    """
    Add a page number text box to the Slide Master bottom-left.
    In python-pptx, use a footer placeholder for the slide number.
    """
    from pptx.util import Pt

    # Add a text box for slide number (bottom left)
    txb = slide_master.shapes.add_textbox(
        left=Inches(0.4),
        top=SLIDE_HEIGHT - Pt(28),
        width=Inches(1.5),
        height=Pt(20),
    )
    tf = txb.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT

    # Add slide number field — OOXML field element
    run = p.add_run()
    fld_xml = (
        '<a:fld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        f'id="{{B3AD2A5A-4C4E-4E4A-8C3A-12345678ABCD}}" type="slidenum">'
        '<a:rPr lang="en-US" dirty="0"/>'
        '<a:t>&lt;slide#&gt;</a:t>'
        "</a:fld>"
    )
    run._r.getparent().append(parse_xml(fld_xml))
    run._r.getparent().remove(run._r)

    # Style the text box
    for para in tf.paragraphs:
        for run in para.runs:
            run.font.size  = Pt(11)
            run.font.color.rgb = hex_to_rgb(theme["colors"]["text_dark"])
            run.font.name  = theme["fonts"]["body"]


# ─────────────────────────────────────────────────────────────────────────────
# 6. INJECT THEME XML INTO THE PRESENTATION PACKAGE
# ─────────────────────────────────────────────────────────────────────────────

def inject_theme_into_prs(prs: Presentation, theme: dict):
    """
    Replace the slide master's theme XML with our custom theme.
    This is the core operation that makes PowerPoint's color palette,
    font picker, and theme variants all use our custom settings.
    """
    theme_xml = build_theme_xml(theme)

    # Access the slide master's theme part via the python-pptx internal API
    slide_master = prs.slide_master
    theme_part = slide_master.theme_color_map   # This path varies by pptx version

    # Direct XML injection via the part's blob
    # python-pptx exposes the theme as a Part with a _blob attribute
    try:
        theme_part_obj = slide_master.part.part_related_by(
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"
        )
        theme_part_obj._blob = theme_xml
        print("[OK] Theme XML injected into slide master part.")
    except Exception as e:
        print(f"[WARNING] Could not inject theme XML directly: {e}")
        print("         Falling back to shape-level styling.")


# ─────────────────────────────────────────────────────────────────────────────
# 7. MAIN — BUILD PRESENTATION FROM CONTRACT
# ─────────────────────────────────────────────────────────────────────────────

def build_presentation(theme: dict, coordinate_maps: list[dict]) -> Presentation:
    """
    Build a complete PPTX file from:
      - theme: the theme dict from the Presentation Contract
      - coordinate_maps: list of Phase 2 coordinate map dicts (one per slide)

    Returns a python-pptx Presentation object ready to save.
    """
    prs = Presentation()
    prs.slide_width  = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    slide_master = prs.slide_master

    print("[1/5] Injecting theme XML...")
    inject_theme_into_prs(prs, theme)

    print("[2/5] Setting slide master background...")
    set_master_background(slide_master, theme["colors"]["background"])

    print("[3/5] Setting master text styles...")
    set_master_text_styles(slide_master, theme)

    print("[4/5] Renaming slide layouts...")
    rename_slide_layouts(slide_master)

    print("[5/5] Adding master shapes (logo, bottom bar, page number)...")
    add_master_bottom_bar(slide_master, theme)
    add_logo_placeholder(slide_master, theme.get("logo_url"))
    add_page_number_placeholder(slide_master, theme)

    print(f"[BUILD] Compiling {len(coordinate_maps)} slides...")
    for coord_map in coordinate_maps:
        _compile_slide(prs, theme, coord_map)

    return prs


def _compile_slide(prs: Presentation, theme: dict, coord_map: dict):
    """
    Compile one slide from its Phase 2 coordinate map.
    Picks the correct layout, then adds each element as a native PPTX shape.
    """
    template_type = coord_map["template_type"]
    layout = get_layout_by_name(prs, template_type)
    slide  = prs.slides.add_slide(layout)

    # Set slide background (in case layout overrides master)
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = hex_to_rgb(theme["colors"]["background"])

    for el in coord_map.get("elements", []):
        _add_element(slide, el, theme)

    # Inject speaker notes
    speaker_notes = coord_map.get("speaker_notes", "")
    if speaker_notes:
        notes_slide = slide.notes_slide
        tf = notes_slide.notes_text_frame
        tf.text = speaker_notes

    # Inject accessibility alt text on slide title shape
    sr_title = coord_map.get("accessibility", {}).get("slide_title_sr", "")
    if sr_title:
        for shape in slide.shapes:
            if shape.has_text_frame and shape.shape_type == 13:   # title placeholder
                shape.element.set("descr", sr_title)
                break


def _add_element(slide, el: dict, theme: dict):
    """
    Add one element from the coordinate map as a native PPTX shape.
    Handles text boxes, images, and rectangles.
    """
    el_type = el.get("element_type", "textbox")

    left   = coord_to_emu(el["x"],      "x")
    top    = coord_to_emu(el["y"],      "y")
    width  = size_to_emu(el["width"],   "x")
    height = size_to_emu(el["height"],  "y")

    if el_type == "textbox":
        _add_text(slide, el, theme, left, top, width, height)
    elif el_type == "image":
        _add_image(slide, el, left, top, width, height)
    elif el_type == "rect":
        _add_rect(slide, el, theme, left, top, width, height)


def _add_text(slide, el: dict, theme: dict, left, top, width, height):
    """Add a styled text box from coordinate map element."""
    txb = slide.shapes.add_textbox(left, top, width, height)
    tf  = txb.text_frame
    tf.word_wrap = True

    text = el.get("text", "").strip()
    if not text:
        return

    p  = tf.paragraphs[0]
    rn = p.add_run()
    rn.text = text

    # Font
    font = rn.font
    font.name  = _resolve_font(el, theme)
    font.size  = Pt(el.get("font_size", 18))
    font.bold  = el.get("font_weight") in ("700", "800", "900", 700, 800, 900)
    font.color.rgb = _parse_color(el.get("color", theme["colors"]["text_dark"]))

    # Paragraph alignment
    align_map = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
    p.alignment = align_map.get(el.get("text_align", "left"), PP_ALIGN.LEFT)

    # No fill, no line on the textbox itself
    txb.fill.background()
    txb.line.fill.background()


def _add_image(slide, el: dict, left, top, width, height):
    """Download and add an image from URL."""
    url = el.get("url")
    if not url:
        return
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        img_stream = io.BytesIO(response.content)
        slide.shapes.add_picture(img_stream, left, top, width, height)
    except Exception as e:
        print(f"[WARNING] Could not load image {url}: {e}")


def _add_rect(slide, el: dict, theme: dict, left, top, width, height):
    """Add a filled rectangle (background blocks, dividers, callout boxes)."""
    from pptx.util import Pt
    shape = slide.shapes.add_shape(1, left, top, width, height)
    bg_hex = el.get("bg_color")
    if bg_hex and bg_hex != "rgba(0, 0, 0, 0)" and bg_hex != "transparent":
        color = _parse_color(bg_hex)
        if color:
            shape.fill.solid()
            shape.fill.fore_color.rgb = color
        else:
            shape.fill.background()
    else:
        shape.fill.background()
    shape.line.fill.background()   # No border by default


def _resolve_font(el: dict, theme: dict) -> str:
    """Pick heading or body font based on font_family in the coordinate map."""
    font_family = el.get("font_family", "")
    if theme["fonts"]["heading"].lower() in font_family.lower():
        return theme["fonts"]["heading"]
    return theme["fonts"]["body"]


def _parse_color(color_str: str) -> Optional[RGBColor]:
    """
    Parse a CSS color string into RGBColor.
    Handles: '#RRGGBB', 'rgb(r, g, b)', 'rgba(r, g, b, a)'.
    Returns None for transparent/invalid.
    """
    if not color_str:
        return None
    s = color_str.strip()
    if s.startswith("#"):
        try:
            return hex_to_rgb(s)
        except Exception:
            return None
    if s.startswith("rgb"):
        parts = s.replace("rgba(", "").replace("rgb(", "").rstrip(")").split(",")
        try:
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            return RGBColor(r, g, b)
        except Exception:
            return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 8. CONVENIENCE — SUBJECT THEME PRESETS
# ─────────────────────────────────────────────────────────────────────────────

SUBJECT_THEMES = {
    "science": {
        "name": "science_blue",
        "colors": {
            "primary":    "#1A6FA8",
            "secondary":  "#0D9E75",
            "accent":     "#F4A623",
            "background": "#F7F9FC",
            "text_dark":  "#1A1A2E",
            "text_light": "#FFFFFF",
            "surface":    "#FFFFFF",
        },
        "fonts": {"heading": "Montserrat", "body": "Open Sans", "mono": "Fira Code"},
        "logo_url": None,
    },
    "math": {
        "name": "math_purple",
        "colors": {
            "primary":    "#5A3FA8",
            "secondary":  "#8B5CF6",
            "accent":     "#10B981",
            "background": "#F5F3FF",
            "text_dark":  "#1A1A2E",
            "text_light": "#FFFFFF",
            "surface":    "#FFFFFF",
        },
        "fonts": {"heading": "Raleway", "body": "Nunito", "mono": "JetBrains Mono"},
        "logo_url": None,
    },
    "history": {
        "name": "history_gold",
        "colors": {
            "primary":    "#92400E",
            "secondary":  "#B45309",
            "accent":     "#1A6FA8",
            "background": "#FFFBF5",
            "text_dark":  "#1C1917",
            "text_light": "#FFFFFF",
            "surface":    "#FFFFFF",
        },
        "fonts": {"heading": "Playfair Display", "body": "Lora", "mono": "Courier Prime"},
        "logo_url": None,
    },
    "english": {
        "name": "english_teal",
        "colors": {
            "primary":    "#0F766E",
            "secondary":  "#0D9E75",
            "accent":     "#F472B6",
            "background": "#F0FDFA",
            "text_dark":  "#134E4A",
            "text_light": "#FFFFFF",
            "surface":    "#FFFFFF",
        },
        "fonts": {"heading": "Merriweather", "body": "Source Serif 4", "mono": "Fira Code"},
        "logo_url": None,
    },
    "computer_science": {
        "name": "cs_dark",
        "colors": {
            "primary":    "#1E293B",
            "secondary":  "#3B82F6",
            "accent":     "#22D3EE",
            "background": "#0F172A",
            "text_dark":  "#E2E8F0",
            "text_light": "#FFFFFF",
            "surface":    "#1E293B",
        },
        "fonts": {"heading": "Space Grotesk", "body": "Inter", "mono": "JetBrains Mono"},
        "logo_url": None,
    },
}


def get_theme_for_subject(subject: str) -> dict:
    """Look up the default theme for a given subject string."""
    return SUBJECT_THEMES.get(subject.lower(), SUBJECT_THEMES["science"])


# ─────────────────────────────────────────────────────────────────────────────
# 9. CLI ENTRY POINT — FOR TESTING
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json, sys

    if len(sys.argv) < 2:
        print("Usage: python slide_master_builder.py contract.json [output.pptx]")
        sys.exit(1)

    contract_path = Path(sys.argv[1])
    output_path   = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output.pptx")

    with open(contract_path) as f:
        contract = json.load(f)

    theme = contract.get("theme", get_theme_for_subject("science"))

    # In production, coordinate_maps comes from Phase 2 Playwright renderer.
    # For testing, we use an empty list (produces a styled empty deck).
    coordinate_maps = contract.get("coordinate_maps", [])

    prs = build_presentation(theme, coordinate_maps)
    prs.save(output_path)
    print(f"\n✅ Saved to {output_path}")
    print(f"   Slides: {len(prs.slides)}")
    print(f"   Master: {prs.slide_master.name}")
    print(f"   Theme:  {theme['name']}")
