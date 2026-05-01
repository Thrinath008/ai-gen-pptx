"""
AI Presentation Pipeline — Master Orchestrator
Ties Phase 1 (Brain), Phase 2 (DOM Calculator), Phase 3 (Compiler) together.

Usage:
    # Business / general deck:
    python orchestrate.py --prompt "Q3 Investor Update" --output deck.pptx

    # Teacher / education mode:
    python orchestrate.py --mode teacher --prompt "30-min lesson on Photosynthesis for Class 7" --output lesson.pptx
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import requests

log = logging.getLogger("orchestrator")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

DOM_CALCULATOR_URL = "http://localhost:3100/calculate-layout"


def _get_sidecar_path(base_output: str, suffix: str) -> Path:
    """Intelligently directs sidecars to the correct subfolder if organized structure exists."""
    base = Path(base_output)
    if base.parent.name == "pptx" and base.parent.parent.name == "outputs":
        subfolder = "md" if suffix.endswith(".md") else "json"
        target_dir = base.parent.parent / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / (base.stem + suffix)
    return base.with_suffix(suffix)


def run(prompt: str, output_path: str, source_docs: list[str] | None = None,
        mode: str = "business", school: str | None = None, 
        teacher: str | None = None, class_name: str | None = None) -> None:
    """
    End-to-end pipeline execution.
    mode: "business" (default) | "teacher"
    """
    start = time.perf_counter()

    # ── Phase 1: Brain ────────────────────────────────────────────────────────
    log.info("Phase 1: Running LangGraph brain… [mode=%s]", mode)

    sys.path.insert(0, str(Path(__file__).parent / "app" / "core"))

    if mode == "teacher":
        from edu_graph import run_edu_pipeline
        from models import EduConfig
        config = EduConfig(school_name=school, teacher_name=teacher, class_name=class_name)
        state = run_edu_pipeline(prompt, source_docs, config=config)
    else:
        try:
            from phase1_brain.graph import run_pipeline
        except ImportError:
            from graph import run_pipeline  # type: ignore
        state = run_pipeline(prompt, source_docs)


    if not state.presentation:
        log.error("Phase 1 failed: %s", state.errors)
        sys.exit(1)

    # Export Lesson Plan if available
    if mode == "teacher" and state.enriched_context and "lesson_plan_md" in state.enriched_context:
        lp_path = _get_sidecar_path(output_path, ".lesson_plan.md")
        lp_path.write_text(state.enriched_context["lesson_plan_md"], encoding="utf-8")
        log.info("Teacher Lesson Plan exported: %s", lp_path)

    contract_json = json.loads(state.presentation.model_dump_json())
    log.info("Phase 1 complete — %d slides", len(contract_json["slides"]))

    # Optionally save the contract for debugging
    contract_file = _get_sidecar_path(output_path, ".contract.json")
    contract_file.write_text(json.dumps(contract_json, indent=2), encoding="utf-8")
    log.info("Contract saved: %s", contract_file)

    # ── Phase 2: DOM Calculator ───────────────────────────────────────────────
    log.info("Phase 2: Calculating layout via headless browser…")

    try:
        response = requests.post(
            DOM_CALCULATOR_URL,
            json=contract_json,
            timeout=120,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        log.error(
            "Phase 2 failed: Cannot connect to DOM Calculator at %s. "
            "Is the Node.js server running?",
            DOM_CALCULATOR_URL,
        )
        sys.exit(1)
    except requests.exceptions.HTTPError as exc:
        log.error("Phase 2 HTTP error: %s — %s", exc, response.text[:400])
        sys.exit(1)

    coordinate_map = response.json()
    log.info("Phase 2 complete — %d slides mapped", len(coordinate_map.get("slides", [])))

    coord_file = _get_sidecar_path(output_path, ".coords.json")
    coord_file.write_text(json.dumps(coordinate_map, indent=2), encoding="utf-8")
    log.info("Coordinate map saved: %s", coord_file)

    # ── Phase 3: Compiler ─────────────────────────────────────────────────────
    log.info("Phase 3: Compiling PPTX…")

    try:
        from phase3_compiler.compiler import compile_presentation
    except ImportError:
        from compiler import compile_presentation  # type: ignore

    try:
        compile_presentation(coordinate_map, output_path)
    except RuntimeError as exc:
        log.error("Phase 3 failed: %s", exc)
        sys.exit(1)

    elapsed = time.perf_counter() - start
    log.info("✓ Pipeline complete in %.1fs — output: %s", elapsed, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI-to-PowerPoint Master Orchestrator")
    parser.add_argument("--prompt", required=True, help="Presentation brief / topic")
    parser.add_argument("--output", default="presentation.pptx", help="Output .pptx path")
    parser.add_argument("--docs",   nargs="*", default=[], help="Source document text files")
    parser.add_argument("--mode",   default="business", choices=["business", "teacher"],
                        help="Pipeline mode: 'business' (default) or 'teacher' for edu decks")
    
    # Edu-specific
    parser.add_argument("--school", help="School name for teacher mode")
    parser.add_argument("--teacher", help="Instructor name for teacher mode")
    parser.add_argument("--class-name", help="Class/Grade for teacher mode")

    args = parser.parse_args()

    source_docs = []
    for doc_path in args.docs:
        try:
            source_docs.append(Path(doc_path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            log.warning("Source doc not found: %s", doc_path)

    run(args.prompt, args.output, source_docs, mode=args.mode,
        school=args.school, teacher=args.teacher, class_name=args.class_name)
