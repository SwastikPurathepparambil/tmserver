import mimetypes
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from tmserver.helpers import _pdf_bytes_to_text, extract_json, resume_to_pdf

from .models import TailoredResume
from .crew import build_crew
from .tools import build_tools



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
