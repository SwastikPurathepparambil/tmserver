from datetime import datetime
from pydantic import BaseModel

class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime
    last_login_at: datetime