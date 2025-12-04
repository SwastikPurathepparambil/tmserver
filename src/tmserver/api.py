from contextlib import asynccontextmanager
from datetime import datetime
import io
import os
import time
import asyncio
from typing import Dict, Any, Optional, List
import base64

from bson import ObjectId, Binary
from fastapi import FastAPI, HTTPException, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

from tmserver.db import get_database, Database, connect_to_db_mongo, disconnect_mongo
from tmserver.models import TailorPayload, UserResponse, WorkshopRequest, WorkshopResponse
from tmserver.auth import (
    verify_google_token,
    create_access_token,
    get_current_user_id,
    optional_get_current_user_id,
)
from tmserver.run_tailor import run_tailor_pipeline
from tmserver.run_workshop import run_workshop_pipeline
from tmserver.helpers import b64_to_bytes

# load_dotenv()  # loads OPENAI_API_KEY, etc.
ENV = os.getenv("ENVIRONMENT", "dev")
IS_PROD = ENV == "prod"

def get_db() -> Database:
    return get_database()


# ========= CONNECTION SETUP ========
# Database connection events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_db_mongo()
    try:
        # App runs here
        yield
    finally:
        # Shutdown
        await disconnect_mongo()

app = FastAPI(title="latest_ai_development API", lifespan=lifespan)

origins = [
    "http://localhost:5173",
    "https://tailormake-git-main-swastiks-projects-db4411ca.vercel.app", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # must be explicit when using credentials
    allow_credentials=True,       # using cookies
    allow_methods=["*"],          
    allow_headers=["*"],          
)

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
        secure=IS_PROD,
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

@app.post("/auth/logout")
def logout(response: Response):
    # Must match the key & settings you used in set_cookie
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=IS_PROD,   # same as when you set it
        samesite="lax",
    )
    return {"ok": True}

# ========= RESUME ROUTES =========

@app.get("/tailored-resumes")
async def list_tailored_resumes(
    user_id: str = Depends(get_current_user_id),
    db: Database = Depends(get_db),
):
    cursor = db.tailored_resumes_collection.find(
        {"user_id": user_id}
    ).sort("createdAt", -1)

    items: List[dict] = []
    async for doc in cursor:
        items.append(
            {
                "id": str(doc["_id"]),
                "filename": doc.get("filename", ""),
                "jobLink": doc.get("jobLink"),
                "createdAt": doc.get("createdAt"),
            }
        )

    return items


@app.get("/tailored-resumes/{resume_id}/pdf")
async def get_tailored_resume_pdf(
    resume_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Database = Depends(get_db),
):
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")

    doc = await db.tailored_resumes_collection.find_one(
        {
            "_id": ObjectId(resume_id),
            "user_id": user_id,  # 🔒 only allow owner
        }
    )

    if not doc:
        raise HTTPException(status_code=404, detail="Tailored resume not found")

    pdf_bytes = bytes(doc["pdfData"])
    filename = doc.get("filename", "tailored_resume.pdf")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )

# ========= KEY ROUTE: TAILOR =========

@app.post("/tailor")
async def tailor_endpoint(
    payload: TailorPayload,
    user_id: str = Depends(get_current_user_id)
    ):
    # Decode uploaded resume (ephemeral)
    resume_bytes = None
    resume_mime = None
    if payload.resume and payload.resume.base64:
        resume_bytes = b64_to_bytes(payload.resume.base64)
        resume_mime = payload.resume.type

    # Run CrewAI pipeline (sync)
    result = run_tailor_pipeline(
        topic=payload.jobLink or payload.topic or "",
        work_experience=payload.workExperience,
        resume_bytes=resume_bytes,
        resume_mime=resume_mime,
    )

    pdf_bytes = result["pdf_bytes"]
    filename = result["filename"]

    # Save PDF in Mongo if you want it on the home page
    db = get_database()
    doc = {
        "user_id": user_id,
        "filename": filename,
        "mime": "application/pdf",
        "pdfData": Binary(pdf_bytes),
        "jobLink": payload.jobLink,
        "createdAt": datetime.utcnow(),
    }
    inserted = await db.tailored_resumes_collection.insert_one(doc)

    # Base64 for instant preview
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    return {
        "ok": True,
        "result": {
            "id": str(inserted.inserted_id),
            "filename": filename,
            "pdfBase64": pdf_base64,
            "pdfUrl": f"/resumes/{inserted.inserted_id}/pdf",  # if you add such a route
        },
    }

# ========= KEY ROUTE: WORKSHOP =========

@app.post("/workshop")
async def workshop_endpoint(
    payload: WorkshopRequest,
    user_id: str = Depends(get_current_user_id),  # or optional_get_current_user_id if you want to allow anon
):
    # Decode uploaded resume (ephemeral, same pattern as /tailor)
    resume_bytes: Optional[bytes] = None
    resume_mime: Optional[str] = None
    resume_name: Optional[str] = None

    if payload.resume and payload.resume.base64:
        resume_bytes = b64_to_bytes(payload.resume.base64)
        resume_mime = payload.resume.type
        resume_name = payload.resume.name

    # Run workshop pipeline (sync)
    workshop_result: WorkshopResponse = run_workshop_pipeline(
        workshop_focus=payload.workshopFocus,
        job_link=payload.jobLink,
        work_experience=payload.workExperience,
        resume_bytes=resume_bytes,
        resume_mime=resume_mime,
        resume_name=resume_name,
    )

    # We keep the same outer shape as /tailor:
    # { ok: true, result: { questions, context } }
    return {
        "ok": True,
        "result": workshop_result,
    }



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
