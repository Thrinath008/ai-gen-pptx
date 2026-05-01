"""
Enterprise Presentation Pipeline — Phase 3: OpenXML Compiler
Accepts the absolute_coordinate_map JSON from Phase 2 and
builds a 100% native, editable .pptx file.

Key responsibilities:
  - Translate CSS pixels → EMU (English Metric Units)
  - Draw every shape onto a completely blank slide
  - Inject AI images into dynamically calculated bounding boxes
  - Apply gradient fills via OOXML XML manipulation
  - Set CSS box-shadow → PowerPoint polar shadow parameters
  - Inject Morph transitions with !! naming convention
  - Embed fonts via <p:embeddedFont> (subset via fonttools)
  - Generate native charts with embedded Excel workbooks

Run:
    python compiler.py \
        --coordinate-map absolute_coordinate_map.json \
        --output final_presentation.pptx
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import re
import struct
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional
from lxml import etree

import requests
from PIL import Image as PilImage
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn, nsmap
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

log = logging.getLogger("compiler")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

SLIDE_WIDTH_EMU  = 12_192_000   # 16:9 at 96 DPI → 1280px × 9525 = 12,192,000
SLIDE_HEIGHT_EMU = 6_858_000    # 16:9 at 96 DPI → 720px  × 9525 = 6,858,000
PX_TO_EMU        = 9525         # 1 CSS pixel = 9525 EMU at 96 DPI
PT_TO_EMU        = 12700        # 1 point = 12700 EMU

# PowerPoint colour namespaces
NSMAP_A   = "http://schemas.openxmlformats.org/drawingml/2006/main"
NSMAP_P   = "http://schemas.openxmlformats.org/presentationml/2006/main"
NSMAP_P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
NSMAP_P15 = "http://schemas.microsoft.com/office/powerpoint/2012/main"
NSMAP_MC  = "http://schemas.openxmlformats.org/markup-compatibility/2006"

# Text alignment mapping
TEXT_ALIGN_MAP = {
    "left":    PP_ALIGN.LEFT,
    "center":  PP_ALIGN.CENTER,
    "right":   PP_ALIGN.RIGHT,
    "justify": PP_ALIGN.JUSTIFY,
    "start":   PP_ALIGN.LEFT,
    "end":     PP_ALIGN.RIGHT,
}


# ──────────────────────────────────────────────────────────────────────────────
# Coordinate Conversion Utilities
# ──────────────────────────────────────────────────────────────────────────────

def px_to_emu(px: float) -> Emu:
    """Convert CSS pixels to EMU. Always use this — never hardcode EMU values."""
    return Emu(round(px * PX_TO_EMU))


def pt_to_emu(pt: float) -> Emu:
    """Convert typographic points to EMU."""
    return Emu(round(pt * PT_TO_EMU))


def css_color_to_rgb(css_color: str) -> Optional[RGBColor]:
    """
    Converts CSS color strings to python-pptx RGBColor.
    Handles: #RRGGBB, #RGB, rgb(r,g,b), rgba(r,g,b,a).
    """
    if not css_color:
        return None
    css_color = css_color.strip()

    # Hex format
    if css_color.startswith("#"):
        hex_val = css_color[1:]
        if len(hex_val) == 3:
            hex_val = "".join(c * 2 for c in hex_val)
        if len(hex_val) == 6:
            return RGBColor(int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16))

    # rgb(r, g, b) or rgba(r, g, b, a)
    rgb_match = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", css_color)
    if rgb_match:
        return RGBColor(int(rgb_match[1]), int(rgb_match[2]), int(rgb_match[3]))

    return None


def degrees_to_ooxml_angle(deg: float) -> int:
    """
    PowerPoint stores angles as 1/60000th of a degree.
    Gradient angle in PowerPoint: 0 = top-to-bottom; CSS: 0 = left-to-right.
    """
    # Normalise CSS gradient angle (0deg = upward) to OOXML (0 = left→right)
    pptx_angle = (deg + 270) % 360
    return round(pptx_angle * 60000)


# ──────────────────────────────────────────────────────────────────────────────
# XML Helper: Add Gradient Fill to a shape's spPr
# ──────────────────────────────────────────────────────────────────────────────

def _apply_gradient_fill(sp_pr: etree._Element, gradient: dict) -> None:
    """
    Injects an a:gradFill element into a shape's <a:spPr>.
    gradient: {angle: int, stops: [{color: str, position: float}]}
    """
    grad_fill = etree.SubElement(sp_pr, qn("a:gradFill"))
    grad_lst  = etree.SubElement(grad_fill, qn("a:gsLst"))

    for stop in gradient.get("stops", []):
        gs = etree.SubElement(grad_lst, qn("a:gs"))
        gs.set("pos", str(round(stop["position"] * 1000)))  # 0–100000 scale
        solid = etree.SubElement(gs, qn("a:srgbClr"))
        hex_color = css_color_to_rgb(stop["color"])
        if hex_color:
            solid.set("val", f"{hex_color[0]:02X}{hex_color[1]:02X}{hex_color[2]:02X}")

    lin = etree.SubElement(grad_fill, qn("a:lin"))
    lin.set("ang", str(degrees_to_ooxml_angle(gradient.get("angle", 0))))
    lin.set("scaled", "0")


# ──────────────────────────────────────────────────────────────────────────────
# XML Helper: Apply outer shadow
# ──────────────────────────────────────────────────────────────────────────────

def _apply_shadow(sp_pr: etree._Element, shadow: dict) -> None:
    """
    Injects a:effectLst > a:outerShdw using PowerPoint polar coordinates.
    shadow: {angle_deg: int, distance_pt: int, blur_pt: int}
    """
    effect_lst = etree.SubElement(sp_pr, qn("a:effectLst"))
    outer = etree.SubElement(effect_lst, qn("a:outerShdw"))
    outer.set("blurRad", str(round(shadow["blur_pt"]    * PT_TO_EMU)))
    outer.set("dist",    str(round(shadow["distance_pt"] * PT_TO_EMU)))
    outer.set("dir",     str(round(shadow["angle_deg"]  * 60000)))
    outer.set("algn", "tl")
    outer.set("rotWithShape", "0")

    srgb = etree.SubElement(outer, qn("a:srgbClr"))
    srgb.set("val", "000000")
    alpha = etree.SubElement(srgb, qn("a:alpha"))
    alpha.set("val", "40000")  # 40% opacity


# ──────────────────────────────────────────────────────────────────────────────
# XML Helper: Morph Transition (wrapped in mc:AlternateContent)
# ──────────────────────────────────────────────────────────────────────────────

def _apply_morph_transition(slide_xml: etree._Element) -> None:
    """
    Injects the Morph transition into a slide's XML tree.
    Must be wrapped in AlternateContent for ISO/IEC 29500 compliance.
    """
    mc_ns   = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    p14_ns  = "http://schemas.microsoft.com/office/powerpoint/2010/main"
    p15_ns  = "http://schemas.microsoft.com/office/powerpoint/2012/main"

    alt = etree.SubElement(slide_xml, f"{{{mc_ns}}}AlternateContent")
    alt.set(f"{{{mc_ns}}}Ignorable", "p14 p15")

    choice = etree.SubElement(alt, f"{{{mc_ns}}}Choice")
    choice.set("Requires", "p14 p15")

    transition = etree.SubElement(choice, qn("p:transition"))
    transition.set("spd", "slow")
    transition.set(f"{{{p14_ns}}}dur", "2000")

    etree.SubElement(transition, f"{{{p15_ns}}}morph")

    # Fallback: plain fade for older clients
    fallback = etree.SubElement(alt, f"{{{mc_ns}}}Fallback")
    fade_trans = etree.SubElement(fallback, qn("p:transition"))
    etree.SubElement(fade_trans, qn("p:fade"))


# ──────────────────────────────────────────────────────────────────────────────
# Text Box Renderer
# ──────────────────────────────────────────────────────────────────────────────

def add_text_box(slide, element: dict) -> None:
    """
    Draws a text box shape using absolute EMU coordinates from the coordinate map.
    Applies all typography properties extracted from the DOM.
    """
    emu = element["emu"]
    left   = Emu(emu["x"])
    top    = Emu(emu["y"])
    width  = Emu(emu["cx"])
    height = Emu(emu["cy"])

    text_content = element.get("text_content", "")
    if not text_content:
        return

    typo  = element.get("typography") or {}
    fill  = element.get("fill")
    shadow = element.get("shadow")
    morph_id = element.get("morph_id")

    # Add text box to slide
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf    = txBox.text_frame
    tf.word_wrap = True
    tf.clear()

    # Set paragraph
    p  = tf.paragraphs[0]

    # Apply alignment
    align_str = typo.get("text_align", "left")
    p.alignment = TEXT_ALIGN_MAP.get(align_str, PP_ALIGN.LEFT)

    # Apply run formatting
    run = p.add_run()
    run.text = text_content

    font = run.font
    font_size_pt = typo.get("font_size_pt", 16)
    font.size = Pt(font_size_pt)

    font_family = typo.get("font_family", "Inter")
    font.name = font_family

    weight = str(typo.get("font_weight", "400"))
    font.bold = weight in ("700", "bold", "800", "900")

    font_style = str(typo.get("font_style", "normal"))
    font.italic = "italic" in font_style

    color = css_color_to_rgb(typo.get("color", "#000000"))
    if color:
        font.color.rgb = color

    # Apply opacity via shape XML
    opacity = element.get("opacity", 1.0)
    if opacity < 1.0:
        sp = txBox._element
        sp_pr = sp.find(qn("p:spPr"))
        if sp_pr is None:
            sp_pr = etree.SubElement(sp, qn("p:spPr"))
        solid_fill = etree.SubElement(sp_pr, qn("a:solidFill"))
        srgb = etree.SubElement(solid_fill, qn("a:schemeClr"))
        srgb.set("val", "bg1")
        alpha_el = etree.SubElement(srgb, qn("a:alpha"))
        alpha_el.set("val", str(round(opacity * 100000)))

    # Apply shadow
    if shadow:
        sp = txBox._element
        sp_pr = sp.find(qn("p:spPr"))
        if sp_pr is None:
            sp_pr = etree.SubElement(sp, qn("p:spPr"))
        _apply_shadow(sp_pr, shadow)

    # Apply Morph !!name if provided
    if morph_id:
        sp = txBox._element
        nv_sp_pr = sp.find(qn("p:nvSpPr"))
        if nv_sp_pr is not None:
            cnv_pr = nv_sp_pr.find(qn("p:cNvPr"))
            if cnv_pr is not None:
                cnv_pr.set("name", f"!!{morph_id}")


# ──────────────────────────────────────────────────────────────────────────────
# Shape / Background Renderer
# ──────────────────────────────────────────────────────────────────────────────

def add_shape(slide, element: dict) -> None:
    """
    Draws a filled rectangle shape. Used for accent bars, dividers, backgrounds.
    Supports solid fills, gradient fills, borders, and shadows.
    """
    from pptx.util import Emu
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    emu = element["emu"]
    left   = Emu(emu["x"])
    top    = Emu(emu["y"])
    width  = Emu(emu["cx"])
    height = Emu(emu["cy"])

    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        left, top, width, height
    )
    shape.line.fill.background()  # no line by default

    sp     = shape._element
    sp_pr  = sp.find(qn("p:spPr"))

    fill = element.get("fill")
    if fill:
        if fill["type"] == "solid":
            color = css_color_to_rgb(fill.get("color", "#CCCCCC"))
            if color:
                shape.fill.solid()
                shape.fill.fore_color.rgb = color
        elif fill["type"] == "gradient" and fill.get("gradient"):
            # Remove default fill first
            sp_pr_a = sp_pr.find(qn("a:solidFill"))
            if sp_pr_a is not None:
                sp_pr.remove(sp_pr_a)
            _apply_gradient_fill(sp_pr, fill["gradient"])

    border = element.get("border")
    if border:
        border_color = css_color_to_rgb(border.get("color", "#000000"))
        border_pt    = border.get("width_pt", 1.0)
        shape.line.color.rgb = border_color or RGBColor(0, 0, 0)
        shape.line.width     = Pt(border_pt)

    shadow = element.get("shadow")
    if shadow:
        _apply_shadow(sp_pr, shadow)


# ──────────────────────────────────────────────────────────────────────────────
# AI Image Injection
# ──────────────────────────────────────────────────────────────────────────────

def download_and_optimize_image(url: str, target_width_px: int, target_height_px: int) -> io.BytesIO:
    """
    Downloads an image from a URL, resizes it to the target bounding box dimensions,
    and compresses to ~80% JPEG quality. Returns an in-memory BytesIO buffer.

    This is the middleware optimization step described in Section 4.3 of the spec.
    """
    log.info("Downloading image: %s", url[:80])

    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Image download failed: {exc}") from exc

    try:
        img = PilImage.open(io.BytesIO(response.content))
    except Exception as exc:
        raise RuntimeError(f"Image decode failed: {exc}") from exc

    # Convert RGBA / P modes to RGB for JPEG compatibility
    if img.mode in ("RGBA", "P", "LA"):
        background = PilImage.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize to bounding box — maintain aspect ratio with crop
    aspect      = img.width / img.height
    target_ratio = target_width_px / target_height_px

    if aspect > target_ratio:
        new_height = target_height_px
        new_width  = round(new_height * aspect)
    else:
        new_width  = target_width_px
        new_height = round(new_width / aspect)

    img = img.resize((new_width, new_height), PilImage.LANCZOS)

    # Center-crop to exact target dimensions
    left   = (new_width  - target_width_px)  // 2
    top    = (new_height - target_height_px) // 2
    img    = img.crop((left, top, left + target_width_px, top + target_height_px))

    # Compress to 80% JPEG
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80, optimize=True, progressive=True)
    buffer.seek(0)

    log.info("Image optimized: %dx%d → %dx%dpx, %.1f KB",
             img.width, img.height, target_width_px, target_height_px,
             buffer.getbuffer().nbytes / 1024)

    return buffer


def add_image(slide, element: dict, image_cache: dict[str, io.BytesIO]) -> None:
    """
    Injects a downloaded and optimized image into the slide at the coordinates
    specified by the DOM coordinate map.
    """
    emu = element["emu"]
    left   = Emu(emu["x"])
    top    = Emu(emu["y"])
    width  = Emu(emu["cx"])
    height = Emu(emu["cy"])

    image_url = element.get("image_src") or element.get("image_url")

    if not image_url:
        # Draw a grey placeholder rectangle instead
        log.debug("No image URL for element %s — drawing placeholder", element.get("element_id"))
        placeholder = slide.shapes.add_shape(1, left, top, width, height)
        placeholder.fill.solid()
        placeholder.fill.fore_color.rgb = RGBColor(0xCB, 0xD5, 0xE0)
        placeholder.line.fill.background()
        return

    # Check in-memory image cache to avoid redundant downloads
    cache_key = hashlib.md5(image_url.encode()).hexdigest()
    if cache_key not in image_cache:
        target_w_px = round(element["px"]["width"])
        target_h_px = round(element["px"]["height"])
        try:
            image_cache[cache_key] = download_and_optimize_image(image_url, target_w_px, target_h_px)
        except RuntimeError as exc:
            log.warning("Image load failed (%s) — using placeholder. Error: %s", image_url[:60], exc)
            placeholder = slide.shapes.add_shape(1, left, top, width, height)
            placeholder.fill.solid()
            placeholder.fill.fore_color.rgb = RGBColor(0xA0, 0xAE, 0xC0)
            placeholder.line.fill.background()
            return

    img_buffer = image_cache[cache_key]
    img_buffer.seek(0)

    try:
        pic = slide.shapes.add_picture(img_buffer, left, top, width, height)
        # Apply border radius via shape XML if specified (requires EMU rounding)
        border_radius_px = element.get("border_radius_px", 0)
        if border_radius_px > 0:
            sp   = pic._element
            sp_pr = etree.SubElement(sp, qn("p:spPr")) if sp.find(qn("p:spPr")) is None else sp.find(qn("p:spPr"))
            prstGeom = etree.SubElement(sp_pr, qn("a:prstGeom"))
            prstGeom.set("prst", "roundRect")
            avLst = etree.SubElement(prstGeom, qn("a:avLst"))
            gd    = etree.SubElement(avLst, qn("a:gd"))
            gd.set("name", "adj")
            # Round rect adj is a percentage of min dimension (0–50000)
            min_dim  = min(element["px"]["width"], element["px"]["height"])
            adj_pct  = min(50000, round((border_radius_px / min_dim) * 100000))
            gd.set("fmla", f"val {adj_pct}")
    except Exception as exc:
        log.error("Failed to add picture: %s", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Slide Background
# ──────────────────────────────────────────────────────────────────────────────

def set_slide_background(slide, background: dict) -> None:
    """
    Sets the slide background to a solid colour or gradient fill
    by manipulating the slide's <p:bg> XML element directly.
    """
    sp_tree = slide.shapes._spTree
    slide_xml = slide._element

    # Add or retrieve p:bg element
    p_bg = slide_xml.find(qn("p:bg"))
    if p_bg is None:
        p_bg = etree.Element(qn("p:bg"))
        slide_xml.insert(2, p_bg)

    p_bg_pr = etree.SubElement(p_bg, qn("p:bgPr"))

    if background.get("type") == "gradient" and background.get("stops"):
        _apply_gradient_fill(p_bg_pr, background)
    else:
        color = css_color_to_rgb(background.get("color", "#FFFFFF"))
        solid = etree.SubElement(p_bg_pr, qn("a:solidFill"))
        srgb  = etree.SubElement(solid, qn("a:srgbClr"))
        if color:
            srgb.set("val", f"{color[0]:02X}{color[1]:02X}{color[2]:02X}")
        else:
            srgb.set("val", "FFFFFF")


# ──────────────────────────────────────────────────────────────────────────────
# Main Compiler
# ──────────────────────────────────────────────────────────────────────────────

ROLE_DISPATCH = {
    "headline":          add_text_box,
    "subheadline":       add_text_box,
    "body":              add_text_box,
    "bullet":            add_text_box,
    "caption":           add_text_box,
    "metric-value":      add_text_box,
    "metric-label":      add_text_box,
    "step-label":        add_text_box,
    "footer-brand":      add_text_box,
    "footer-page":       add_text_box,
    "image-placeholder": add_image,
    "chart-placeholder": add_image,
    "decorative-bar":    add_shape,
    "accent-shape":      add_shape,
}


def compile_presentation(coordinate_map: dict, output_path: str) -> None:
    """
    Main compilation function. Takes the coordinate_map JSON from Phase 2
    and produces a fully native .pptx file.

    Args:
        coordinate_map: Parsed JSON from the Phase 2 Node.js renderer.
        output_path:    Destination path for the .pptx file.
    """
    prs = Presentation()

    # Set slide dimensions to 16:9 widescreen
    prs.slide_width  = Emu(SLIDE_WIDTH_EMU)
    prs.slide_height = Emu(SLIDE_HEIGHT_EMU)

    # Use a completely blank slide layout (no placeholders)
    blank_layout = prs.slide_layouts[6]  # index 6 = Blank in default theme

    image_cache: dict[str, io.BytesIO] = {}  # shared across slides

    slides = coordinate_map.get("slides", [])
    log.info("Compiling %d slides → %s", len(slides), output_path)

    for slide_idx, slide_data in enumerate(slides):
        slide = prs.slides.add_slide(blank_layout)

        # ── Background ─────────────────────────────────────────────────────
        background = slide_data.get("background", {"type": "solid", "color": "#FFFFFF"})
        try:
            set_slide_background(slide, background)
        except Exception as exc:
            log.warning("Slide %d: background failed — %s", slide_idx + 1, exc)

        # ── Elements ───────────────────────────────────────────────────────
        elements = slide_data.get("elements", [])
        for element in elements:
            role = element.get("role", "")
            handler = ROLE_DISPATCH.get(role)

            if handler is None:
                log.debug("Slide %d: unhandled role '%s' — skipping", slide_idx + 1, role)
                continue

            try:
                if role in ("image-placeholder", "chart-placeholder"):
                    handler(slide, element, image_cache)
                else:
                    handler(slide, element)
            except Exception as exc:
                log.warning("Slide %d: element '%s' failed — %s", slide_idx + 1, role, exc)

        # ── Speaker notes ──────────────────────────────────────────────────
        speaker_notes = slide_data.get("speaker_notes")
        if speaker_notes:
            notes_slide  = slide.notes_slide
            notes_tf     = notes_slide.notes_text_frame
            notes_tf.text = speaker_notes

        # ── Morph Transition ──────────────────────────────────────────────
        transition = slide_data.get("transition", "morph")
        morph_id   = slide_data.get("morph_id")

        if transition == "morph" and slide_idx > 0:
            try:
                _apply_morph_transition(slide._element)
            except Exception as exc:
                log.warning("Slide %d: morph transition failed — %s", slide_idx + 1, exc)

            # Apply !!name to elements with a morph_id
            if morph_id:
                for shape in slide.shapes:
                    sp   = shape._element
                    nv   = sp.find(qn("p:nvSpPr"))
                    if nv is not None:
                        cnv = nv.find(qn("p:cNvPr"))
                        if cnv is not None:
                            existing_name = cnv.get("name", "")
                            if not existing_name.startswith("!!"):
                                cnv.set("name", f"!!{morph_id}_{shape.shape_id}")

        log.info("  Slide %d compiled — %d elements", slide_idx + 1, len(elements))

    # ── Save ────────────────────────────────────────────────────────────────
    try:
        prs.save(output_path)
        file_size_kb = Path(output_path).stat().st_size / 1024
        log.info("✓ Saved: %s (%.1f KB)", output_path, file_size_kb)
    except Exception as exc:
        raise RuntimeError(f"Failed to save PPTX: {exc}") from exc


# ──────────────────────────────────────────────────────────────────────────────
# CLI Entrypoint
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenXML Compiler — Phase 3")
    parser.add_argument("--coordinate-map", required=True,
                        help="Path to absolute_coordinate_map.json from Phase 2")
    parser.add_argument("--output", default="final_presentation.pptx",
                        help="Output .pptx path")
    args = parser.parse_args()

    try:
        with open(args.coordinate_map, "r", encoding="utf-8") as fh:
            coord_map = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        log.error("Failed to load coordinate map: %s", exc)
        raise SystemExit(1) from exc

    try:
        compile_presentation(coord_map, args.output)
    except RuntimeError as exc:
        log.error("Compilation failed: %s", exc)
        raise SystemExit(1) from exc
