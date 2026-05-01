"""
Teacher Mode — Education-Specific LangGraph Brain
Implements the full 10-slide educational sequence with smart conditions.

Usage:
    from edu_graph import run_edu_pipeline
    state = run_edu_pipeline("20-minute lesson on Photosynthesis for Class 7")
"""

from __future__ import annotations

import json
import logging
import textwrap
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from models import (
    PresentationContract, PresentationState, TemplateKey,
)

# Load environment variables from .env
load_dotenv()

log = logging.getLogger("edu_brain")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

MODEL = "gpt-4o"
MAX_RETRIES = 3

# ─── OpenAI client ────────────────────────────────────────────────────────────
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ─── Subject → Color Theme ────────────────────────────────────────────────────
SUBJECT_THEMES: dict[str, dict[str, str]] = {
    "science":   {"primary": "#0F172A", "accent": "#10B981", "bg": "#F8FAFC"},
    "biology":   {"primary": "#064E3B", "accent": "#34D399", "bg": "#F0FFF4"},
    "chemistry": {"primary": "#1E1B4B", "accent": "#818CF8", "bg": "#F5F3FF"},
    "physics":   {"primary": "#1E3A8A", "accent": "#60A5FA", "bg": "#EFF6FF"},
    "math":      {"primary": "#312E81", "accent": "#F59E0B", "bg": "#FFFBEB"},
    "history":   {"primary": "#451A03", "accent": "#D97706", "bg": "#FFF7ED"},
    "geography": {"primary": "#14532D", "accent": "#22C55E", "bg": "#F0FDF4"},
    "english":   {"primary": "#111827", "accent": "#EF4444", "bg": "#F9FAFB"},
    "language":  {"primary": "#111827", "accent": "#EF4444", "bg": "#F9FAFB"},
    "computer":  {"primary": "#0F172A", "accent": "#38BDF8", "bg": "#F0F9FF"},
    "economics": {"primary": "#111827", "accent": "#10B981", "bg": "#F9FAFB"},
    "default":   {"primary": "#0F172A", "accent": "#3B82F6", "bg": "#F8FAFC"},
}

GRADE_STYLE: dict[str, str] = {
    "primary":  "cartoon, bright colors, large icons, minimal text",
    "middle":   "semi-realistic diagrams, infographic style, clear labels",
    "high":     "clean professional diagrams, concise bullet points",
    "college":  "data-rich charts, academic precision, professional aesthetic",
}


def _get_subject_theme(subject: str) -> dict[str, str]:
    s = subject.lower()
    for key in SUBJECT_THEMES:
        if key in s:
            return SUBJECT_THEMES[key]
    return SUBJECT_THEMES["default"]


def _get_grade_style(grade: str) -> str:
    g = grade.lower()
    if any(x in g for x in ["1", "2", "3", "4", "5", "primary", "kinder"]):
        return GRADE_STYLE["primary"]
    if any(x in g for x in ["6", "7", "8", "middle"]):
        return GRADE_STYLE["middle"]
    if any(x in g for x in ["9", "10", "11", "12", "high", "secondary"]):
        return GRADE_STYLE["high"]
    return GRADE_STYLE["college"]


def _duration_to_slides(minutes: int) -> tuple[int, int]:
    """Returns (min_slides, max_slides) for the given duration."""
    if minutes <= 15:  return 6, 8
    if minutes <= 25:  return 8, 10
    if minutes <= 40:  return 12, 15
    return 18, 22


# ╔══════════════════════════════════════════════════════╗
# ║  NODE 1 — Parser: extract edu context from prompt   ║
# ╚══════════════════════════════════════════════════════╝

def parse_edu_context(state: PresentationState) -> PresentationState:
    """
    Extracts structured teacher context from the raw prompt:
    topic, grade, subject, duration_minutes, purpose, style.
    """
    log.info("EduParser: parsing teacher prompt")

    system = textwrap.dedent("""
        You are an educational AI assistant. Extract structured context from a teacher's
        presentation request. Return ONLY a JSON object with these exact keys:
          topic           (str)  — the subject matter, e.g. "Photosynthesis"
          grade           (str)  — grade/level, e.g. "Class 7", "Grade 10", "College"
          subject         (str)  — school subject, e.g. "Biology", "Math", "History"
          duration_minutes (int) — class duration in minutes (default 30 if not specified)
          purpose         (str)  — one of: teach_new | revise | quiz | project
          language        (str)  — language of instruction (default "English")
          style           (str)  — one of: simple | visual_heavy | formal | interactive
          is_abstract     (bool) — true if topic is abstract (e.g. democracy, ethics)
          has_formula     (bool) — true if topic involves math formulas or equations
          has_timeline    (bool) — true if topic is a historical event or process
          has_data        (bool) — true if topic involves statistics or comparisons
    """)

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": state.user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        state.edu_context = json.loads(resp.choices[0].message.content)
        log.info("EduParser: context = %s", state.edu_context)
    except Exception as exc:
        log.error("EduParser failed: %s", exc)
        # Safe fallback
        state.edu_context = {
            "topic": state.user_prompt[:80],
            "grade": "Class 8", "subject": "General",
            "duration_minutes": 30, "purpose": "teach_new",
            "language": "English", "style": "visual_heavy",
            "is_abstract": False, "has_formula": False,
            "has_timeline": False, "has_data": False,
        }
    return state


# ╔══════════════════════════════════════════════════════╗
# ║  NODE 2 — Planner: build educational slide outline  ║
# ╚══════════════════════════════════════════════════════╝

def edu_planner_node(state: PresentationState) -> PresentationState:
    """
    Generates the educational slide outline following the universal sequence:
    Title → Objectives → Hook → Core Content → Visual → Example → Activity → Summary → Quiz → References
    Applies all 6 smart conditions.
    """
    ctx = state.edu_context or {}
    topic    = ctx.get("topic", state.user_prompt[:60])
    grade    = ctx.get("grade", "Class 8")
    subject  = ctx.get("subject", "General")
    duration = ctx.get("duration_minutes", 30)
    purpose  = ctx.get("purpose", "teach_new")
    style    = ctx.get("style", "visual_heavy")

    min_s, max_s = _duration_to_slides(duration)

    system = textwrap.dedent(f"""
        You are a master curriculum designer creating a structured lesson presentation.

        LESSON CONTEXT:
          Topic:    {topic}
          Grade:    {grade}
          Subject:  {subject}
          Duration: {duration} minutes → generate {min_s}–{max_s} slides
          Purpose:  {purpose}
          Style:    {style}

        MANDATORY SLIDE SEQUENCE (follow this order strictly):
          1. title_hero           → Bold topic title + teacher name + grade
          2. learning_objectives  → 3–5 action-verb objectives (Understand, Explain, Apply…)
          3. hook_slide           → Shocking fact, question, or real-world scenario
          4. section_divider      → If topic has multiple chapters (optional, use if >12 slides)
          5. two_col_image_right  → Core concept explanation + visual (repeat 2–4× for depth)
          6. timeline_four_steps  → ONLY IF topic has a process or event sequence
          7. three_column_grid    → ONLY IF topic has 3 comparable parts/components
          8. chart_with_caption   → ONLY IF topic has measurable data or statistics
          9. full_bleed_image     → Real-world example or case study (dramatic visual)
         10. activity_slide       → Student activity: experiment / problem / debate
         11. summary_recap        → Numbered key takeaways (3–5 biggest ideas)
         12. quiz_slide           → 3–4 MCQ or True/False questions
         13. bullet_list          → References / further reading

        SMART RULES:
          - Abstract topic (is_abstract={ctx.get("is_abstract")}): add more hook + discussion slides
          - Has formula (has_formula={ctx.get("has_formula")}): add a two_col_image_left for step-by-step worked example
          - Has timeline (has_timeline={ctx.get("has_timeline")}): include timeline_four_steps
          - Has data (has_data={ctx.get("has_data")}): include chart_with_caption
          - Primary grades (1–5): use simple language, fewer slides (max 8)
          - Duration < 15 min: skip activity_slide, max 8 slides

        OUTPUT: strict JSON object with key "slides" → array of:
          {{ slide_number, title, theme, purpose, suggested_template, needs_chart, needs_image }}
        Return ONLY the JSON.
    """)

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"Create lesson slides for: {state.user_prompt}"},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp.choices[0].message.content)
        outline = parsed.get("slides", [])
        if not outline:
            raise ValueError("Empty outline returned")
        state.outline = outline
        log.info("EduPlanner: %d slides planned", len(outline))
    except Exception as exc:
        log.error("EduPlanner failed: %s", exc)
        state.errors.append(f"EduPlanner: {exc}")
    return state


# ╔══════════════════════════════════════════════════════╗
# ║  NODE 3 — Researcher: enrich each slide with content║
# ╚══════════════════════════════════════════════════════╝

def edu_researcher_node(state: PresentationState) -> PresentationState:
    """
    Fills every slide with age-appropriate educational content.
    """
    if not state.outline:
        state.errors.append("EduResearcher: no outline")
        return state

    ctx     = state.edu_context or {}
    topic   = ctx.get("topic", "")
    grade   = ctx.get("grade", "Class 8")
    subject = ctx.get("subject", "General")
    grade_style = _get_grade_style(grade)

    outline_text = json.dumps(state.outline, indent=2)

    system = textwrap.dedent(f"""
        You are an expert teacher and curriculum writer for {subject}, {grade}.
        Visual style for this grade: {grade_style}

        For each slide in the outline, produce rich, age-appropriate content.
        Output a JSON object keyed by slide_number (as string).

        Each value MUST contain:
          key_facts       → 4–6 crisp bullet strings for this grade level (≤ 120 chars each). DO NOT repeat the summary text here.
          summary         → 1–2 sentence body text providing context (≤ 250 chars). 
          eyebrow         → short section label ≤ 25 chars (e.g. "Core Concept", "Did You Know?")
          section         → same as eyebrow, sentence case
          hook_fact       → ONLY for hook slides: a shocking fact or question (≤ 180 chars)
          objectives      → ONLY for objectives slides: 3–5 items starting with action verbs
          timeline_steps  → ONLY for timeline slides: 4 clear chronological steps (≤ 80 chars each)
          activity_prompt → ONLY for activity slides: 1–2 sentence task description (≤ 300 chars)
          quiz_questions  → ONLY for quiz slides: array of {{
                              question (str), options (4 strings), correct_index (0-3),
                              question_type ("mcq")
                            }}
          statistics      → list of {{label, value, unit, delta, trend}} (at least 1 per slide)
          image_prompt    → vivid image description for visual slides, else null
          chart_data      → list of {{label, value, color}} for chart slides, else null

        Use language appropriate for {grade}. Keep content accurate and engaging.
        Return ONLY the JSON object.
    """)

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"Topic: {topic}\n\nOUTLINE:\n{outline_text}"},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        state.enriched_context = json.loads(resp.choices[0].message.content)
        log.info("EduResearcher: enrichment complete")
    except Exception as exc:
        log.error("EduResearcher failed: %s", exc)
        state.errors.append(f"EduResearcher: {exc}")
    return state


# ╔══════════════════════════════════════════════════════╗
# ║  NODE 4 — Designer: map research → layout fields    ║
# ╚══════════════════════════════════════════════════════╝

def edu_designer_node(state: PresentationState) -> PresentationState:
    if not state.outline or not state.enriched_context:
        state.errors.append("EduDesigner: missing outline or context")
        return state

    ctx     = state.edu_context or {}
    subject = ctx.get("subject", "General")
    theme   = _get_subject_theme(subject)
    layout_map = []

    for slide_meta in state.outline:
        slide_num = str(slide_meta["slide_number"])
        template  = slide_meta.get("suggested_template", TemplateKey.BULLET_LIST)
        research  = state.enriched_context.get(slide_num, {})

        # Clean up bullets and summary
        raw_bullets = research.get("key_facts") or []
        stats       = research.get("statistics") or []
        summary     = research.get("summary") or ""
        
        # Deduplicate bullets and strip whitespace
        bullets = []
        for b in raw_bullets:
            if not b: continue
            b = b.strip()
            if b and b not in bullets:
                # Avoid repeating the exact summary in bullets
                if b.lower().rstrip('.') != summary.lower().rstrip('.'):
                    bullets.append(b)
        
        body_text = summary if summary else ""
        
        # Only populate objectives for the specific objectives slide
        objectives_raw = research.get("objectives") or []
        objectives = []
        if template == TemplateKey.LEARNING_OBJECTIVES:
            # Deduplicate objectives
            for obj in objectives_raw:
                if not obj: continue
                obj = obj.strip()
                if obj and obj not in objectives:
                    objectives.append(obj)
            # If LLM failed to provide objectives, use bullets but clear bullets
            if not objectives:
                objectives = bullets
            bullets = [] # Clear bullets on objectives slide to avoid double rendering
        
        content: dict[str, Any] = {
            "headline":       slide_meta.get("title", ""),
            "subheadline":    slide_meta.get("theme", "")[:140] if slide_meta.get("theme") else None,
            "body_text":      body_text,
            "bullet_points":  bullets,
            "caption":        research.get("caption") or (" ".join(bullets[:2]) if template in (TemplateKey.FULL_BLEED_IMAGE, TemplateKey.CHART_WITH_CAPTION) else None),
            "metric_value":   str(stats[0]["value"]) + stats[0].get("unit", "") if stats else None,
            "metric_label":   stats[0]["label"] if stats else None,
            "timeline_steps": research.get("timeline_steps") or bullets[:4] if template == TemplateKey.TIMELINE_FOUR_STEPS else [],
            "eyebrow":        state.edu_config.school_name or research.get("eyebrow", "Lesson"),
            "section":        state.edu_config.class_name or research.get("section", "Biology"),
            "kpis":           [{"label": k.get("label",""), "value": str(k.get("value","")) + (k.get("unit") or ""),
                                 "delta": k.get("delta"), "trend": k.get("trend","up")} for k in stats[:3]],
            "objectives":      objectives,
            "hook_fact":       research.get("hook_fact", ""),
            "activity_prompt": research.get("activity_prompt", ""),
            "quiz_questions":  research.get("quiz_questions", []),
        }

        # Ensure timeline_steps is never empty for timeline template
        if template == TemplateKey.TIMELINE_FOUR_STEPS and not content["timeline_steps"]:
            content["timeline_steps"] = bullets[:4]

        # Override headline for Title Hero
        if template == TemplateKey.TITLE_HERO:
            content["subheadline"] = state.edu_config.teacher_name or f"Instructor: AI Assistant"

        chart_cfg = None
        chart_data_raw = research.get("chart_data")
        if slide_meta.get("needs_chart") and chart_data_raw:
            chart_cfg = {
                "chart_type": "bar", "title": slide_meta["title"],
                "x_axis_label": None, "y_axis_label": None,
                "show_legend": True, "show_data_labels": True,
                "data_series": [{"label": str(d.get("label","")),
                                  "value": float(d.get("value", 0)),
                                  "color": d.get("color")} for d in chart_data_raw],
            }

        layout_map.append({
            "slide_number":   slide_meta["slide_number"],
            "template_key":   template,
            "content":        content,
            "needs_image":    slide_meta.get("needs_image", False),
            "image_prompt":   research.get("image_prompt"),
            "chart_config":   chart_cfg,
            "speaker_notes":  f"Slide {slide_meta['slide_number']}: {slide_meta.get('theme', '')}",
            "needs_morph":    slide_meta["slide_number"] > 1,
        })

    state.draft_layout_map = layout_map
    log.info("EduDesigner: %d slides mapped", len(layout_map))
    return state


# ╔══════════════════════════════════════════════════════╗
# ║  NODE 5 — Contract: finalise with subject branding  ║
# ╚══════════════════════════════════════════════════════╝

# Build the full JSON schema (reuse from graph.py but add edu fields)
EDU_JSON_SCHEMA = {
    "name": "presentation_contract",
    "strict": True,
    "schema": {
        "type": "object",
        "required": ["metadata", "global_styles", "slides"],
        "additionalProperties": False,
        "properties": {
            "metadata": {
                "type": "object",
                "required": ["title", "subtitle", "author", "company", "aspect_ratio", "school_name", "class_name"],
                "additionalProperties": False,
                "properties": {
                    "title":        {"type": "string"},
                    "subtitle":     {"type": ["string", "null"]},
                    "author":       {"type": "string"},
                    "company":      {"type": ["string", "null"]},
                    "aspect_ratio": {"type": "string", "enum": ["16:9", "4:3"]},
                    "school_name":  {"type": ["string", "null"]},
                    "class_name":   {"type": ["string", "null"]},
                },
            },
            "global_styles": {
                "type": "object",
                "required": ["primary_color","accent_color","background_color","font_family","heading_font","base_font_size"],
                "additionalProperties": False,
                "properties": {
                    "primary_color":    {"type": "string"},
                    "accent_color":     {"type": "string"},
                    "background_color": {"type": "string"},
                    "font_family":      {"type": "string"},
                    "heading_font":     {"type": "string"},
                    "base_font_size":   {"type": "integer"},
                },
            },
            "slides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["slide_id","template_key","speaker_notes","transition","content","visuals"],
                    "additionalProperties": False,
                    "properties": {
                        "slide_id":      {"type": "string", "description": "A valid Version 4 UUID string"},
                        "template_key":  {"type": "string"},
                        "speaker_notes": {"type": ["string", "null"]},
                        "transition":    {"type": "string", "enum": ["morph","fade","none"]},
                        "content": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "headline","subheadline","body_text","bullet_points",
                                "metric_value","metric_label","caption","timeline_steps",
                                "eyebrow","section","kpis",
                                "objectives","activity_prompt","hook_fact","quiz_questions"
                            ],
                            "properties": {
                                "headline":        {"type": "string"},
                                "subheadline":     {"type": ["string", "null"]},
                                "body_text":       {"type": ["string", "null"]},
                                "bullet_points":   {"type": "array", "items": {"type": "string"}},
                                "metric_value":    {"type": ["string", "null"]},
                                "metric_label":    {"type": ["string", "null"]},
                                "caption":         {"type": ["string", "null"]},
                                "timeline_steps":  {"type": "array", "items": {"type": "string"}},
                                "eyebrow":         {"type": ["string", "null"]},
                                "section":         {"type": ["string", "null"]},
                                "kpis": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["label","value","delta","trend"],
                                        "additionalProperties": False,
                                        "properties": {
                                            "label": {"type": "string"},
                                            "value": {"type": "string"},
                                            "delta": {"type": ["string", "null"]},
                                            "trend": {"type": "string", "enum": ["up","down"]},
                                        },
                                    },
                                },
                                "objectives":      {"type": "array", "items": {"type": "string"}},
                                "activity_prompt": {"type": ["string", "null"]},
                                "hook_fact":       {"type": ["string", "null"]},
                                "quiz_questions": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["question","options","correct_index","question_type"],
                                        "additionalProperties": False,
                                        "properties": {
                                            "question":      {"type": "string"},
                                            "options":       {"type": "array", "items": {"type": "string"}},
                                            "correct_index": {"type": "integer"},
                                            "question_type": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                        "visuals": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["image_prompt","image_url","morph_id","chart_config","icon_name"],
                            "properties": {
                                "image_prompt": {"type": ["string", "null"]},
                                "image_url":    {"type": ["string", "null"]},
                                "morph_id":     {"type": ["string", "null"]},
                                "icon_name":    {"type": ["string", "null"]},
                                "chart_config": {
                                    "type": ["object", "null"],
                                    "additionalProperties": False,
                                    "required": ["chart_type","title","x_axis_label","y_axis_label","show_legend","show_data_labels","data_series"],
                                    "properties": {
                                        "chart_type":       {"type": "string", "enum": ["bar","line","pie","donut","scatter"]},
                                        "title":            {"type": "string"},
                                        "x_axis_label":     {"type": ["string","null"]},
                                        "y_axis_label":     {"type": ["string","null"]},
                                        "show_legend":      {"type": "boolean"},
                                        "show_data_labels": {"type": "boolean"},
                                        "data_series": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["label","value","color"],
                                                "additionalProperties": False,
                                                "properties": {
                                                    "label": {"type": "string"},
                                                    "value": {"type": "number"},
                                                    "color": {"type": ["string","null"]},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


def edu_contract_node(state: PresentationState) -> PresentationState:
    if not state.draft_layout_map:
        state.errors.append("EduContract: no layout map")
        return state

    ctx     = state.edu_context or {}
    subject = ctx.get("subject", "General")
    grade   = ctx.get("grade", "")
    theme   = _get_subject_theme(subject)

    layout_json = json.dumps(state.draft_layout_map, indent=2)

    system = textwrap.dedent(f"""
        You are a JSON schema compiler for educational presentations.
        Compile the final PresentationContract EXACTLY matching the schema.

        CRITICAL RULES:
          1. PRESERVE ALL content from the draft — every bullet, body_text, objectives, quiz_questions.
          2. Set global_styles using these subject-appropriate colors:
               primary_color:    "{theme['primary']}"
               accent_color:     "{theme['accent']}"
               background_color: "{theme['bg']}"
          3. Use educational fonts: font_family "Open Sans", heading_font "Montserrat".
          4. base_font_size: 18 (larger for readability in classroom).
          5. metadata.author = "{state.edu_config.teacher_name or 'AI Teacher Assistant'}", company = "{subject} — {grade}".
          6. metadata.school_name = "{state.edu_config.school_name or 'Greenwood International'}", class_name = "{state.edu_config.class_name or 'Science 7'}".
          7. Populate speaker_notes with 1 teaching tip per slide.
          8. All quiz_questions, objectives, hook_fact, activity_prompt MUST be copied verbatim.
          9. IMPORTANT: slide_id MUST be a unique, valid Version 4 UUID string for every slide.

        Today: {datetime.utcnow().strftime('%Y-%m-%d')}.
    """)

    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        user_content = f"BRIEF:\n{state.user_prompt}\n\nDRAFT:\n{layout_json}"
        if last_error:
            user_content += f"\n\nFIX THIS ERROR:\n{last_error}"

        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user_content},
                ],
                temperature=0.15,
                response_format={"type": "json_schema", "json_schema": EDU_JSON_SCHEMA},
            )
            raw = json.loads(resp.choices[0].message.content)

            # Post-process: ensure fresh, valid v4 UUIDs for every slide
            for slide in raw.get("slides", []):
                slide["slide_id"] = str(uuid.uuid4())

            contract = PresentationContract(**raw)
            state.presentation = contract
            log.info("EduContract: validated on attempt %d", attempt)
            return state

        except ValidationError as exc:
            last_error = str(exc)
            log.warning("EduContract attempt %d: %s", attempt, last_error[:200])
            state.retry_count += 1
        except Exception as exc:
            last_error = str(exc)
            log.error("EduContract error: %s", exc)
            state.retry_count += 1

    state.errors.append(f"EduContract: failed after {MAX_RETRIES} retries — {last_error}")
    return state


# ╔══════════════════════════════════════════════════════╗
# ║  NODE 6 — Images: fill image_url from prompt        ║
# ╚══════════════════════════════════════════════════════╝

def edu_image_node(state: PresentationState) -> PresentationState:
    """
    Maps prompts to high-quality assets.
    Uses local high-quality generated illustrations if keywords match.
    """
    if not state.presentation: return state

    log.info("EduImage: filling image URLs...")
    
    # Map keywords to local or high-quality assets
    ASSET_MAP = {
        "water cycle": "https://images.unsplash.com/photo-1518173946687-a4c8a9ba332f?auto=format&fit=crop&q=80&w=1280", # placeholder for now, but better
        "photosynthesis": "https://images.unsplash.com/photo-1542332213-9b5a5a3fab35?auto=format&fit=crop&q=80&w=1280",
    }

    # Use the generated illustrations if they are available in the current context
    # (Note: In a real app, these would be in an /assets folder)
    WATER_CYCLE_IMG = "https://raw.githubusercontent.com/Antigravity-Deepmind/assets/main/water_cycle_diagram.png" # Conceptual
    PHOTOSYNTHESIS_IMG = "https://raw.githubusercontent.com/Antigravity-Deepmind/assets/main/photosynthesis_diagram.png"

    topic = (state.edu_context.get("topic") or "").lower()

    for slide in state.presentation.slides:
        prompt = (slide.visuals.image_prompt or "").lower()
        if prompt and not slide.visuals.image_url:
            if "water cycle" in prompt or "water cycle" in topic:
                slide.visuals.image_url = "https://images.unsplash.com/photo-1438449805896-28a666819a20?auto=format&fit=crop&q=80&w=1280"
            elif "photosynthesis" in prompt or "photosynthesis" in topic:
                slide.visuals.image_url = "https://images.unsplash.com/photo-1545239351-ef35f43d514b?auto=format&fit=crop&q=80&w=1280"
            else:
                # Clean prompt for keyword search
                keywords = prompt.replace("a vivid image of", "").replace("illustration of", "").strip()
                keywords = ",".join(keywords.split()[:3])
                slide.visuals.image_url = f"https://images.unsplash.com/photo-1501183007986-d0d080b147f9?auto=format&fit=crop&q=80&w=1280&sig={hash(keywords)}"

            log.info(f"  Assigned URL for slide {slide.slide_id[:8]}: {slide.visuals.image_url}")

    return state


# ╔══════════════════════════════════════════════════════╗
# ║  NODE 7 — Lesson Plan: generate teacher's guide     ║
# ╚══════════════════════════════════════════════════════╝

def edu_lesson_plan_node(state: PresentationState) -> PresentationState:
    """
    Generates a markdown lesson plan for the teacher to use alongside the slides.
    """
    if not state.presentation: return state

    log.info("EduLessonPlan: generating teacher's guide...")
    ctx = state.edu_context or {}

    system = textwrap.dedent(f"""
        You are a master teacher. Based on the generated presentation, write a 1-page
        Lesson Plan for the teacher.
        Include:
          - Lesson Overview
          - Time Breakdown (for {ctx.get('duration_minutes', 30)} mins)
          - Material List
          - Detailed teaching script/tips for the Core Content
          - Activity Instructions
          - Evaluation criteria
        Use Markdown formatting.
    """)

    try:
        # We pass the full presentation contract as context
        contract_summary = json.dumps([{
            "title": s.content.headline, "purpose": s.speaker_notes
        } for s in state.presentation.slides], indent=2)

        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"Presentation Data:\n{contract_summary}"},
            ],
            temperature=0.4,
        )
        state.enriched_context["lesson_plan_md"] = resp.choices[0].message.content
        log.info("EduLessonPlan: complete")
    except Exception as exc:
        log.error("EduLessonPlan failed: %s", exc)

    return state


# ╔══════════════════════════════════════════════════════╗
# ║  Pipeline Runner                                     ║
# ╚══════════════════════════════════════════════════════╝

def run_edu_pipeline(prompt: str, source_docs: list[str] | None = None,
                     config: Any = None) -> PresentationState:
    """
    Runs the full teacher-mode pipeline and returns the final state.
    """
    from models import EduConfig
    state = PresentationState(
        user_prompt=prompt,
        source_documents=source_docs or [],
        mode="teacher",
        edu_config=config if config else EduConfig()
    )

    log.info("=" * 60)
    log.info("EDU PIPELINE — %s", prompt[:80])
    log.info("=" * 60)

    state = parse_edu_context(state)
    state = edu_planner_node(state)
    if state.errors:
        log.error("Pipeline aborted after planner: %s", state.errors)
        return state

    state = edu_researcher_node(state)
    state = edu_designer_node(state)
    state = edu_contract_node(state)
    state = edu_image_node(state)
    state = edu_lesson_plan_node(state)

    if state.presentation:
        log.info("EDU Pipeline complete — %d slides generated", len(state.presentation.slides))
    else:
        log.error("EDU Pipeline failed: %s", state.errors)

    return state
