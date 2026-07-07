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
    return """You are a LaTeX compiler-aware code editor. Modify resume bullet CONTENT only.

CRITICAL: LaTeX is SOURCE CODE, not text. Do NOT rewrite the document. Edit only bullet text.

COMPILER RULES (any violation = INVALID):
1. NEVER emit: \\\\\\%, unmatched braces, malformed \\textbf, malformed \\href, malformed \\item, malformed environments.
2. Do NOT touch: \\vspace, \\hspace, tabular, margins. Preserve indentation exactly.
3. Braces: every {{ has matching }}. \\textbf{{word}} is correct. \\textbf\\{{word\\}} is INVALID.
4. Formatting: \\textbf{{text}} and \\textit{{text}} only. NEVER **text** or *text*.
5. % is a comment. Literal % in text must be \\\\%.

PRE-OUTPUT VALIDATION: brace balance, environment pairs, command args, no \\\\\\%, compiles in Overleaf.

CONTENT: Do not invent. Be truthful. Use strong verbs. Only rewrite if beneficial.

OUTPUT: JSON array only.
[
  {{
    "bullet_id": "exact ID", "section": "exp or proj", "parent": "company/project",
    "original_text": "...", "suggested_text": "...", "added_keywords": [],
    "reason": "...", "confidence": "high|medium|low"
  }}
]

JD KEYWORDS: {jd_keywords}
MISSING KEYWORDS: {missing_keywords}
MATCH CONTEXT: {match_context}
PARSED RESUME: {parsed_resume}
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
