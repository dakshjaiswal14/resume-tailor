from pydantic import BaseModel
from typing import List, Optional


class ResumeBullet(BaseModel):
    id: str
    text: str
    raw_latex: Optional[str] = None


class ExperienceItem(BaseModel):
    id: str
    company: str
    role: str
    duration: Optional[str] = None
    bullets: List[ResumeBullet]


class ProjectItem(BaseModel):
    id: str
    name: str
    bullets: List[ResumeBullet]


class EducationItem(BaseModel):
    id: str
    institution: str
    degree: str
    details: Optional[str] = None


class ResumeModel(BaseModel):
    resume_id: str
    summary: Optional[str] = None
    skills: List[str] = []
    experience: List[ExperienceItem] = []
    projects: List[ProjectItem] = []
    education: List[EducationItem] = []


class UploadResumeResponse(BaseModel):
    resume_id: str
    filename: str
    tex_path: str
    parsed_json_path: str
    status: str


class PatchRequest(BaseModel):
    resume_id: str
    bullet_id: str
    new_text: str

class SuggestionItem(BaseModel):
    bullet_id: str
    section: str
    parent: str
    original_text: str
    suggested_text: str
    added_keywords: List[str]
    reason: str
    confidence: str


class ValidateSuggestionsRequest(BaseModel):
    resume_id: str
    missing_keywords: List[str]
    suggestions: List[SuggestionItem]

class ApplySuggestionItem(BaseModel):
    bullet_id: str
    new_text: str


class ApplySuggestionsRequest(BaseModel):
    resume_id: str
    accepted_suggestions: List[ApplySuggestionItem]

class GenerateFinalResumeRequest(BaseModel):
    resume_id: str