import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException #used for error handling
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Extra
from typing import Optional

from .main import run as run_crew
from .main import run_interview_prep  #cleaner 

import time
import asyncio

load_dotenv()  # loads OPENAI_API_KEY, etc.

app = FastAPI(title="Resume Tailor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Resume(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    size: Optional[int] = None
    base64: Optional[str] = None

class RunPayload(BaseModel):
    workExperience: Optional[str] = None
    jobLink: Optional[str] = None
    resume: Optional[Resume] = None

    class Config:
        extra = Extra.allow  # keep any unmodeled extras if they appear


@app.get("/")
def root():
    return {"status": "ok", "service": "Resume Tailor API"} # health endpoint 


@app.post("/run")
def run_endpoint(payload: RunPayload):
    """
    Get tailored resume with ORIGINAL/SUGGESTED comparisons.
    
    Input: resume (PDF/TXT), job link, optional work experience
    Output: Section-by-section comparison with improvement suggestions
    """
    if not payload.jobLink:
        raise HTTPException(status_code=400, detail="jobLink is required")

    print("=== Resume Tailoring Request ===")
    print("jobLink:", payload.jobLink)
    print("workExperience:", payload.workExperience[:100] if payload.workExperience else None)

    if payload.resume:
        print("resume.name:", payload.resume.name)
        print("resume.type:", payload.resume.type)
        print("resume.size:", payload.resume.size)
    try:  
        result = run_crew(
            topic=payload.jobLink,
            work_experience=payload.workExperience,
            resume_name=payload.resume.name if payload.resume else None,
            resume_mime=payload.resume.type if payload.resume else None,
            resume_base64=payload.resume.base64 if payload.resume else None,
        )
        return {"ok": True, "result": str(result)}
    
    except Exception as e:
        print(f"Error in /run: {e}")
        raise HTTPException(status_code=500, detail=str(e))  #error handling



@app.post("/interview-prep")
def interview_prep_endpoint(payload: RunPayload):
    """
    Get interview preparation materials.
    
    Input: resume (PDF/TXT), job link, optional work experience
    Output: Likely interview questions with answer hints, elevator pitch, keywords
    """
    if not payload.jobLink:
        raise HTTPException(status_code=400, detail="jobLink is required")

    print("=== Interview Prep Request ===")
    print("jobLink:", payload.jobLink)
    print("workExperience:", payload.workExperience[:100] if payload.workExperience else None)

    if payload.resume:
        print("resume.name:", payload.resume.name)
        print("resume.type:", payload.resume.type)
        print("resume.size:", payload.resume.size)

    try:
        result = run_interview_prep(
            topic=payload.jobLink,
            work_experience=payload.workExperience,
            resume_name=payload.resume.name if payload.resume else None,
            resume_mime=payload.resume.type if payload.resume else None,
            resume_base64=payload.resume.base64 if payload.resume else None,
        )
        return {"ok": True, "result": str(result)}
    
    except Exception as e:
        print(f"Error in /interview-prep: {e}")
        raise HTTPException(status_code=500, detail=str(e))