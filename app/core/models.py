"""
Enterprise Presentation Pipeline — Pydantic Data Contracts
All shared state types for the LangGraph multi-agent brain.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────
# Enumerations
# ──────────────────────────────────────────────

class AspectRatio(str, Enum):
    WIDESCREEN = "16:9"
    STANDARD   = "4:3"


class TransitionType(str, Enum):
    MORPH = "morph"
    FADE  = "fade"
    NONE  = "none"


class TemplateKey(str, Enum):
    # ── Business / General layouts ──────────────
    TITLE_HERO              = "title_hero"
    TWO_COL_IMAGE_RIGHT     = "two_col_image_right"
    TWO_COL_IMAGE_LEFT      = "two_col_image_left"
    LARGE_METRIC_HERO       = "large_metric_hero"
    TIMELINE_FOUR_STEPS     = "timeline_four_steps"
    FULL_BLEED_IMAGE        = "full_bleed_image"
    THREE_COLUMN_GRID       = "three_column_grid"
    BULLET_LIST             = "bullet_list"
    CHART_WITH_CAPTION      = "chart_with_caption"
    SECTION_DIVIDER         = "section_divider"
    EXECUTIVE_BRIEF         = "executive_brief"
    DATA_INSIGHT            = "data_insight"
    # ── Education / Teacher layouts ─────────────
    LEARNING_OBJECTIVES     = "learning_objectives"
    HOOK_SLIDE              = "hook_slide"
    ACTIVITY_SLIDE          = "activity_slide"
    QUIZ_SLIDE              = "quiz_slide"
    SUMMARY_RECAP           = "summary_recap"


class ChartType(str, Enum):
    BAR         = "bar"
    LINE        = "line"
    PIE         = "pie"
    DONUT       = "donut"
    SCATTER     = "scatter"


# ──────────────────────────────────────────────
# Nested sub-models
# ──────────────────────────────────────────────

class KPI(BaseModel):
    label: str
    value: str
    delta: Optional[str] = None
    trend: Optional[str] = "up"  # "up" or "down"


class DataPoint(BaseModel):
    label: str = Field(..., description="Category label for the data point.")
    value: float = Field(..., description="Numeric value for the data point.")
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class ChartConfig(BaseModel):
    chart_type: ChartType
    title: str
    x_axis_label: Optional[str] = None
    y_axis_label: Optional[str] = None
    data_series: list[DataPoint] = Field(..., min_length=1)
    show_legend: bool = True
    show_data_labels: bool = False


class QuizQuestion(BaseModel):
    question: str
    options: list[str] = Field(default_factory=list, description="A/B/C/D options")
    correct_index: int = Field(0, description="0-based index of correct option")
    question_type: str = Field("mcq", description="mcq | true_false")


class SlideContent(BaseModel):
    headline: str = Field(..., max_length=120)
    subheadline: Optional[str] = Field(None, max_length=160)
    body_text: Optional[str] = Field(None, max_length=800)
    bullet_points: list[str] = Field(default_factory=list, max_length=8)
    metric_value: Optional[str] = Field(None, max_length=30,
        description="Large KPI value, e.g. '$4.2B' or '97%'")
    metric_label: Optional[str] = Field(None, max_length=80)
    caption: Optional[str] = Field(None, max_length=200)
    # Ordered list of step labels for timeline layouts
    timeline_steps: list[str] = Field(default_factory=list, max_length=4)
    # Business layout fields
    eyebrow: Optional[str] = Field(None, max_length=50)
    section: Optional[str] = Field(None, max_length=50)
    kpis: list[KPI] = Field(default_factory=list, max_length=3)
    # Education-specific fields
    objectives: list[str] = Field(default_factory=list, max_length=5,
        description="Learning objectives starting with action verbs")
    activity_prompt: Optional[str] = Field(None, max_length=400,
        description="Activity or discussion prompt for students")
    quiz_questions: list[QuizQuestion] = Field(default_factory=list, max_length=5,
        description="MCQ or True/False questions for the quiz slide")
    hook_fact: Optional[str] = Field(None, max_length=200,
        description="Shocking fact, question, or hook statement")

    @field_validator("bullet_points", mode="before")
    @classmethod
    def _cap_bullet_length(cls, v: list[str]) -> list[str]:
        return [bp[:160] for bp in v]


class SlideVisuals(BaseModel):
    image_prompt: Optional[str] = Field(None, max_length=500,
        description="DALL-E / Midjourney prompt for background or feature image.")
    image_url: Optional[str] = None          # resolved after asset-fetch stage
    chart_config: Optional[ChartConfig] = None
    icon_name: Optional[str] = None          # maps to SVG asset library key
    morph_id: Optional[str] = Field(None,
        description="Shared !!name tag for PowerPoint Morph transitions.")


class Slide(BaseModel):
    slide_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    template_key: TemplateKey
    speaker_notes: Optional[str] = Field(None, max_length=1000)
    content: SlideContent
    visuals: SlideVisuals = Field(default_factory=SlideVisuals)
    transition: TransitionType = TransitionType.MORPH


class GlobalStyles(BaseModel):
    primary_color:   str = Field("#0F2D5E", pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color:    str = Field("#E8514A", pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str = Field("#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    font_family:     str = "Inter"
    heading_font:    str = "Playfair Display"
    base_font_size:  int = Field(16, ge=10, le=24)


class PresentationMetadata(BaseModel):
    title:        str
    subtitle:     Optional[str] = None
    author:       str = "AI Pipeline"
    company:      Optional[str] = None
    school_name:  Optional[str] = None
    class_name:   Optional[str] = None
    aspect_ratio: AspectRatio = AspectRatio.WIDESCREEN
    created_at:   Optional[str] = None


# ──────────────────────────────────────────────
# Master Data Contract
# ──────────────────────────────────────────────

class PresentationContract(BaseModel):
    """
    Final validated artifact from the ContractNode.
    This exact structure is serialised to JSON and forwarded to
    the Node.js headless renderer (Phase 2).
    """
    metadata:      PresentationMetadata
    global_styles: GlobalStyles = Field(default_factory=GlobalStyles)
    slides:        list[Slide] = Field(..., min_length=1)


# ──────────────────────────────────────────────
# LangGraph Shared State
# ──────────────────────────────────────────────

class EduConfig(BaseModel):
    school_name: Optional[str] = Field(None, description="Name of the school/college")
    school_logo_url: Optional[str] = Field(None, description="URL to school logo PNG/SVG")
    teacher_name: Optional[str] = Field(None, description="Name of the instructor")
    class_name: Optional[str] = Field(None, description="Grade/Section, e.g. 'Class 7-B'")


class PresentationState(BaseModel):
    """
    The single mutable state object passed through every LangGraph node.
    Each node reads what it needs and writes back its output key.
    """
    # ── Input ──────────────────────────────────
    user_prompt:       str
    source_documents:  list[str] = Field(default_factory=list)
    mode:              str = Field("business", description="business | teacher")

    # ── Education context (teacher mode only) ──
    edu_context: Optional[dict[str, Any]] = Field(None,
        description="Parsed teacher context: topic, grade, subject, duration, purpose, style")
    edu_config:  EduConfig = Field(default_factory=EduConfig)

    # ── Intermediate artifacts ──────────────────
    outline:           Optional[list[dict[str, Any]]] = None
    enriched_context:  Optional[dict[str, Any]] = None
    draft_layout_map:  Optional[list[dict[str, Any]]] = None

    # ── Final output ────────────────────────────
    presentation:      Optional[PresentationContract] = None

    # ── Control ─────────────────────────────────
    retry_count:       int = 0
    errors:            list[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
