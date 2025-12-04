import base64
import io
import mimetypes
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pypdf import PdfReader

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    ListFlowable,
    ListItem,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

from io import BytesIO

from .models import TailoredResume
from .crew import build_crew
from .tools import build_tools


# ----------------------------------------------------------------------
# Jinja / Templates
# ----------------------------------------------------------------------

# Folder that contains your Jinja2 HTML templates (e.g. "resume.html")
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


# ----------------------------------------------------------------------
# PDF / Text Helpers
# ----------------------------------------------------------------------

def _pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    """
    Best-effort text extraction from a PDF.

    Note:
        - Relies on pypdf's .extract_text(), which is not perfect but works
          for many text-based PDFs.
        - Silently skips pages that raise errors during extraction.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    texts: List[str] = []

    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            # If a page can't be parsed, just skip it and keep going
            continue

    return "\n".join(texts).strip()


def b64_to_bytes(data: str) -> bytes:
    """
    Decode a base64 string into bytes.

    Supports both:
      - Pure base64: "AAAA..."
      - Data URLs: "data:application/pdf;base64,AAAA..."

    Args:
        data: Base64 data, possibly with a "data:...;base64," prefix.

    Returns:
        Raw decoded bytes.
    """
    if "," in data:  # handle "data:...;base64,XXXX"
        data = data.split(",", 1)[1]
    return base64.b64decode(data)


def extract_json(text: str) -> str:
    """
    Extract a JSON object string from raw text, optionally wrapped in
    ```json ... ``` fences.

    This is useful when LLM output comes back as:

        ```json
        { "foo": "bar" }
        ```

    or just raw:

        { "foo": "bar" }

    Args:
        text: The raw text that may contain JSON.

    Returns:
        A substring that starts with '{' and ends with '}', or the input
        string if no fences are present.
    """
    text = text.strip()

    # If it looks like fenced code, try to pull out the JSON body
    if text.startswith("```"):
        # Split on backticks: e.g. ["", "json\n{...}", ""]
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            # Case 1: the chunk itself is pure JSON
            if p.startswith("{") and p.endswith("}"):
                return p
            # Case 2: begins with "json" then JSON
            if p.startswith("json"):
                json_part = p[len("json"):].strip()
                if json_part.startswith("{") and json_part.endswith("}"):
                    return json_part

    # Otherwise assume it's already plain JSON
    return text


# ----------------------------------------------------------------------
# HTML Rendering (optional)
# ----------------------------------------------------------------------

def render_resume_html(resume: TailoredResume) -> str:
    """
    Render a TailoredResume object into HTML using Jinja2.

    This expects there to be a "resume.html" file in TEMPLATES_DIR
    that uses the `resume` context variable.
    """
    template = env.get_template("resume.html")
    return template.render(resume=resume)


# If you want to generate a PDF from the HTML instead of using reportlab,
# you can use WeasyPrint as shown below.
#
# from weasyprint import HTML
#
# def html_to_pdf(html: str) -> bytes:
#     """
#     Convert HTML markup into a PDF using WeasyPrint.
#
#     Args:
#         html: Valid HTML string.
#
#     Returns:
#         PDF as raw bytes.
#     """
#     return HTML(string=html).write_pdf()


# ----------------------------------------------------------------------
# ReportLab PDF Rendering
# ----------------------------------------------------------------------

def resume_to_pdf(resume: Dict[str, Any]) -> bytes:
    """
    Render a TailoredResume-like dictionary into a nicely formatted one-page PDF.

    Expected shape (simplified):

        {
          "contact": {
              "name": "...",
              "email": "...",
              "phone": "...",
              "location": "...",
              "links": ["...", ...]
          },
          "headline": "Some role / specialization headline",
          "summary": "Optional profile summary",
          "sections": [
              {
                  "title": "Education",
                  "items": [...]
              },
              {
                  "title": "Experience",
                  "items": [...]
              },
              {
                  "title": "Projects",
                  "items": [...]
              },
              ...
          ]
        }

    Args:
        resume: A dict version of TailoredResume (e.g. from model_dump()).

    Returns:
        PDF as raw bytes.
    """

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()

    # ---------- Paragraph styles ----------

    name_style = ParagraphStyle(
        "Name",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        alignment=TA_LEFT,
        spaceAfter=4,
    )

    contact_style = ParagraphStyle(
        "Contact",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        alignment=TA_LEFT,
        spaceAfter=8,
    )

    headline_style = ParagraphStyle(
        "Headline",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        spaceAfter=6,
    )

    summary_style = ParagraphStyle(
        "Summary",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        spaceAfter=10,
    )

    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=12,
        leading=14,
        spaceBefore=10,
        spaceAfter=4,
    )

    item_title_style = ParagraphStyle(
        "ItemTitle",
        parent=styles["Normal"],
        fontSize=10.5,
        leading=13,
        spaceBefore=2,
        spaceAfter=0,
    )

    meta_line_style = ParagraphStyle(
        "MetaLine",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        spaceAfter=2,
    )

    bullet_style = ParagraphStyle(
        "Bullet",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
    )

    story: List[Any] = []

    # ---------- Header: name + contact ----------

    contact = resume.get("contact", {}) or {}
    name = contact.get("name") or "Anonymous Candidate"
    story.append(Paragraph(name, name_style))

    # Build single-line contact string: email · phone · location · links
    contact_parts: List[str] = []
    if contact.get("email"):
        contact_parts.append(contact["email"])
    if contact.get("phone"):
        contact_parts.append(contact["phone"])
    if contact.get("location"):
        contact_parts.append(contact["location"])

    links = contact.get("links") or []
    contact_parts.extend(str(link) for link in links if link)

    if contact_parts:
        contact_line = " · ".join(contact_parts)
        story.append(Paragraph(contact_line, contact_style))

    # ---------- Headline + Summary ----------

    headline = resume.get("headline")
    if headline:
        story.append(Paragraph(headline, headline_style))

    summary = resume.get("summary")
    if summary:
        story.append(Paragraph(summary, summary_style))

    # Small spacer before sections
    story.append(Spacer(1, 4))

    # ---------- Sections (Education, Experience, Projects, etc.) ----------

    sections = resume.get("sections", []) or []

    def find_section(title: str) -> Optional[Dict[str, Any]]:
        """Find a section by title, case-insensitive."""
        for s in sections:
            if s.get("title", "").lower() == title.lower():
                return s
        return None

    # Enforce Education > Experience > Projects order, then any remaining sections
    ordered_sections: List[Dict[str, Any]] = []
    for key in ("Education", "Experience", "Projects"):
        section = find_section(key)
        if section:
            ordered_sections.append(section)

    # Add any other sections that weren't already included
    for s in sections:
        if s not in ordered_sections:
            ordered_sections.append(s)

    # Render each section + its items
    for section in ordered_sections:
        title = section.get("title", "")
        items = section.get("items") or []

        if not items:
            continue

        story.append(Paragraph(title.upper(), section_title_style))

        for item in items:
            lower_title = title.lower()

            if lower_title == "education":
                _render_education_item(
                    story=story,
                    item=item,
                    item_title_style=item_title_style,
                    meta_line_style=meta_line_style,
                    bullet_style=bullet_style,
                )

            elif lower_title == "experience":
                _render_experience_item(
                    story=story,
                    item=item,
                    item_title_style=item_title_style,
                    meta_line_style=meta_line_style,
                    bullet_style=bullet_style,
                )

            else:
                # Projects or any additional custom section
                _render_generic_item(
                    story=story,
                    item=item,
                    item_title_style=item_title_style,
                    meta_line_style=meta_line_style,
                    bullet_style=bullet_style,
                )

            # Small space between items
            story.append(Spacer(1, 4))

    # Build PDF
    doc.build(story)
    return buffer.getvalue()


def _render_education_item(
    story: List[Any],
    item: Dict[str, Any],
    item_title_style: ParagraphStyle,
    meta_line_style: ParagraphStyle,
    bullet_style: ParagraphStyle,
) -> None:
    """Render a single 'Education' item into the story."""
    institution = item.get("institution", "")
    degree = item.get("degree", "")
    loc = item.get("location") or ""
    grad = item.get("graduation") or ""

    line_main = f"<b>{institution}</b>"
    if degree:
        line_main += f" — {degree}"

    story.append(Paragraph(line_main, item_title_style))

    meta_parts: List[str] = []
    if loc:
        meta_parts.append(loc)
    if grad:
        meta_parts.append(grad)
    if meta_parts:
        story.append(Paragraph(" · ".join(meta_parts), meta_line_style))

    coursework = item.get("coursework") or []
    if coursework:
        cw_text = "Relevant coursework: " + ", ".join(coursework)
        story.append(Paragraph(cw_text, bullet_style))


def _render_experience_item(
    story: List[Any],
    item: Dict[str, Any],
    item_title_style: ParagraphStyle,
    meta_line_style: ParagraphStyle,
    bullet_style: ParagraphStyle,
) -> None:
    """Render a single 'Experience' item into the story."""
    role = item.get("role", "")
    company = item.get("company", "")
    loc = item.get("location") or ""
    start = item.get("start_date") or ""
    end = item.get("end_date") or ""

    main_line = f"<b>{role}</b>"
    if company:
        main_line += f" · {company}"
    story.append(Paragraph(main_line, item_title_style))

    meta_parts: List[str] = []
    if loc:
        meta_parts.append(loc)

    if start or end:
        date_str = f"{start} — {end}"
        if date_str.strip():
            meta_parts.append(date_str)

    if meta_parts:
        story.append(Paragraph(" · ".join(meta_parts), meta_line_style))

    bullets = item.get("bullets") or []
    if bullets:
        bullet_items = [
            ListItem(Paragraph(b, bullet_style), leftIndent=10)
            for b in bullets
        ]
        story.append(
            ListFlowable(
                bullet_items,
                bulletType="bullet",
                start="•",
                leftIndent=15,
                bulletIndent=5,
            )
        )


def _render_generic_item(
    story: List[Any],
    item: Dict[str, Any],
    item_title_style: ParagraphStyle,
    meta_line_style: ParagraphStyle,
    bullet_style: ParagraphStyle,
) -> None:
    """
    Render a generic item (e.g. Project or custom section).

    Expected keys:
        - name:        Project or item name
        - tech_stack:  List of technologies used
        - bullets:     List of bullet points describing the work
    """
    name_ = item.get("name", "")
    tech_stack = item.get("tech_stack") or []
    bullets = item.get("bullets") or []

    if name_:
        story.append(Paragraph(f"<b>{name_}</b>", item_title_style))

    if tech_stack:
        tech_line = "Tech: " + ", ".join(str(t) for t in tech_stack)
        story.append(Paragraph(tech_line, meta_line_style))

    if bullets:
        bullet_items = [
            ListItem(Paragraph(b, bullet_style), leftIndent=10)
            for b in bullets
        ]
        story.append(
            ListFlowable(
                bullet_items,
                bulletType="bullet",
                start="•",
                leftIndent=15,
                bulletIndent=5,
            )
        )


# ----------------------------------------------------------------------
# Main Tailoring Pipeline
# ----------------------------------------------------------------------

def run_tailor_pipeline(
    topic: str,
    work_experience: Optional[str] = None,
    resume_bytes: Optional[bytes] = None,
    resume_mime: Optional[str] = None,
) -> Dict[str, Any]:
    """
    End-to-end pipeline to:
      1. Load env + defaults
      2. (Optionally) parse an uploaded resume into text (MDX)
      3. (Optionally) save user-provided work_experience as MDX
      4. Build tools + crew
      5. Run the crew to produce a TailoredResume JSON
      6. Convert that TailoredResume into a PDF
      7. Return PDF bytes + a suggested filename

    Args:
        topic:
            Treated as "job_posting_url" or a generic topic string that the
            downstream tasks use to tailor the resume.
        work_experience:
            Optional free-form text describing the candidate's background.
            If omitted, falls back to PERSONAL_WRITEUP from environment.
        resume_bytes:
            Optional resume file as raw bytes (ideally PDF).
        resume_mime:
            MIME type of the uploaded resume (e.g. "application/pdf").

    Returns:
        {
          "pdf_bytes": <PDF as bytes>,
          "filename":  "<suggested_filename>.pdf"
        }
    """
    load_dotenv()

    github_url = os.getenv("GITHUB_URL", "https://github.com/joaomdmoura")
    personal_writeup = work_experience or os.getenv("PERSONAL_WRITEUP", "")

    with TemporaryDirectory() as td:
        tmpdir = Path(td)

        resume_text_path: Optional[Path] = None
        work_exp_path: Optional[Path] = None

        # 1) Decode the uploaded resume and extract text
        if resume_bytes:
            # Guess extension from MIME type; default to .pdf
            ext = mimetypes.guess_extension(resume_mime or "") or ".pdf"
            resume_path = tmpdir / f"resume{ext}"
            resume_path.write_bytes(resume_bytes)

            # If it's a PDF, attempt text extraction, otherwise leave a note
            if (resume_mime or "").lower() == "application/pdf" or ext == ".pdf":
                text = _pdf_bytes_to_text(resume_bytes)
            else:
                text = (
                    f"[Resume uploaded as {resume_mime or ext}; "
                    f"text extraction not supported]"
                )

            resume_text_path = tmpdir / "resume_text.mdx"
            resume_text_path.write_text(text or "", encoding="utf-8")

        # 2) Save work experience text as MDX
        if personal_writeup:
            work_exp_path = tmpdir / "work_experience.mdx"
            work_exp_path.write_text(personal_writeup, encoding="utf-8")

        # 3) Build tools
        tools = build_tools(
            resume_text_path=resume_text_path,
            work_experience_path=work_exp_path,
        )

        # 4) Build the crew in "resume tailoring" mode
        crew = build_crew(
            tool_instances=tools,
            task_names=["research_task", "profile_task", "resume_strategy_task"],
        )

        # 5) Start the crew kickoff
        inputs = {
            "job_posting_url": topic,
            "github_url": github_url,
            "personal_writeup": personal_writeup,
        }

        raw = crew.kickoff(inputs=inputs)
        raw_str = str(raw)

        # LLM may wrap JSON in ```json fences; extract just the JSON
        clean_json = extract_json(raw_str)

        # Parse into a TailoredResume instance using Pydantic
        tailored = TailoredResume.model_validate_json(clean_json)

        # 6) Render the final PDF
        pdf_bytes = resume_to_pdf(tailored.model_dump())

        # Generate a safe filename from the headline
        safe_headline = (tailored.headline or "tailored_resume").replace(" ", "_").lower()
        filename = f"{safe_headline}.pdf"

        return {
            "pdf_bytes": pdf_bytes,
            "filename": filename,
            # Optionally return the TailoredResume object (debugging)
            # "tailored": tailored,
        }
