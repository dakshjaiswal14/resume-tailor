import os
import subprocess
from typing import Dict

from app.utils.file_helpers import RESUME_GENERATED_DIR, ensure_dirs


def generate_final_resume(resume_id: str) -> Dict:
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
            "pdflatex not found. Please install a LaTeX distribution and ensure pdflatex is in PATH."
        )
