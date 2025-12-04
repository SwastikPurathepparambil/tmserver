from datetime import datetime
from pydantic import BaseModel
from typing import List, Dict, Any, Optional


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


class ExperienceItem(BaseModel):
    role: str
    company: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bullets: List[str] = []

class ResumeSection(BaseModel):
    title: str
    # keep it loose for now; you can tighten later
    items: List[Dict[str, Any]]

class ResumeContact(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    links: List[str] = []

class TailoredResume(BaseModel):
    contact: ResumeContact
    headline: str
    summary: str
    sections: List[ResumeSection]