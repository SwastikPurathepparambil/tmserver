from fastapi import FastAPI, HTTPException, status, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import List
from bson import ObjectId
import os
import uvicorn

from tmserver.models import UserResponse
from tmserver.auth import verify_google_token, create_access_token, get_current_user_id, optional_get_current_user_id
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


# ========= Sample Route =========

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

@app.post("/auth/google")
async def google_login(google_token: dict, response: Response, db: Database = Depends(get_db)):
    user_info = await verify_google_token(google_token["token"])
    
    now = datetime.utcnow()
    existing = await db.users_set.find_one({"google_sub": user_info["google_sub"]})

    if existing:

        await db.users_set.update_one(
            {"google_sub": user_info["google_sub"]},
            {"$set": {"last_login_at": now}}
        )

        user_id = str(existing["_id"])
    else:
        result = await db.users_set.insert_one(
            {
                "google_sub": user_info["google_sub"],
                "email": user_info["email"],
                "created_at": now,
                "last_login_at": now
            }
        )
        user_id = str(result.inserted_id)


    token = create_access_token({"sub": user_id})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=24 * 3600
    )
    return {
        "user": 
        {
        "id": user_id,
        "email": user_info["email"]
        }
    }

@app.get("/auth/me")
async def get_me(user_id: str | None = Depends(optional_get_current_user_id), db: Database = Depends(get_db)):
    if user_id is None:
        return None
    
    user = await db.users_set.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Not Found")

    return UserResponse(
        id=str(user["_id"]),
        email=user["email"],
        created_at=user["created_at"],
        last_login_at=user["last_login_at"],
    )

