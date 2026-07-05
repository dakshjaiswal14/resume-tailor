import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.jd_analyzer import analyze_jd
from app.services.resume_matcher import match_resume_to_jd
from app.services.rewrite_engine import generate_rewrite_suggestions
from app.services.ai_rewrite_engine import generate_ai_rewrite_suggestions
from app.services.suggestion_validator import validate_suggestions
from app.models.schemas import *
from app.utils.file_helpers import RESUME_PARSED_DIR, load_json

router = APIRouter(prefix="/jd", tags=["Job Description"])


class JDMatchRequest(BaseModel):
    resume_id: str
    jd_text: str


def load_parsed_resume(resume_id: str):
    parsed_path = os.path.join(RESUME_PARSED_DIR, f"{resume_id}.json")

    if not os.path.exists(parsed_path):
        raise HTTPException(status_code=404, detail="Parsed resume not found")

    return load_json(parsed_path)


@router.post("/analyze")
def analyze_job_description(request: JDMatchRequest):
    parsed_resume = load_parsed_resume(request.resume_id)

    jd_analysis = analyze_jd(request.jd_text)
    match_result = match_resume_to_jd(parsed_resume, jd_analysis)

    return {
        "resume_id": request.resume_id,
        "jd_analysis": jd_analysis,
        "match_result": match_result
    }


@router.post("/suggest-rewrites")
def suggest_rewrites(request: JDMatchRequest):
    parsed_resume = load_parsed_resume(request.resume_id)

    jd_analysis = analyze_jd(request.jd_text)
    match_result = match_resume_to_jd(parsed_resume, jd_analysis)

    # Try AI first, fallback to heuristic engine
    try:
        suggestions = generate_ai_rewrite_suggestions(
            parsed_resume=parsed_resume,
            jd_analysis=jd_analysis,
            match_result=match_result
        )
        source = "ai"
    except Exception as e:
        print(f"AI rewrite failed, falling back to heuristic engine: {e}")
        suggestions = generate_rewrite_suggestions(parsed_resume, match_result)
        source = "fallback"

    return {
        "resume_id": request.resume_id,
        "jd_keywords": jd_analysis["keywords"],
        "missing_keywords": match_result["missing_keywords"],
        "suggestions": suggestions,
        "source": source
    }

@router.post("/validate-suggestions")
def validate_jd_suggestions(request: ValidateSuggestionsRequest):
    validated = validate_suggestions(
        suggestions=[s.dict() for s in request.suggestions],
        missing_keywords=request.missing_keywords
    )

    return {
        "resume_id": request.resume_id,
        "validated_suggestions": validated
    }