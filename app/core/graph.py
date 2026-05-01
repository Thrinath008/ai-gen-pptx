"""
Enterprise Presentation Pipeline — LangGraph Multi-Agent Brain
Phase 1: Planner → Researcher → Designer → Contract

Run:
    python graph.py --prompt "Q3 Investor Update for AcmeCorp"
"""

from __future__ import annotations

import json
import logging
import os
import textwrap
import uuid
from datetime import datetime
from typing import Any, Literal

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from openai import OpenAI
from pydantic import ValidationError

from models import (
    AspectRatio,
    ChartConfig,
    ChartType,
    DataPoint,
    GlobalStyles,
    PresentationContract,
    PresentationMetadata,
    PresentationState,
    Slide,
    SlideContent,
    SlideVisuals,
    TemplateKey,
    TransitionType,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("brain")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o"

# ──────────────────────────────────────────────
# Layout character budget table
# Enforced by the DesignerNode before calling the LLM.
# ──────────────────────────────────────────────
LAYOUT_CHAR_LIMITS: dict[str, dict[str, int]] = {
    TemplateKey.TITLE_HERO:           {"headline": 80,  "subheadline": 140, "body_text": 200},
    TemplateKey.TWO_COL_IMAGE_RIGHT:  {"headline": 90,  "body_text": 420,   "bullet_points": 5},
    TemplateKey.TWO_COL_IMAGE_LEFT:   {"headline": 90,  "body_text": 420,   "bullet_points": 5},
    TemplateKey.LARGE_METRIC_HERO:    {"headline": 80,  "body_text": 300,   "metric_value": 30, "metric_label": 80},
    TemplateKey.TIMELINE_FOUR_STEPS:  {"headline": 80,  "timeline_steps": 4, "body_text": 200},
    TemplateKey.FULL_BLEED_IMAGE:     {"headline": 60,  "caption": 160, "body_text": 160},
    TemplateKey.THREE_COLUMN_GRID:    {"headline": 80,  "bullet_points": 9},
    TemplateKey.BULLET_LIST:          {"headline": 90,  "bullet_points": 7, "body_text": 200},
    TemplateKey.CHART_WITH_CAPTION:   {"headline": 90,  "caption": 200, "body_text": 200},
    TemplateKey.SECTION_DIVIDER:      {"headline": 60,  "body_text": 200, "subheadline": 120},
    TemplateKey.EXECUTIVE_BRIEF:      {"headline": 80,  "body_text": 300, "bullet_points": 4},
    TemplateKey.DATA_INSIGHT:         {"headline": 80,  "body_text": 300, "bullet_points": 5},
}

MAX_RETRIES = 3


# ╔══════════════════════════════════════════════╗
# ║  NODE 1 — PlannerNode                        ║
# ╚══════════════════════════════════════════════╝

def planner_node(state: PresentationState) -> PresentationState:
    """
    Converts the raw user prompt into a structured narrative outline.
    Output: list[{slide_number, title, theme, purpose, suggested_template}]
    """
    log.info("PlannerNode: generating outline for '%s'", state.user_prompt[:80])

    system_prompt = textwrap.dedent("""
        You are a world-class McKinsey / BCG presentation strategist.
        Your job: turn a presentation brief into a TIGHT, PURPOSEFUL slide outline.

        TEMPLATE GUIDE — pick the best one per slide:
          title_hero          → Opening title slide. Use ONLY for slide 1.
          executive_brief     → Strategy/leadership update. Dark luxury layout. Use for executive summaries.
          bullet_list         → Key takeaway or concept slide. Grid of 6-8 crisp bullets. Most common layout.
          two_col_image_right → Explanation + supporting visual on right. Use when content has an image opportunity.
          two_col_image_left  → Same as above, mirrored. Alternate with two_col_image_right for variety.
          large_metric_hero   → Single dominant KPI or number tells the whole story (e.g., 94% accuracy, $2.3M).
          timeline_four_steps → Step-by-step process, roadmap, or sequential flow. Exactly 4 steps.
          three_column_grid   → Compare 3 options, 3 pillars, or 3 categories side by side. Use for comparisons.
          chart_with_caption  → Data chart + key insight caption. Use when needs_chart is true.
          full_bleed_image    → Dramatic visual statement. Use sparingly for impact moments.
          section_divider     → Dark transition slide between major sections. Use before new chapters.
          data_insight        → Dashboard-style KPI cards + bullet insights on light background.

        RULES:
          - Generate 10–13 slides
          - NEVER use title_hero more than once
          - Use section_divider between major topic changes
          - Use large_metric_hero or data_insight when there are strong numbers
          - Vary templates — don't repeat the same template 3x in a row
          - Every slide must have a SPECIFIC, PUNCHY title (≤ 65 chars)
          - Set needs_chart=true for ANY slide that has comparative or trend data
          - Set needs_image=true for concept/explanation slides

        OUTPUT: a strict JSON object with key "slides" containing an array. Each slide:
          { slide_number, title, theme, purpose, suggested_template, needs_chart, needs_image }
        where purpose is: "intro" | "data" | "insight" | "cta" | "section_break"
        Return ONLY the JSON object.
    """)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": state.user_prompt},
            ],
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            outline = parsed.get("slides", parsed.get("outline", []))
            if not outline and not parsed:
                 outline = []
            elif not outline and parsed:
                 # If it's a dict but no slides/outline key, maybe the dict itself is the first slide or it's a list?
                 # But system prompt says JSON array.
                 outline = []
        else:
            outline = parsed

        if not isinstance(outline, list) or len(outline) == 0:
            # Fallback: if it's a dict with keys like "1", "2", it might be slide numbers
            if isinstance(parsed, dict) and any(k.isdigit() for k in parsed.keys()):
                outline = [v for k, v in sorted(parsed.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999)]
            
            if not outline:
                raise ValueError(f"Outline must be a non-empty list. Got: {type(parsed)}")

        state.outline = outline
        log.info("PlannerNode: outline with %d slides generated", len(outline))

    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        log.error("PlannerNode failed: %s", exc)
        state.errors.append(f"PlannerNode: {exc}")

    return state


# ╔══════════════════════════════════════════════╗
# ║  NODE 2 — ResearcherNode                     ║
# ╚══════════════════════════════════════════════╝

def researcher_node(state: PresentationState) -> PresentationState:
    """
    Enriches the outline with factual depth per slide.
    In production: calls Tavily / Bing Search + RAG vector DB.
    Here: calls the LLM with the outline and any source documents.
    """
    log.info("ResearcherNode: enriching %d slides", len(state.outline or []))

    if not state.outline:
        state.errors.append("ResearcherNode: no outline to enrich")
        return state

    outline_text = json.dumps(state.outline, indent=2)
    source_text  = "\n\n".join(state.source_documents) if state.source_documents else "No source documents provided."

    system_prompt = textwrap.dedent("""
        You are a senior research analyst writing content for a professional business presentation.
        Given a slide outline, produce RICH, DETAILED content for every slide.

        Output a JSON object keyed by slide_number (as a string, e.g. "1", "2").
        Each value must contain EVERY field below:

          key_facts      → list of 5–7 crisp, specific bullet strings (each ≤ 140 chars).
                           Write like a consulting analyst: precise, data-backed, no vague filler.
                           MINIMUM 5 bullets per slide, even for simple topics.

          summary        → A 2-sentence executive summary of this slide's core argument (≤ 280 chars total).
                           This becomes the slide's body text — make it substantive.

          statistics     → list of {label, value, unit, delta, trend} objects.
                           Include at least 1 real or estimated statistic per slide.
                           trend must be "up" or "down".
                           delta is a string like "+18%" or "−$340".

          eyebrow        → Short section label (≤ 30 chars), e.g. "Key Finding", "Market Analysis",
                           "Strategic Insight", "Next Steps". Match the slide's theme.

          section        → Same as eyebrow but sentence-cased, e.g. "Key Finding".

          image_prompt   → A vivid, descriptive Midjourney-style image prompt if needs_image is true, else null.
                           Example: "Futuristic data center with glowing server racks, blue neon lighting,
                           shallow depth of field, 8K photorealistic"

          chart_data     → list of {label, value, color} if needs_chart is true, else null.
                           Use real relative values. color should be a hex code.
                           Provide 4–6 data points.

        Return ONLY the JSON object with string-integer keys.
    """)

    user_msg = f"OUTLINE:\n{outline_text}\n\nSOURCE MATERIAL:\n{source_text}"

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        state.enriched_context = json.loads(response.choices[0].message.content)
        log.info("ResearcherNode: enrichment complete")

    except (json.JSONDecodeError, ValueError) as exc:
        log.error("ResearcherNode failed: %s", exc)
        state.errors.append(f"ResearcherNode: {exc}")

    return state


# ╔══════════════════════════════════════════════╗
# ║  NODE 3 — DesignerNode                       ║
# ╚══════════════════════════════════════════════╝

def _enforce_char_limits(content: dict[str, Any], template_key: str) -> dict[str, Any]:
    """
    Hard-truncates any content field that exceeds the layout budget.
    Mutates and returns the content dict.
    """
    limits = LAYOUT_CHAR_LIMITS.get(template_key, {})
    for field, limit in limits.items():
        if field == "bullet_points":
            content[field] = [bp[:160] for bp in content.get(field, [])[:limit]]
        elif field == "timeline_steps":
            content[field] = [s[:80] for s in content.get(field, [])[:limit]]
        elif field in content and isinstance(content[field], str):
            if len(content[field]) > limit:
                log.warning("Designer: truncating '%s' from %d to %d chars",
                            field, len(content[field]), limit)
                content[field] = content[field][:limit].rsplit(" ", 1)[0] + "…"
    return content


def designer_node(state: PresentationState) -> PresentationState:
    """
    Merges research into per-slide content objects and enforces char budgets.
    Produces draft_layout_map: list of fully resolved slide dicts.
    """
    log.info("DesignerNode: mapping %d slides to layouts", len(state.outline or []))

    if not state.outline or not state.enriched_context:
        state.errors.append("DesignerNode: missing outline or enriched context")
        return state

    layout_map = []

    for slide_meta in state.outline:
        slide_num   = str(slide_meta["slide_number"])
        template    = slide_meta.get("suggested_template", TemplateKey.BULLET_LIST)
        research    = state.enriched_context.get(slide_num, {})

        # Pull rich content from research
        bullet_pts  = research.get("key_facts", [])
        stats       = research.get("statistics", [])
        summary     = research.get("summary", "")
        eyebrow_val = research.get("eyebrow", slide_meta.get("purpose", "Key Insight").replace("_", " ").title())
        section_val = research.get("section", eyebrow_val)

        # body_text: use the research summary if available, else join first 2 bullets
        body_text = summary if summary else (" ".join(bullet_pts[:2]) if bullet_pts else "")

        content: dict[str, Any] = {
            "headline":      slide_meta.get("title", ""),
            "subheadline":   slide_meta.get("theme", "")[:140] if slide_meta.get("theme") else None,
            "body_text":     body_text,
            "bullet_points": bullet_pts,
            "caption": " ".join(bullet_pts[:3]) if template in (
                TemplateKey.FULL_BLEED_IMAGE, TemplateKey.CHART_WITH_CAPTION) else None,
            "metric_value": str(stats[0]["value"]) + stats[0].get("unit", "") if stats else None,
            "metric_label": stats[0]["label"] if stats else None,
            "timeline_steps": bullet_pts[:4] if template == TemplateKey.TIMELINE_FOUR_STEPS else [],
            "eyebrow": eyebrow_val,
            "section": section_val,
            "kpis": [
                {
                    "label": k.get("label", "Metric"),
                    "value": str(k.get("value", "0")) + (k.get("unit") or ""),
                    "delta": k.get("delta"),
                    "trend": k.get("trend", "up")
                } for k in stats[:3]
            ]
        }

        # Enforce character budgets — no layout overflow
        content = _enforce_char_limits(content, template)

        # Build chart config if required
        chart_cfg = None
        chart_data_raw = research.get("chart_data")
        if slide_meta.get("needs_chart") and chart_data_raw:
            # Normalize chart_data: accept {label,value} or {label,value,color}
            series = []
            for item in chart_data_raw:
                series.append({
                    "label": str(item.get("label", "")),
                    "value": float(item.get("value", 0)),
                    "color": item.get("color") or None,
                })
            chart_cfg = {
                "chart_type":       "bar",
                "title":            slide_meta["title"],
                "x_axis_label":     None,
                "y_axis_label":     None,
                "show_legend":      True,
                "show_data_labels": True,
                "data_series":      series,
            }

        layout_map.append({
            "slide_id":      str(uuid.uuid4()),
            "slide_number":  slide_meta["slide_number"],
            "template_key":  template,
            "content":       content,
            "image_prompt":  research.get("image_prompt"),
            "chart_config":  chart_cfg,
            "needs_morph":   slide_meta["slide_number"] > 1,
        })

    state.draft_layout_map = layout_map
    log.info("DesignerNode: draft layout map with %d slides", len(layout_map))
    return state


# ╔══════════════════════════════════════════════╗
# ║  NODE 4 — ContractNode                       ║
# ╚══════════════════════════════════════════════╝

# JSON Schema for Structured Outputs — matches PresentationContract exactly
PRESENTATION_JSON_SCHEMA = {
    "name": "presentation_contract",
    "strict": True,
    "schema": {
        "type": "object",
        "required": ["metadata", "global_styles", "slides"],
        "additionalProperties": False,
        "properties": {
            "metadata": {
                "type": "object",
                "required": ["title", "subtitle", "author", "company", "aspect_ratio"],
                "additionalProperties": False,
                "properties": {
                    "title":        {"type": "string"},
                    "subtitle":     {"type": ["string", "null"]},
                    "author":       {"type": "string"},
                    "company":      {"type": ["string", "null"]},
                    "aspect_ratio": {"type": "string", "enum": ["16:9", "4:3"]},
                },
            },
            "global_styles": {
                "type": "object",
                "required": ["primary_color", "accent_color", "background_color", "font_family", "heading_font", "base_font_size"],
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
                    "required": ["slide_id", "template_key", "speaker_notes", "transition", "content", "visuals"],
                    "additionalProperties": False,
                    "properties": {
                        "slide_id":      {"type": "string"},
                        "template_key":  {"type": "string"},
                        "speaker_notes": {"type": ["string", "null"]},
                        "transition":    {"type": "string"},
                        "content": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["headline", "subheadline", "body_text", "bullet_points", "metric_value", "metric_label", "caption", "timeline_steps", "eyebrow", "section", "kpis"],
                            "properties": {
                                "headline":       {"type": "string"},
                                "subheadline":    {"type": ["string", "null"]},
                                "body_text":      {"type": ["string", "null"]},
                                "bullet_points":  {"type": "array", "items": {"type": "string"}},
                                "metric_value":   {"type": ["string", "null"]},
                                "metric_label":   {"type": ["string", "null"]},
                                "caption":        {"type": ["string", "null"]},
                                "timeline_steps": {"type": "array", "items": {"type": "string"}},
                                "eyebrow":        {"type": ["string", "null"]},
                                "section":        {"type": ["string", "null"]},
                                "kpis": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["label", "value", "delta", "trend"],
                                        "additionalProperties": False,
                                        "properties": {
                                            "label": {"type": "string"},
                                            "value": {"type": "string"},
                                            "delta": {"type": ["string", "null"]},
                                            "trend": {"type": "string", "enum": ["up", "down"]},
                                        },
                                    },
                                },
                            },
                        },
                        "visuals": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["image_prompt", "image_url", "morph_id", "chart_config", "icon_name"],
                            "properties": {
                                "image_prompt": {"type": ["string", "null"]},
                                "image_url":    {"type": ["string", "null"]},
                                "morph_id":     {"type": ["string", "null"]},
                                "chart_config": {
                                    "type": ["object", "null"],
                                    "additionalProperties": False,
                                    "required": ["chart_type", "title", "x_axis_label", "y_axis_label", "show_legend", "show_data_labels", "data_series"],
                                    "properties": {
                                        "chart_type": {"type": "string", "enum": ["bar", "line", "pie", "donut", "scatter"]},
                                        "title": {"type": "string"},
                                        "x_axis_label": {"type": ["string", "null"]},
                                        "y_axis_label": {"type": ["string", "null"]},
                                        "show_legend": {"type": "boolean"},
                                        "show_data_labels": {"type": "boolean"},
                                        "data_series": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["label", "value", "color"],
                                                "additionalProperties": False,
                                                "properties": {
                                                    "label": {"type": "string"},
                                                    "value": {"type": "number"},
                                                    "color": {"type": ["string", "null"]},
                                                },
                                            },
                                        },
                                    },
                                },
                                "icon_name":    {"type": ["string", "null"]},
                            },
                        },
                    },
                },
            },
        },
    },
}


def contract_node(state: PresentationState) -> PresentationState:
    """
    Locks the final presentation into the strict Pydantic schema using
    OpenAI Structured Outputs (response_format with json_schema).
    Implements a retry loop with self-correction on validation failure.
    """
    log.info("ContractNode: compiling final data contract")

    if not state.draft_layout_map:
        state.errors.append("ContractNode: no draft layout map available")
        return state

    layout_json = json.dumps(state.draft_layout_map, indent=2)
    prompt_text = state.user_prompt

    system_prompt = textwrap.dedent(f"""
        You are a JSON schema compiler. Given a draft layout map and original brief,
        compile the final PresentationContract JSON EXACTLY matching the provided schema.

        CRITICAL RULES:
          1. PRESERVE ALL CONTENT from the draft layout map. Do NOT summarize, shorten,
             or omit bullet_points, body_text, headline, or statistics.
          2. Copy every bullet from key_facts into bullet_points (5-7 per slide minimum).
          3. Use the draft body_text verbatim as the slide body_text — do not paraphrase.
          4. Choose brand colours and fonts matching the industry/tone of the brief.
             Use rich hex colours (e.g. #1A3D6E not #0000FF).
          5. Populate speaker_notes with 2 coaching sentences per slide.
          6. Assign morph_id values like "!!Hero", "!!Chart1", "!!Metric" to visuals.
          7. Set global_styles to match the deck brand identity.

        Today's date: {datetime.utcnow().strftime('%Y-%m-%d')}.
    """)

    last_error: str = ""

    for attempt in range(1, MAX_RETRIES + 1):
        user_content = f"BRIEF:\n{prompt_text}\n\nDRAFT LAYOUT MAP:\n{layout_json}"
        if last_error:
            user_content += f"\n\nPREVIOUS VALIDATION ERROR — CORRECT THIS:\n{last_error}"

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_content},
                ],
                temperature=0.2,
                response_format={
                    "type": "json_schema",
                    "json_schema": PRESENTATION_JSON_SCHEMA,
                },
            )

            raw_json = response.choices[0].message.content
            raw_dict = json.loads(raw_json)

            # Validate against Pydantic model
            contract = PresentationContract(**raw_dict)
            state.presentation = contract
            log.info("ContractNode: contract validated on attempt %d", attempt)
            return state

        except ValidationError as exc:
            last_error = str(exc)
            log.warning("ContractNode attempt %d: Pydantic validation error — %s", attempt, last_error[:200])
            state.retry_count += 1

        except json.JSONDecodeError as exc:
            last_error = f"JSON decode error: {exc}"
            log.warning("ContractNode attempt %d: JSON error — %s", attempt, last_error)
            state.retry_count += 1

    state.errors.append(f"ContractNode: failed after {MAX_RETRIES} retries. Last error: {last_error}")
    return state


# ╔══════════════════════════════════════════════╗
# ║  ROUTING LOGIC                               ║
# ╚══════════════════════════════════════════════╝

def _route_after_planner(state: PresentationState) -> Literal["researcher", "end_with_error"]:
    if state.outline:
        return "researcher"
    return "end_with_error"


def _route_after_researcher(state: PresentationState) -> Literal["designer", "end_with_error"]:
    if state.enriched_context:
        return "designer"
    return "end_with_error"


def _route_after_designer(state: PresentationState) -> Literal["contract", "end_with_error"]:
    if state.draft_layout_map:
        return "contract"
    return "end_with_error"


def _route_after_contract(state: PresentationState) -> Literal["end_success", "end_with_error"]:
    if state.presentation:
        return "end_success"
    return "end_with_error"


def _error_sink(state: PresentationState) -> PresentationState:
    log.error("Pipeline terminated with errors: %s", state.errors)
    return state


def _success_sink(state: PresentationState) -> PresentationState:
    slide_count = len(state.presentation.slides) if state.presentation else 0
    log.info("Pipeline complete — %d slides generated", slide_count)
    return state


# ╔══════════════════════════════════════════════╗
# ║  GRAPH ASSEMBLY                              ║
# ╚══════════════════════════════════════════════╝

def build_graph() -> StateGraph:
    graph = StateGraph(PresentationState)

    # Register nodes
    graph.add_node("planner",         planner_node)
    graph.add_node("researcher",      researcher_node)
    graph.add_node("designer",        designer_node)
    graph.add_node("contract",        contract_node)
    graph.add_node("end_with_error",  _error_sink)
    graph.add_node("end_success",     _success_sink)

    # Entry point
    graph.set_entry_point("planner")

    # Conditional edges with explicit routing functions
    graph.add_conditional_edges("planner",    _route_after_planner,
                                 {"researcher": "researcher", "end_with_error": "end_with_error"})
    graph.add_conditional_edges("researcher", _route_after_researcher,
                                 {"designer": "designer",    "end_with_error": "end_with_error"})
    graph.add_conditional_edges("designer",   _route_after_designer,
                                 {"contract": "contract",    "end_with_error": "end_with_error"})
    graph.add_conditional_edges("contract",   _route_after_contract,
                                 {"end_success": "end_success", "end_with_error": "end_with_error"})

    # Terminal nodes
    graph.add_edge("end_with_error", END)
    graph.add_edge("end_success",    END)

    return graph.compile()


# ╔══════════════════════════════════════════════╗
# ║  ENTRYPOINT                                  ║
# ╚══════════════════════════════════════════════╝

def run_pipeline(prompt: str, source_docs: list[str] | None = None) -> PresentationState:
    compiled = build_graph()
    initial_state = PresentationState(
        user_prompt=prompt,
        source_documents=source_docs or [],
    )
    final_output = compiled.invoke(initial_state)
    return PresentationState(**final_output)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="AI Presentation Brain")
    parser.add_argument("--prompt", required=True, help="Presentation brief")
    parser.add_argument("--output", default="presentation_contract.json",
                        help="Output JSON file path")
    args = parser.parse_args()

    result = run_pipeline(args.prompt)

    if result.presentation:
        output_path = args.output
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(result.presentation.model_dump_json(indent=2))
        print(f"\n✓ Contract written to: {output_path}")
        print(f"  Slides: {len(result.presentation.slides)}")
    else:
        print("\n✗ Pipeline failed. Errors:")
        for err in result.errors:
            print(f"  • {err}")
        sys.exit(1)
