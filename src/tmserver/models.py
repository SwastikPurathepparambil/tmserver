from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Any, Optional


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime
    last_login_at: datetime

class ResumeUpload(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    base64: Optional[str] = None

class TailorPayload(BaseModel):
    topic: Optional[str] = None
    workExperience: Optional[str] = None
    jobLink: Optional[str] = None
    resume: Optional[ResumeUpload] = None
    submittedAt: Optional[str] = None