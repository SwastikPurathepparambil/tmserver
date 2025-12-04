from fastapi import FastAPI, HTTPException, status, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import List
from bson import ObjectId
import os
import uvicorn
from latest_ai_development.main import run as run_crew

import time
import asyncio

load_dotenv()  # loads OPENAI_API_KEY, etc.

app = FastAPI(title="latest_ai_development API")

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

# ========= Sample Route =========

@app.post("/run")
def run_endpoint(payload: RunPayload):

    # run_crew()

    print("workExperience:", payload.workExperience)
    print("jobLink:", payload.jobLink)

    if payload.resume:
        print("resume.name:", payload.resume.name)
        print("resume.type:", payload.resume.type)
        print("resume.size:", payload.resume.size)
        if payload.resume.base64:
            print("resume.base64 (first 80):", payload.resume.base64[:80], "...")
    
    # result = "Over the past five years, Agentic Artificial Intelligence (AI) " \
    # "has reached a significant level of maturity. AI systems are demonstrating human-like " \
    # "capabilities, understanding, reasoning, learning, and interacting in real-time. They " \
    # "have garnered widespread implementation in robotics, automation, and smart devices " \
    # "sectors, consequently leading to rapid growth and advancements in these fields."

    


    # return {"ok": True, "result": result}
    result = run_crew(
        topic=payload.jobLink or payload.topic,
        work_experience=payload.workExperience,
        resume_name=payload.resume.name if payload.resume else None,
        resume_mime=payload.resume.type if payload.resume else None,
        resume_base64=payload.resume.base64 if payload.resume else None,
    )
    return {"ok": True, "result": str(result)}

# ========= End of Sample Route =========

# ========= AUTH ROUTES =========
