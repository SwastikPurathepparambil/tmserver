from fastapi import FastAPI
from tmserver.db import get_database, Database
from tmserver.auth import verify_google_token, create_access_token
from datetime import datetime
from fastapi import Depends
from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware
from tmserver.db import connect_to_db_mongo, disconnect_mongo
app = FastAPI(title = "Taylor Make API")

def get_db() -> Database:
    return get_database()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy"
    }




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
async def get_me(user_id: str = Depends(get_current_user_id), db: Database = Depends(get_db)):
    user = await db.users_set.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(status_code=404, detail = "Not Found")

    return {
        "id": str(user["_id"]),
        "email": user.get("email"),
        "created_at": user.get("created_at"),
        
        "last_login_at": user.get("last_login_at")
    }