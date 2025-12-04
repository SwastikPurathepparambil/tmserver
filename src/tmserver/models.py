from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Any, Optional


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime
    last_login_at: datetime
