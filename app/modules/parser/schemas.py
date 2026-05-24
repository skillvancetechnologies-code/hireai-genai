from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional

class ParsedCandidate(BaseModel):
    name: str = Field(..., max_length=255)
    email: EmailStr
    phone: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience_years: float = Field(..., ge=0, le=50)
    education: str
    projects: List[str] = Field(default_factory=list)
    raw_text: str
    summary: str
    parse_confidence: float = Field(..., ge=0, le=1)
    