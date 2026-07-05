import os
import glob
import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from app.models.schemas import *
from app.services.latex_parser import parse_resume
from app.services.latex_patcher import patch_bullet_in_tex
from app.services.pdf_compiler import compile_tex_to_pdf
from app.services.resume_output_service import (
    apply_suggestions_to_resume,
    generate_final_resume,
)
from app.utils.file_helpers import (
    ensure_dirs,
    generate_resume_id,
    save_json,
    load_json,
    RESUME_MASTER_DIR,
    RESUME_PARSED_DIR,
    RESUME_GENERATED_DIR,
)

router = APIRouter(prefix="/resume", tags=["Resume"])


# ---------------------------------------------------------------------------
# List all master resumes
# ---------------------------------------------------------------------------

@router.get("/list")
def list_resumes():
    """Return all uploaded master resumes with summary info."""
    ensure_dirs()
    resumes = []

    for tex_path in sorted(
        glob.glob(os.path.join(RESUME_MASTER_DIR, "*.tex")),
        key=os.path.getmtime,
        reverse=True,
    ):
        filename = os.path.basename(tex_path)
        resume_id = filename.replace(".tex", "")
        parsed_path = os.path.join(RESUME_PARSED_DIR, f"{resume_id}.json")

        summary = {
            "resume_id": resume_id,
            "filename": filename,
            "display_name": resume_id.replace("resume_", ""),
            "companies": [],
            "bullet_count": 0,
            "skill_count": 0,
            "uploaded_at": datetime.datetime.fromtimestamp(
                os.path.getmtime(tex_path)
            ).isoformat(),
        }

        # Enrich with parsed data if available
        if os.path.exists(parsed_path):
            try:
                parsed = load_json(parsed_path)
                summary["display_name"] = parsed.get("display_name", summary["display_name"])
                summary["companies"] = [
                    e["company"] for e in parsed.get("experience", [])
                ]
                summary["bullet_count"] = sum(
                    len(e.get("bullets", [])) for e in parsed.get("experience", [])
                ) + sum(
                    len(p.get("bullets", [])) for p in parsed.get("projects", [])
                )
                summary["skill_count"] = len(parsed.get("skills", []))
            except Exception:
                pass  # corrupted JSON → return basic info

        resumes.append(summary)

    return resumes


# ---------------------------------------------------------------------------
# Clear all data  (must be BEFORE /{resume_id} to avoid route conflict)
# ---------------------------------------------------------------------------

@router.delete("/admin/clear-all")
def clear_all_resumes():
    """Delete ALL master resumes, parsed JSONs, and generated files."""
    deleted = 0
    for directory in [RESUME_MASTER_DIR, RESUME_PARSED_DIR, RESUME_GENERATED_DIR]:
        for path in glob.glob(os.path.join(directory, "*")):
            try:
                os.remove(path)
                deleted += 1
            except Exception:
                pass
    return {"deleted_count": deleted, "status": "all_data_cleared"}


# ---------------------------------------------------------------------------
# Delete a single resume and all linked data
# ---------------------------------------------------------------------------

@router.delete("/{resume_id}")
def delete_resume(resume_id: str):
    """Delete a master resume, its parsed JSON, and all generated files."""
    deleted = []
    not_found = True

    # Master .tex
    master_path = os.path.join(RESUME_MASTER_DIR, f"{resume_id}.tex")
    if os.path.exists(master_path):
        os.remove(master_path)
        deleted.append("master .tex")
        not_found = False

    # Parsed JSON
    parsed_path = os.path.join(RESUME_PARSED_DIR, f"{resume_id}.json")
    if os.path.exists(parsed_path):
        os.remove(parsed_path)
        deleted.append("parsed JSON")
        not_found = False

    # Generated files (tailored .tex, .pdf, .json, .log, .aux, .out)
    for pattern in [f"{resume_id}_*"]:
        for path in glob.glob(os.path.join(RESUME_GENERATED_DIR, pattern)):
            os.remove(path)
            deleted.append(os.path.basename(path))

    if not_found:
        raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")

    return {
        "resume_id": resume_id,
        "deleted_files": deleted,
        "count": len(deleted),
        "status": "deleted",
    }


# ---------------------------------------------------------------------------
# Upload & Parse
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=UploadResumeResponse)
async def upload_resume(tex_file: UploadFile = File(...), custom_filename: str = Form("")):
    ensure_dirs()

    if not tex_file.filename.endswith(".tex"):
        raise HTTPException(status_code=400, detail="Only .tex files are allowed")

    # Use custom filename if provided, otherwise use the uploaded file's name
    base_name = custom_filename.strip() if custom_filename.strip() else tex_file.filename
    # Remove .tex extension if present (we'll add it back)
    if base_name.endswith(".tex"):
        base_name = base_name[:-4]
    # Sanitize: replace spaces/special chars with underscores
    import re as _re
    base_name = _re.sub(r"[^\w\-]", "_", base_name)
    if not base_name:
        base_name = "resume"

    resume_id = f"resume_{generate_resume_id()}"
    filename = f"{base_name}.tex"
    tex_path = os.path.join(RESUME_MASTER_DIR, f"{resume_id}.tex")
    parsed_json_path = os.path.join(RESUME_PARSED_DIR, f"{resume_id}.json")

    content = await tex_file.read()
    tex_content = content.decode("utf-8")

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    parsed_resume = parse_resume(tex_content, resume_id)

    # Store the display filename in the parsed JSON
    parsed_dict = parsed_resume.model_dump()
    parsed_dict["display_name"] = base_name
    save_json(parsed_json_path, parsed_dict)

    return UploadResumeResponse(
        resume_id=resume_id,
        filename=filename,
        tex_path=tex_path,
        parsed_json_path=parsed_json_path,
        status="uploaded_and_parsed",
    )


# ---------------------------------------------------------------------------
# Serve parsed JSON
# ---------------------------------------------------------------------------

@router.get("/parsed/{resume_id}")
def get_parsed_resume(resume_id: str):
    """Return the parsed resume JSON for a given resume_id."""
    parsed_path = os.path.join(RESUME_PARSED_DIR, f"{resume_id}.json")
    if not os.path.exists(parsed_path):
        raise HTTPException(status_code=404, detail="Parsed resume not found")
    return load_json(parsed_path)


# ---------------------------------------------------------------------------
# Serve generated files
# ---------------------------------------------------------------------------

@router.get("/generated/{filename}")
def get_generated_file(filename: str):
    """Serve a generated .tex or .pdf file."""
    file_path = os.path.join(RESUME_GENERATED_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    if filename.endswith(".pdf"):
        return FileResponse(file_path, media_type="application/pdf")
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            return PlainTextResponse(content=f.read())


# ---------------------------------------------------------------------------
# Cover letter generation
# ---------------------------------------------------------------------------

class CoverLetterRequest(BaseModel):
    jd_text: str
    company_name: str = ""
    hiring_manager: str = "Hiring Manager"
    candidate_name: str = ""


@router.post("/{resume_id}/cover-letter")
def generate_cover_letter(resume_id: str, request: CoverLetterRequest):
    """Generate a tailored plain-text cover letter based on resume + JD."""
    parsed_path = os.path.join(RESUME_PARSED_DIR, f"{resume_id}.json")
    if not os.path.exists(parsed_path):
        raise HTTPException(status_code=404, detail="Parsed resume not found")

    parsed_resume = load_json(parsed_path)

    from app.services.jd_analyzer import analyze_jd
    from app.services.resume_matcher import match_resume_to_jd
    from app.services.cover_letter_generator import generate_cover_letter as gen_cl

    jd_analysis = analyze_jd(request.jd_text)
    match_result = match_resume_to_jd(parsed_resume, jd_analysis)

    text = gen_cl(
        parsed_resume=parsed_resume,
        jd_analysis=jd_analysis,
        match_result=match_result,
        company_name=request.company_name or jd_analysis.get("company_name", ""),
        hiring_manager=request.hiring_manager,
        candidate_name=request.candidate_name,
    )

    return {
        "resume_id": resume_id,
        "text": text,
        "company_name": jd_analysis.get("company_name", ""),
        "status": "generated",
    }


# ---------------------------------------------------------------------------
# Candidate name config
# ---------------------------------------------------------------------------

class CandidateNameRequest(BaseModel):
    candidate_name: str


@router.get("/config/candidate-name")
def get_candidate_name():
    """Return the current candidate name from env."""
    import os as _os
    from pathlib import Path as _Path
    from dotenv import load_dotenv as _load_dotenv
    _root = _Path(__file__).resolve().parents[3]
    _load_dotenv(dotenv_path=_root / ".env", override=True)
    return {"candidate_name": _os.getenv("CANDIDATE_NAME", "")}


@router.post("/config/candidate-name")
def set_candidate_name(request: CandidateNameRequest):
    """Update the candidate name in .env (runtime + persisted)."""
    import os as _os
    from pathlib import Path as _Path
    root = _Path(__file__).resolve().parents[3]
    env_path = root / ".env"

    # Read existing .env
    lines = env_path.read_text(encoding="utf-8").splitlines()
    found = False
    new_lines = []
    for line in lines:
        if line.startswith("CANDIDATE_NAME="):
            new_lines.append(f"CANDIDATE_NAME={request.candidate_name}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"CANDIDATE_NAME={request.candidate_name}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Also update env var for current process
    _os.environ["CANDIDATE_NAME"] = request.candidate_name

    return {"candidate_name": request.candidate_name, "status": "updated"}


# ---------------------------------------------------------------------------
# Cover letter → PDF
# ---------------------------------------------------------------------------

class CoverLetterPDFRequest(BaseModel):
    text: str


@router.post("/{resume_id}/cover-letter/pdf")
def cover_letter_to_pdf(resume_id: str, request: CoverLetterPDFRequest):
    """Convert cover letter plain text to a PDF using pdflatex."""
    import subprocess, tempfile, base64
    from app.utils.latex_utils import escape_latex

    latex_text = escape_latex(request.text)

    # Wrap in a clean LaTeX document
    latex_doc = (
        r"\documentclass[11pt]{article}\n"
        r"\usepackage[utf8]{inputenc}\n"
        r"\usepackage[margin=1in]{geometry}\n"
        r"\usepackage{parskip}\n"
        r"\usepackage{hyperref}\n"
        r"\begin{document}\n"
        + latex_text +
        r"\n\end{document}"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "cover_letter.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_doc)

        try:
            for _ in range(2):  # two passes
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "cover_letter.tex"],
                    cwd=tmpdir, capture_output=True, text=True, timeout=30,
                )
        except FileNotFoundError:
            raise HTTPException(
                status_code=500,
                detail="pdflatex not installed. Install TeX Live or MiKTeX.",
            )

        pdf_path = os.path.join(tmpdir, "cover_letter.pdf")
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            return {
                "resume_id": resume_id,
                "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
                "size_bytes": len(pdf_bytes),
                "status": "generated",
            }

        raise HTTPException(status_code=500, detail="PDF compilation failed")


# ---------------------------------------------------------------------------
# Patch a single bullet
# ---------------------------------------------------------------------------

@router.post("/patch")
def patch_resume(request: PatchRequest):
    master_tex_path = os.path.join(RESUME_MASTER_DIR, f"{request.resume_id}.tex")
    parsed_json_path = os.path.join(RESUME_PARSED_DIR, f"{request.resume_id}.json")
    generated_tex_path = os.path.join(
        RESUME_GENERATED_DIR, f"{request.resume_id}_patched.tex"
    )

    if not os.path.exists(master_tex_path):
        raise HTTPException(status_code=404, detail="Resume .tex not found")
    if not os.path.exists(parsed_json_path):
        raise HTTPException(status_code=404, detail="Parsed resume JSON not found")

    parsed_resume = load_json(parsed_json_path)

    with open(master_tex_path, "r", encoding="utf-8") as f:
        original_tex = f.read()

    updated_tex = patch_bullet_in_tex(
        original_tex, parsed_resume, request.bullet_id, request.new_text
    )

    with open(generated_tex_path, "w", encoding="utf-8") as f:
        f.write(updated_tex)

    return {"status": "patched", "generated_tex_path": generated_tex_path}


# ---------------------------------------------------------------------------
# Compile LaTeX → PDF
# ---------------------------------------------------------------------------

@router.post("/compile/{resume_id}")
def compile_resume(resume_id: str):
    generated_tex_path = os.path.join(
        RESUME_GENERATED_DIR, f"{resume_id}_patched.tex"
    )
    if not os.path.exists(generated_tex_path):
        raise HTTPException(status_code=404, detail="Patched .tex file not found")
    return compile_tex_to_pdf(generated_tex_path)


# ---------------------------------------------------------------------------
# Apply suggestions (batch) & Generate final
# ---------------------------------------------------------------------------

@router.post("/apply-suggestions")
def apply_suggestions(request: ApplySuggestionsRequest):
    try:
        return apply_suggestions_to_resume(
            resume_id=request.resume_id,
            accepted_suggestions=[s.dict() for s in request.accepted_suggestions],
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-final")
def generate_final(request: GenerateFinalResumeRequest):
    try:
        return generate_final_resume(request.resume_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
