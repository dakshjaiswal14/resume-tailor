"""
Resume output service — applies accepted suggestions to produce tailored LaTeX
and optionally compiles to PDF.
"""

import os
import json
import subprocess
from typing import List, Dict

from app.services.latex_patcher import patch_bullet_in_tex
from app.utils.latex_utils import escape_latex
from app.utils.file_helpers import (
    RESUME_MASTER_DIR,
    RESUME_PARSED_DIR,
    RESUME_GENERATED_DIR,
    ensure_dirs,
    load_json,
)


# ---------------------------------------------------------------------------
# Apply accepted suggestions → produce tailored .tex
# ---------------------------------------------------------------------------

def apply_suggestions_to_resume(
    resume_id: str,
    accepted_suggestions: List[Dict],
) -> Dict:
    """Patch the master .tex with accepted suggestions, save the result."""
    ensure_dirs()

    parsed_path = os.path.join(RESUME_PARSED_DIR, f"{resume_id}.json")
    master_tex_path = os.path.join(RESUME_MASTER_DIR, f"{resume_id}.tex")
    generated_tex_path = os.path.join(RESUME_GENERATED_DIR, f"{resume_id}_tailored.tex")
    generated_json_path = os.path.join(RESUME_GENERATED_DIR, f"{resume_id}_tailored.json")

    if not os.path.exists(parsed_path):
        raise FileNotFoundError(f"Parsed resume not found: {parsed_path}")
    if not os.path.exists(master_tex_path):
        raise FileNotFoundError(f"Master tex resume not found: {master_tex_path}")

    parsed_resume = load_json(parsed_path)

    with open(master_tex_path, "r", encoding="utf-8") as f:
        updated_tex = f.read()

    applied_count = 0
    updated_bullets = []

    for suggestion in accepted_suggestions:
        bullet_id = suggestion["bullet_id"]
        plain_new_text = suggestion["new_text"]

        try:
            updated_tex = patch_bullet_in_tex(
                updated_tex, parsed_resume, bullet_id, plain_new_text
            )
            applied_count += 1
            updated_bullets.append({
                "bullet_id": bullet_id,
                "new_text": plain_new_text,
                "status": "applied",
            })
        except Exception as e:
            updated_bullets.append({
                "bullet_id": bullet_id,
                "new_text": plain_new_text,
                "status": "failed",
                "error": str(e),
            })

    # --- Post-generation integrity check ---
    from app.utils.latex_utils import validate_and_fix_tex

    validation = validate_and_fix_tex(updated_tex)
    updated_tex = validation["tex"]

    # Save tailored .tex (after validation fixes)
    with open(generated_tex_path, "w", encoding="utf-8") as f:
        f.write(updated_tex)

    # Save updated parsed JSON with applied-suggestions metadata
    generated_json = parsed_resume.copy()
    generated_json["applied_suggestions"] = updated_bullets
    generated_json["validation"] = {
        "fixes_applied": validation["fixes"],
        "errors_remaining": validation["errors"],
    }
    with open(generated_json_path, "w", encoding="utf-8") as f:
        json.dump(generated_json, f, indent=2, ensure_ascii=False)

    return {
        "resume_id": resume_id,
        "updated_tex_path": str(generated_tex_path),
        "updated_json_path": str(generated_json_path),
        "applied_count": applied_count,
        "total_requested": len(accepted_suggestions),
        "applied_suggestions": updated_bullets,
        "validation": {
            "fixes_applied": validation["fixes"],
            "errors_remaining": validation["errors"],
        },
        "status": "success" if applied_count > 0 else "failed",
    }


# ---------------------------------------------------------------------------
# Compile tailored .tex → PDF  (optional — requires pdflatex)
# ---------------------------------------------------------------------------

def generate_final_resume(resume_id: str) -> Dict:
    """Compile the tailored .tex to PDF using pdflatex."""
    ensure_dirs()

    tex_path = os.path.join(RESUME_GENERATED_DIR, f"{resume_id}_tailored.tex")
    pdf_path = os.path.join(RESUME_GENERATED_DIR, f"{resume_id}_tailored.pdf")
    log_path = os.path.join(RESUME_GENERATED_DIR, f"{resume_id}_latex_output.log")

    if not os.path.exists(tex_path):
        raise FileNotFoundError(f"Tailored .tex file not found: {tex_path}")

    try:
        result = subprocess.run(
            [
                "pdflatex",
                "-interaction=nonstopmode",
                "-output-directory",
                str(RESUME_GENERATED_DIR),
                str(tex_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        full_log = (result.stdout or "") + "\n\n" + (result.stderr or "")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(full_log)

        latex_errors = [
            "! Extra }",
            "! Misplaced alignment tab character",
            "! Missing } inserted",
            "! Undefined control sequence",
        ]
        has_latex_error = any(err in full_log for err in latex_errors)

        if result.returncode != 0 or has_latex_error:
            return {
                "resume_id": resume_id,
                "status": "warning",
                "tex_path": str(tex_path),
                "pdf_path": str(pdf_path),
                "log_path": str(log_path),
                "message": "PDF generated, but LaTeX issues were detected. Review log file.",
            }

        return {
            "resume_id": resume_id,
            "status": "success",
            "tex_path": str(tex_path),
            "pdf_path": str(pdf_path),
            "log_path": str(log_path),
            "message": "Final tailored resume PDF generated successfully.",
        }

    except FileNotFoundError:
        raise FileNotFoundError(
            "pdflatex not found. Please install a LaTeX distribution "
            "and ensure pdflatex is in PATH."
        )
