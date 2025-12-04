from google.auth.transport import requests
from google.oauth2 import id_token
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi import Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

SECRET_KEY = os.getenv("SECRET_KEY", "secret")
ALGORITHM = "HS256"

security = HTTPBearer()

#current experiation time is 24 hours -> change if needed
def create_access_token(data: dict):
    data = data.copy()
    currentTime = datetime.utcnow()
    expiredTime = currentTime + timedelta(hours=24)
    data.update({"exp": expiredTime})
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


        
async def get_current_user_id(request: Request):
    token = request.cookies.get("access_token")


    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user_id = verify_token(token)
    return user_id

     
async def optional_get_current_user_id(request: Request):
    token = request.cookies.get("access_token")


    if not token:
        return None
    try: 
        user_id = verify_token(token)
        return user_id

    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


async def verify_google_token(token: str):
    try:
        id_information = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            os.getenv("GOOGLE_CLIENT_ID")
        )
        google_sub = id_information['sub']
        email = id_information['email']
        
        return {"google_sub": google_sub, "email": email}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"token not valid: {str(e)}"
        )