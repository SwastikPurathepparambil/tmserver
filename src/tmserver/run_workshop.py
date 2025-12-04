import json
import mimetypes
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from dotenv import load_dotenv

from .helpers import _pdf_bytes_to_text, extract_json
from .tools import build_tools
from .crew import build_crew
from .models import WorkshopResponse, WorkshopResponseContext


def run_workshop_pipeline(
    workshop_focus: Optional[str],
    job_link: Optional[str] = None,
    work_experience: Optional[str] = None,
    resume_bytes: Optional[bytes] = None,
    resume_mime: Optional[str] = None,
    resume_name: Optional[str] = None,
) -> WorkshopResponse:
    """
    End-to-end pipeline to generate resume workshop questions.

    Returns a WorkshopResponse Pydantic model:

        {
          "questions": [...],
          "context": {
            "resumeName": "...",
            "workshopFocus": "...",
            "jobLink": "...",
            "hasExtraNotes": true/false
          }
        }
    """
    load_dotenv()

    personal_writeup = work_experience or os.getenv("PERSONAL_WRITEUP", "")

    with TemporaryDirectory() as td:
        tmpdir = Path(td)

        resume_text_path: Optional[Path] = None
        work_exp_path: Optional[Path] = None

        # 1) Decode the uploaded resume and extract text for tools
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

        # 2) Save work experience text as MDX (if provided or from env)
        if personal_writeup:
            work_exp_path = tmpdir / "work_experience.mdx"
            work_exp_path.write_text(personal_writeup, encoding="utf-8")

        # 3) Build tools (same pattern as tailoring pipeline)
        tools = build_tools(
            resume_text_path=resume_text_path,
            work_experience_path=work_exp_path,
        )

        # 4) Build the crew for "resume workshop" mode
        #    Make sure your crew/tasks know to return JSON with a `questions` key.
        crew = build_crew(
            tool_instances=tools,
            task_names=["resume_workshop_questions_task"],
        )

        # 5) Kick off the crew. Your task prompt should use these fields.
        inputs = {
            "workshop_focus": workshop_focus or "",
            "job_posting_url": job_link or "",
            "personal_writeup": personal_writeup,
        }

        raw = crew.kickoff(inputs=inputs)
        raw_str = str(raw)

        # LLM may wrap JSON in ```json fences; extract just the JSON
        clean_json = extract_json(raw_str)

        # Expect JSON like: { "questions": ["Q1", "Q2", ...] }
        parsed = json.loads(clean_json)
        questions = parsed.get("questions") or []

        context = WorkshopResponseContext(
            resumeName=resume_name,
            workshopFocus=workshop_focus,
            jobLink=job_link,
            hasExtraNotes=bool(personal_writeup.strip()),
        )

        return WorkshopResponse(
            questions=questions,
            context=context,
        )
