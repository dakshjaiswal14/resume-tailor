"""Application tracker routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.application_tracker import (
    list_applications,
    add_application,
    update_application,
    delete_application,
    STATUSES,
)

router = APIRouter(prefix="/applications", tags=["Applications"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AddApplicationRequest(BaseModel):
    company: str
    position: str = ""
    resume_id: str = ""
    cover_letter_text: str = ""
    notes: str = ""


class UpdateApplicationRequest(BaseModel):
    status: str = ""
    notes: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def get_applications():
    """List all applications (newest first)."""
    return list_applications()


@router.get("/statuses")
def get_statuses():
    """Return the list of valid statuses."""
    return STATUSES


@router.post("")
def create_application(request: AddApplicationRequest):
    """Track a new job application."""
    return add_application(
        company=request.company,
        position=request.position,
        resume_id=request.resume_id,
        cover_letter_text=request.cover_letter_text,
        notes=request.notes,
    )


@router.patch("/{app_id}")
def patch_application(app_id: str, request: UpdateApplicationRequest):
    """Update status or notes for an application."""
    result = update_application(app_id, status=request.status, notes=request.notes)
    if result is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return result


@router.delete("/{app_id}")
def remove_application(app_id: str):
    """Delete an application."""
    if not delete_application(app_id):
        raise HTTPException(status_code=404, detail="Application not found")
    return {"app_id": app_id, "status": "deleted"}
