# src/resume_tailor/tools/__init__.py
from pathlib import Path
from typing import Optional, Dict, Any
from crewai_tools import FileReadTool, MDXSearchTool, ScrapeWebsiteTool, SerperDevTool


def build_tools(
    resume_text_path: Optional[Path] = None,
    work_experience_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Build tool instances for the crew.
    """
    search_tool = SerperDevTool()
    scrape_tool = ScrapeWebsiteTool()

    tools = {
        "search_tool": search_tool,
        "scrape_tool": scrape_tool,
    }

    if resume_text_path:
        tools["read_resume"] = FileReadTool(file_path=str(resume_text_path))
        tools["semantic_search_resume"] = MDXSearchTool(mdx=str(resume_text_path))

    if work_experience_path:
        tools["read_workexp"] = FileReadTool(file_path=str(work_experience_path))
        tools["semantic_search_workexp"] = MDXSearchTool(mdx=str(work_experience_path))

    return tools
