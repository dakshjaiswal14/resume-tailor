import json
import os
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


def apply_suggestions_to_resume(resume_id: str, accepted_suggestions: List[Dict]) -> Dict:
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
        original_tex = f.read()

    updated_tex = original_tex

    applied_count = 0
    updated_bullets = []

    for suggestion in accepted_suggestions:
        bullet_id = suggestion["bullet_id"]
        plain_new_text = suggestion["new_text"]
        latex_new_text = escape_latex(plain_new_text)

        try:
            updated_tex = patch_bullet_in_tex(
                updated_tex,
                parsed_resume,
                bullet_id,
                plain_new_text
            )
            applied_count += 1
            updated_bullets.append({
                "bullet_id": bullet_id,
                "new_text": plain_new_text,
                "status": "applied"
            })
        except Exception as e:
            updated_bullets.append({
                "bullet_id": bullet_id,
                "new_text": plain_new_text,
                "status": "failed",
                "error": str(e)
            })

    # Save tailored tex
    with open(generated_tex_path, "w", encoding="utf-8") as f:
        f.write(updated_tex)

    # Also save updated parsed JSON copy (optional but useful)
    generated_json = parsed_resume.copy()
    generated_json["applied_suggestions"] = updated_bullets
    with open(generated_json_path, "w", encoding="utf-8") as f:
        json.dump(generated_json, f, indent=2, ensure_ascii=False)

    return {
        "resume_id": resume_id,
        "updated_tex_path": str(generated_tex_path),
        "updated_json_path": str(generated_json_path),
        "applied_count": applied_count,
        "total_requested": len(accepted_suggestions),
        "applied_suggestions": updated_bullets,
        "status": "success" if applied_count > 0 else "failed"
    }