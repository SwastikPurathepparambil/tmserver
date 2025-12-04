from fastapi import FastAPI, HTTPException, status, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId
import os
import uvicorn
from contextlib import asynccontextmanager   

from tmserver.db import get_database, Database,connect_to_db_mongo, disconnect_mongo
from tmserver.models import UserResponse
from tmserver.auth import verify_google_token, create_access_token, get_current_user_id, optional_get_current_user_id

import time
import asyncio

# load_dotenv()  # loads OPENAI_API_KEY, etc.
ENV = os.getenv("ENVIRONMENT", "dev")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
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
    print(user)
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
        secure=False,   # same as when you set it
        samesite="lax",
    )
    return {"ok": True}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
