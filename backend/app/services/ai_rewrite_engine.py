"""
Gemini-powered resume rewrite engine.

Loads the system prompt from prompts/rewrite_generator.txt and uses it to
generate structured, high-quality bullet-point rewrite suggestions that align
the candidate's resume with a target job description.
"""

import json
from pathlib import Path

from app.services.llm_client import generate_json_response
from app.utils.latex_utils import normalize_latex_formatting

# Resolve the prompts directory relative to this file
PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def build_rewrite_prompt(
    parsed_resume: dict,
    jd_analysis: dict,
    match_result: dict,
) -> str:
    """Construct the full prompt for the Gemini rewrite API call."""
    template = _load_prompt("rewrite_generator.txt")

    if not template:
        template = _default_prompt()

    company_name = jd_analysis.get("company_name", "")

    return template.format(
        company_name=company_name or "the company",
        jd_keywords=json.dumps(jd_analysis.get("keywords", []), indent=2),
        missing_keywords=json.dumps(match_result.get("missing_keywords", []), indent=2),
        match_context=json.dumps(match_result, indent=2),
        parsed_resume=json.dumps(parsed_resume, indent=2),
    )


def _default_prompt() -> str:
    """Fallback prompt used when prompts/rewrite_generator.txt is unavailable."""
    return """You are an expert technical resume optimization assistant.

Your task is to improve resume bullet points so they align better with a target job description from {company_name}.

IMPORTANT RULES:
1. Do NOT invent experiences, tools, technologies, metrics, or responsibilities not present or strongly implied in the original bullet.
2. Keep rewrites truthful and ATS-friendly.
3. Improve clarity, specificity, and alignment with the job description.
4. Naturally incorporate relevant missing keywords ONLY where appropriate.
5. Rewrite only bullets that genuinely benefit from optimization.
6. If a bullet should not be changed, do not include it in the output.
7. Return ONLY valid JSON. No markdown. No explanation.
8. Preserve the original meaning and factual content — do not exaggerate.
9. CRITICAL — This is LaTeX, NOT Markdown:
    - Bold: \\textbf{{microservices}} (braces around the word). NOT **microservices** or \\textbf\\{{word\\}}
    - Italic: \\textit{{APIs}}
    - Always wrap text in {{ }} after the command: \\command{{text}}
    - Never escape braces with backslashes. The output goes into a .tex file.

Return output as a JSON array of objects with this exact schema:
[
  {{
    "bullet_id": "string (the exact ID from the parsed resume)",
    "section": "string (experience or project)",
    "parent": "string (company name or project name)",
    "original_text": "string",
    "suggested_text": "string",
    "added_keywords": ["string"],
    "reason": "string (brief explanation of what was improved)",
    "confidence": "high|medium|low"
  }}
]

JOB DESCRIPTION KEYWORDS:
{jd_keywords}

MISSING KEYWORDS (keywords in JD but not found in resume):
{missing_keywords}

MATCH CONTEXT:
{match_context}

PARSED RESUME:
{parsed_resume}

Return JSON array only. No other text.
""".strip()


def generate_ai_rewrite_suggestions(
    parsed_resume: dict,
    jd_analysis: dict,
    match_result: dict,
) -> list:
    """Call Gemini to generate rewrite suggestions for resume bullets."""
    prompt = build_rewrite_prompt(parsed_resume, jd_analysis, match_result)

    response = generate_json_response(prompt)

    if not isinstance(response, list):
        raise ValueError(f"LLM response is not a list (got {type(response).__name__})")

    # Normalize LaTeX formatting + validate
    required_fields = {"bullet_id", "suggested_text", "confidence"}
    for i, item in enumerate(response):
        missing = required_fields - set(item.keys())
        if missing:
            raise ValueError(f"Suggestion at index {i} is missing fields: {missing}")
        # Fix common AI formatting mistakes
        item["suggested_text"] = normalize_latex_formatting(item["suggested_text"])
        if "original_text" in item:
            item["original_text"] = normalize_latex_formatting(item["original_text"])

    return response
