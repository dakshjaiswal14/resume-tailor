import os
import subprocess


def compile_tex_to_pdf(tex_path: str):
    working_dir = os.path.dirname(tex_path)
    filename = os.path.basename(tex_path)

    try:
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", filename],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=30
        )

        pdf_name = filename.replace(".tex", ".pdf")
        pdf_path = os.path.join(working_dir, pdf_name)

        return {
            "status": "compiled" if os.path.exists(pdf_path) else "failed",
            "pdf_path": pdf_path if os.path.exists(pdf_path) else None,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }