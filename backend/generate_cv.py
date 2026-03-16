#!/usr/bin/env python3
"""
Generate a clean PDF CV for Damir Imangulov from bio.txt.
Usage: python generate_cv.py [output.pdf]
"""
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

# ── Colour palette ────────────────────────────────────────────────────────────
BLUE   = colors.HexColor("#1d4ed8")
DARK   = colors.HexColor("#111827")
MUTED  = colors.HexColor("#6b7280")
LIGHT  = colors.HexColor("#f3f4f6")
RULE   = colors.HexColor("#e5e7eb")

# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle("name",
            fontName="Helvetica-Bold", fontSize=22, textColor=DARK,
            spaceAfter=1*mm, leading=26),
        "title": ParagraphStyle("title",
            fontName="Helvetica", fontSize=12, textColor=BLUE,
            spaceAfter=4*mm, leading=16),
        "contact": ParagraphStyle("contact",
            fontName="Helvetica", fontSize=8.5, textColor=MUTED,
            spaceAfter=1*mm, leading=12),
        "section": ParagraphStyle("section",
            fontName="Helvetica-Bold", fontSize=10, textColor=BLUE,
            spaceBefore=5*mm, spaceAfter=1.5*mm, leading=14,
            textTransform="uppercase", letterSpacing=0.8),
        "job_title": ParagraphStyle("job_title",
            fontName="Helvetica-Bold", fontSize=9.5, textColor=DARK,
            spaceBefore=3*mm, spaceAfter=0.5*mm, leading=13),
        "job_meta": ParagraphStyle("job_meta",
            fontName="Helvetica-Oblique", fontSize=8.5, textColor=MUTED,
            spaceAfter=1.5*mm, leading=12),
        "body": ParagraphStyle("body",
            fontName="Helvetica", fontSize=8.5, textColor=DARK,
            spaceAfter=1*mm, leading=13),
        "tech": ParagraphStyle("tech",
            fontName="Helvetica-Oblique", fontSize=8, textColor=MUTED,
            spaceAfter=1*mm, leading=12),
        "bullet": ParagraphStyle("bullet",
            fontName="Helvetica", fontSize=8.5, textColor=DARK,
            leftIndent=4*mm, leading=13),
    }


def rule(story):
    story.append(HRFlowable(width="100%", thickness=0.5, color=RULE, spaceAfter=1*mm))


def section_heading(story, text, styles):
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(text, styles["section"]))
    rule(story)


def bullets(story, items, styles):
    li = [ListItem(Paragraph(item.strip(), styles["bullet"]), bulletColor=BLUE,
                   leftIndent=8*mm, bulletIndent=2*mm) for item in items if item.strip()]
    story.append(ListFlowable(li, bulletType="bullet", bulletFontSize=6,
                              leftIndent=0, spaceBefore=0))


# ── Content builder ───────────────────────────────────────────────────────────
def build(bio_path: Path, styles: dict) -> list:
    text = bio_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    story = []

    # ── Header
    story.append(Paragraph("Damir Imangulov", styles["name"]))
    story.append(Paragraph("Solution Architect  ·  Senior Full-Stack Engineer", styles["title"]))
    story.append(Paragraph(
        "dimangulov@gmail.com  ·  linkedin.com/in/damir-imangulov-5b1346102  ·  "
        "github.com/dimangulov  ·  Sofia, Bulgaria",
        styles["contact"]))
    rule(story)

    def get_section(heading: str) -> list[str]:
        """Return lines belonging to a top-level section."""
        inside = False
        result = []
        for line in lines:
            if line.strip() == heading:
                inside = True
                continue
            if inside:
                if re.match(r'^[A-Z ]+$', line.strip()) and len(line.strip()) > 3:
                    break
                result.append(line)
        return result

    # ── Professional Summary
    section_heading(story, "Professional Summary", styles)
    in_summary = False
    for line in lines:
        if line.strip() == "PROFESSIONAL SUMMARY":
            in_summary = True
            continue
        if in_summary:
            if re.match(r'^[A-Z ]{4,}$', line.strip()):
                break
            if line.strip():
                story.append(Paragraph(line.strip(), styles["body"]))
    story.append(Spacer(1, 1*mm))

    # ── Core Competencies (two-column condensed)
    section_heading(story, "Core Competencies", styles)
    in_comp = False
    current_group = None
    comp_items: list[str] = []
    for line in lines:
        if line.strip() == "CORE COMPETENCIES":
            in_comp = True
            continue
        if in_comp:
            if re.match(r'^[A-Z ]{4,}$', line.strip()):
                break
            if line.strip().endswith(":"):
                if comp_items:
                    story.append(Paragraph(f"<b>{current_group}</b>", styles["body"]))
                    bullets(story, comp_items, styles)
                    comp_items = []
                current_group = line.strip().rstrip(":")
            elif line.strip().startswith("- "):
                comp_items.append(line.strip()[2:])
    if comp_items and current_group:
        story.append(Paragraph(f"<b>{current_group}</b>", styles["body"]))
        bullets(story, comp_items, styles)

    # ── Professional Experience
    section_heading(story, "Professional Experience", styles)
    in_exp = False
    job_lines: list[str] = []
    for line in lines:
        if line.strip() == "PROFESSIONAL EXPERIENCE":
            in_exp = True
            continue
        if in_exp:
            if line.strip() in ("EDUCATION", "CERTIFICATIONS", "NOTABLE PROJECTS"):
                break
            job_lines.append(line)

    # Parse individual jobs
    job_blocks: list[list[str]] = []
    current_block: list[str] = []
    for line in job_lines:
        if re.match(r'^.+—.+\(\d{4}', line):
            if current_block:
                job_blocks.append(current_block)
            current_block = [line]
        elif current_block:
            current_block.append(line)
    if current_block:
        job_blocks.append(current_block)

    for block in job_blocks:
        header = block[0].strip()
        # Split "Title — Company (dates)"
        m = re.match(r'^(.+?)\s*—\s*(.+?)\s*(\(\d{4}.*\))\s*$', header)
        if m:
            title_txt = m.group(1).strip()
            company_txt = m.group(2).strip()
            dates_txt = m.group(3).strip()
            story.append(Paragraph(f"{title_txt}  —  {company_txt}", styles["job_title"]))
            story.append(Paragraph(dates_txt, styles["job_meta"]))
        else:
            story.append(Paragraph(header, styles["job_title"]))

        job_bullets: list[str] = []
        tech_line = ""
        for line in block[1:]:
            stripped = line.strip()
            if stripped.startswith("- "):
                job_bullets.append(stripped[2:])
            elif stripped.startswith("Technologies:"):
                tech_line = stripped
        if job_bullets:
            bullets(story, job_bullets, styles)
        if tech_line:
            story.append(Paragraph(tech_line, styles["tech"]))

    # ── Notable Projects
    section_heading(story, "Notable Projects", styles)
    in_proj = False
    proj_block: list[str] = []
    for line in lines:
        if line.strip() == "NOTABLE PROJECTS":
            in_proj = True
            continue
        if in_proj:
            if line.strip() in ("LANGUAGES", "CONTACT", "EDUCATION"):
                break
            proj_block.append(line)

    for line in proj_block:
        stripped = line.strip()
        if stripped.startswith("Project:"):
            story.append(Paragraph(stripped[8:].strip(), styles["job_title"]))
        elif stripped.startswith("Technologies:"):
            story.append(Paragraph(stripped, styles["tech"]))
        elif stripped:
            story.append(Paragraph(stripped, styles["body"]))

    # ── Education & Certifications side by side (just sequential here)
    section_heading(story, "Education & Certifications", styles)
    for section_name in ("EDUCATION", "CERTIFICATIONS"):
        in_sec = False
        for line in lines:
            if line.strip() == section_name:
                in_sec = True
                continue
            if in_sec:
                if re.match(r'^[A-Z ]{4,}$', line.strip()):
                    break
                stripped = line.strip()
                if stripped.startswith("- "):
                    story.append(Paragraph("• " + stripped[2:], styles["bullet"]))
                elif stripped:
                    story.append(Paragraph(stripped,
                        styles["job_title"] if section_name == "EDUCATION" else styles["body"]))

    story.append(Spacer(1, 2*mm))
    return story


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    bio_path = Path(__file__).parent / "bio.txt"
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "damir_imangulov_cv.pdf"

    styles = make_styles()

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=18*mm,
        rightMargin=18*mm,
        topMargin=16*mm,
        bottomMargin=16*mm,
        title="Damir Imangulov — CV",
        author="Damir Imangulov",
    )

    story = build(bio_path, styles)
    doc.build(story)
    print(f"PDF written to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
