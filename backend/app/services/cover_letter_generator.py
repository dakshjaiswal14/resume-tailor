"""
Cover letter generator — uses Gemini to produce a tailored plain-text cover
letter based on the parsed resume + job description match.
"""

import os
import json
from pathlib import Path

from app.services.llm_client import generate_json_response

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"

# Load candidate name once
from dotenv import load_dotenv
load_dotenv(dotenv_path=ENV_PATH, override=True)
DEFAULT_CANDIDATE_NAME = os.getenv("CANDIDATE_NAME", "")


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def generate_cover_letter(
    parsed_resume: dict,
    jd_analysis: dict,
    match_result: dict,
    company_name: str = "",
    hiring_manager: str = "Hiring Manager",
    candidate_name: str = "",
) -> str:
    """Generate a cover letter in plain text, returning the text string."""

    # Use provided values or extract from JD analysis
    if not company_name:
        company_name = jd_analysis.get("company_name", "")
    if not candidate_name:
        candidate_name = DEFAULT_CANDIDATE_NAME

    # Collect top matching bullets as "strengths"
    strengths = []
    for b in match_result.get("top_matching_bullets", [])[:5]:
        if b.get("score", 0) > 0:
            strengths.append(
                f"- {b.get('text', '')} "
                f"(matches: {b.get('matched_keywords', [])})"
            )

    template = _load_prompt("cover_letter.txt")
    if not template:
        template = _DEFAULT_PROMPT

    prompt = template.format(
        company_name=company_name or "[Company Name]",
        hiring_manager=hiring_manager,
        candidate_name=candidate_name or "the Candidate",
        parsed_resume=json.dumps(parsed_resume, indent=2),
        jd_keywords=json.dumps(jd_analysis.get("keywords", [])),
        missing_keywords=json.dumps(match_result.get("missing_keywords", [])),
        match_strengths="\n".join(strengths) if strengths else "N/A",
    )

    response = generate_json_response(prompt)

    if isinstance(response, dict):
        if "text" in response:
            return response["text"]
        if "latex_body" in response:
            return response["latex_body"]

    if isinstance(response, str):
        return response

    raise ValueError(f"Unexpected cover letter response: {type(response)}")


_DEFAULT_PROMPT = """You are a professional cover letter writer.

Write a tailored cover letter in PLAIN TEXT for {hiring_manager} at {company_name}.
Candidate name: {candidate_name}

RULES:
1. Plain text only — no LaTeX, no markdown.
2. Use {candidate_name} as the candidate's full name throughout.
3. Use double newlines between paragraphs.
4. Include candidate header (name, email, phone, LinkedIn), date, then letter.
5. 3-4 paragraphs: intro, experience match, why this role at {company_name}, closing.
6. Only reference experiences from the resume. Be truthful and concise.
7. Return JSON: {{"text": "cover letter text..."}}

RESUME: {parsed_resume}
JD KEYWORDS: {jd_keywords}
MISSING KEYWORDS: {missing_keywords}
MATCHED STRENGTHS: {match_strengths}
"""
