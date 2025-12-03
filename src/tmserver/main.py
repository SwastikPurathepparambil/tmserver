import base64
import io
import mimetypes
import os
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pypdf import PdfReader

from .crew import build_crew
from .tools import build_tools


def _b64_to_bytes(data: str) -> bytes:
    """Accepts raw base64 or data URLs; returns decoded bytes."""
    if "," in data:  # handle "data:...;base64,XXXX"
        data = data.split(",", 1)[1]
    return base64.b64decode(data)


def _pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    """Extracts text from a PDF (best-effort)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    texts = []
    for page in reader.pages:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            pass
    return "\n".join(texts).strip()


def _extract_text_from_file(
    file_bytes: bytes,
    mime_type: Optional[str],
    filename: Optional[str]
) -> str:
    """Extract text from PDF or TXT files."""
    mime = (mime_type or "").lower()
    name = (filename or "").lower()
    
    # PDF handling
    if mime == "application/pdf" or name.endswith(".pdf"):
        return _pdf_bytes_to_text(file_bytes)
    
    # Plain text handling
    if mime == "text/plain" or name.endswith(".txt"):
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1")
    
    # Fallback: try PDF first, then text
    ext = mimetypes.guess_extension(mime_type or "") or ".pdf"
    if ext == ".pdf":
        return _pdf_bytes_to_text(file_bytes)
    
    return f"[{filename or 'resume'} uploaded as {mime_type or ext}; text extraction not supported]"


def run(
    topic: str,
    work_experience: Optional[str] = None,
    resume_name: Optional[str] = None,
    resume_mime: Optional[str] = None,
    resume_base64: Optional[str] = None,
) -> str:
    """
    Entry used by FastAPI. Ingests payload fields (job URL, work_experience text,
    and an optional base64 resume), builds ephemeral tooling, and runs the
    3-task pipeline. Nothing is persisted.
    """
    load_dotenv()

    # Inputs the YAML tasks reference
    github_url = os.getenv("GITHUB_URL", "https://github.com/joaomdmoura")
    personal_writeup = work_experience or os.getenv("PERSONAL_WRITEUP", "")

    with TemporaryDirectory() as td:
        tmpdir = Path(td)

        resume_text_path: Optional[Path] = None
        work_exp_path: Optional[Path] = None

        # ---- Decode resume (if provided) and extract text into a temp MDX ----
        if resume_base64:
            file_bytes = _b64_to_bytes(resume_base64)
            text = _extract_text_from_file(file_bytes, resume_mime, resume_name)

            resume_text_path = tmpdir / "resume_text.mdx"
            resume_text_path.write_text(text or "", encoding="utf-8")

        # ---- Save work_experience as temp MDX so tools can read/search it ----
        if personal_writeup:
            work_exp_path = tmpdir / "work_experience.mdx"
            work_exp_path.write_text(personal_writeup, encoding="utf-8")

        # ---- Build tools bound to these ephemeral files ----
        tools = build_tools(
            resume_text_path=resume_text_path,
            work_experience_path=work_exp_path,
        )

        # ---- Build the crew with all 3 tasks ----
        crew = build_crew(
            tool_instances=tools,
            task_names=["research_task", "profile_task", "resume_strategy_task"],
        )

        # ---- Provide inputs referenced in tasks.yaml ----
        inputs = {
            "job_posting_url": topic,
            "github_url": github_url,
            "personal_writeup": personal_writeup,
        }

        result = crew.kickoff(inputs=inputs)
        return str(result)
