from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Any, Optional
class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime
    last_login_at: datetime


class CreateResume(BaseModel):
    target_role: str
    content: Dict[str, Any]

class UpdateResume(BaseModel):
    target_role: Optional[str] = None
    content: Optional[Dict[str, Any]] = None


class ResumeResponse(BaseModel):
    id: str
    target_role: str
    content: Dict[str, Any]
    date_uploaded: datetime
    updated_at: datetime


class ListResume(BaseModel):
    id: str
    target_role: str
    date_uploaded: datetime
    updated_at: datetime