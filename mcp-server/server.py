"""
RoleTailor AI — MCP Server

Exposes resume tailoring tools via the Model Context Protocol (MCP).
Connect Claude Code (or any MCP client) to this server to:
  - Parse LaTeX resumes (Overleaf-compatible)
  - Analyze job descriptions
  - Match resumes against JDs
  - Generate AI-powered rewrite suggestions
  - Apply accepted suggestions back into LaTeX
  - Compile LaTeX to PDF (if pdflatex is available)

Usage:
    python mcp-server/server.py

Configure in .claude/mcp.json:
    {
      "mcpServers": {
        "roletailor": {
          "command": "python",
          "args": ["mcp-server/server.py"]
        }
      }
    }
"""

import sys
import os
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Any

# Ensure the backend package is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ---------------------------------------------------------------------------
# Backend imports (lazy — imported when tools are called)
# ---------------------------------------------------------------------------

_latex_parser = None
_jd_analyzer = None
_resume_matcher = None
_ai_rewrite_engine = None
_latex_patcher = None


def _get_parser():
    global _latex_parser
    if _latex_parser is None:
        from app.services.latex_parser import parse_resume
        _latex_parser = parse_resume
    return _latex_parser


def _get_jd_analyzer():
    global _jd_analyzer
    if _jd_analyzer is None:
        from app.services.jd_analyzer import analyze_jd
        _jd_analyzer = analyze_jd
    return _jd_analyzer


def _get_matcher():
    global _resume_matcher
    if _resume_matcher is None:
        from app.services.resume_matcher import match_resume_to_jd
        _resume_matcher = match_resume_to_jd
    return _resume_matcher


def _get_rewrite_engine():
    global _ai_rewrite_engine
    if _ai_rewrite_engine is None:
        from app.services.ai_rewrite_engine import generate_ai_rewrite_suggestions
        _ai_rewrite_engine = generate_ai_rewrite_suggestions
    return _ai_rewrite_engine


def _get_patcher():
    global _latex_patcher
    if _latex_patcher is None:
        from app.services.latex_patcher import patch_bullet_in_tex
        _latex_patcher = patch_bullet_in_tex
    return _latex_patcher


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server("roletailor")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="parse_resume",
            description="Parse a LaTeX resume (from Overleaf or any LaTeX editor) into structured JSON. "
            "Handles custom macros like \\resumeItem, \\resumeSubheading, etc. "
            "Returns sections, bullets with IDs, skills, experience entries, projects, and education.",
            inputSchema={
                "type": "object",
                "properties": {
                    "latex_code": {
                        "type": "string",
                        "description": "Complete LaTeX source code of the resume",
                    },
                },
                "required": ["latex_code"],
            },
        ),
        Tool(
            name="analyze_job_description",
            description="Analyze a job description to extract keywords, must-have requirements, "
            "preferred skills, responsibilities, and seniority level.",
            inputSchema={
                "type": "object",
                "properties": {
                    "jd_text": {
                        "type": "string",
                        "description": "Full text of the job description",
                    },
                },
                "required": ["jd_text"],
            },
        ),
        Tool(
            name="match_resume_to_jd",
            description="Match a parsed resume against a job description. "
            "Returns match scores per bullet, weak bullets (low keyword overlap), "
            "and a list of keywords from the JD missing in the resume.",
            inputSchema={
                "type": "object",
                "properties": {
                    "resume_json": {
                        "type": "object",
                        "description": "Parsed resume JSON (output from parse_resume)",
                    },
                    "jd_text": {
                        "type": "string",
                        "description": "Full text of the job description",
                    },
                },
                "required": ["resume_json", "jd_text"],
            },
        ),
        Tool(
            name="generate_suggestions",
            description="Use Gemini AI to generate rewrite suggestions for resume bullets. "
            "Each suggestion includes original text, suggested rewrite, added keywords, "
            "a reason for the change, and a confidence score (high/medium/low). "
            "Only bullets that benefit from optimization are included.",
            inputSchema={
                "type": "object",
                "properties": {
                    "resume_json": {
                        "type": "object",
                        "description": "Parsed resume JSON (output from parse_resume)",
                    },
                    "jd_text": {
                        "type": "string",
                        "description": "Full text of the job description",
                    },
                },
                "required": ["resume_json", "jd_text"],
            },
        ),
        Tool(
            name="apply_suggestions",
            description="Apply accepted rewrite suggestions back to the original LaTeX code. "
            "Takes the original LaTeX, the parsed resume JSON, and a list of accepted "
            "suggestions (bullet_id + new_text). Returns the updated LaTeX code.",
            inputSchema={
                "type": "object",
                "properties": {
                    "latex_code": {
                        "type": "string",
                        "description": "Original LaTeX source code of the resume",
                    },
                    "resume_json": {
                        "type": "object",
                        "description": "Parsed resume JSON (output from parse_resume)",
                    },
                    "accepted_suggestions": {
                        "type": "array",
                        "description": "List of accepted suggestions, each with bullet_id and new_text",
                        "items": {
                            "type": "object",
                            "properties": {
                                "bullet_id": {"type": "string"},
                                "new_text": {"type": "string"},
                            },
                            "required": ["bullet_id", "new_text"],
                        },
                    },
                },
                "required": ["latex_code", "resume_json", "accepted_suggestions"],
            },
        ),
        Tool(
            name="compile_pdf",
            description="Compile LaTeX code to PDF. Requires pdflatex to be installed. "
            "Returns the PDF as base64-encoded bytes, or an error message if "
            "pdflatex is not available. Note: Overleaf users can skip this tool "
            "and compile directly in Overleaf.",
            inputSchema={
                "type": "object",
                "properties": {
                    "latex_code": {
                        "type": "string",
                        "description": "LaTeX source code to compile",
                    },
                },
                "required": ["latex_code"],
            },
        ),
        Tool(
            name="list_resumes",
            description="List all uploaded master resumes with summary info "
            "(company names, bullet count, skill count, upload date).",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="delete_resume",
            description="Delete a master resume and all linked data "
            "(parsed JSON, generated .tex, .pdf, .log files).",
            inputSchema={
                "type": "object",
                "properties": {
                    "resume_id": {
                        "type": "string",
                        "description": "The resume ID to delete",
                    },
                },
                "required": ["resume_id"],
            },
        ),
        Tool(
            name="generate_cover_letter",
            description="Generate a tailored LaTeX cover letter based on "
            "the parsed resume and job description using Gemini AI.",
            inputSchema={
                "type": "object",
                "properties": {
                    "resume_json": {
                        "type": "object",
                        "description": "Parsed resume JSON (output from parse_resume)",
                    },
                    "jd_text": {
                        "type": "string",
                        "description": "Full text of the job description",
                    },
                    "company_name": {
                        "type": "string",
                        "description": "Target company name (optional)",
                    },
                    "hiring_manager": {
                        "type": "string",
                        "description": "Hiring manager name (optional, defaults to 'Hiring Manager')",
                    },
                    "candidate_name": {
                        "type": "string",
                        "description": "Candidate's full name (optional, uses CANDIDATE_NAME from .env if not set)",
                    },
                },
                "required": ["resume_json", "jd_text"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        result = await _dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


async def _dispatch(name: str, args: dict) -> Any:
    if name == "parse_resume":
        latex_code = args["latex_code"]
        resume_id = "mcp_resume"
        parsed = _get_parser()(latex_code, resume_id)
        return parsed.model_dump()

    elif name == "analyze_job_description":
        jd_text = args["jd_text"]
        return _get_jd_analyzer()(jd_text)

    elif name == "match_resume_to_jd":
        resume_json = args["resume_json"]
        jd_text = args["jd_text"]
        jd_analysis = _get_jd_analyzer()(jd_text)
        return _get_matcher()(resume_json, jd_analysis)

    elif name == "generate_suggestions":
        resume_json = args["resume_json"]
        jd_text = args["jd_text"]
        jd_analysis = _get_jd_analyzer()(jd_text)
        match_result = _get_matcher()(resume_json, jd_analysis)

        try:
            suggestions = _get_rewrite_engine()(resume_json, jd_analysis, match_result)
            source = "ai"
        except Exception as e:
            # Fallback to heuristic engine
            from app.services.rewrite_engine import generate_rewrite_suggestions
            suggestions = generate_rewrite_suggestions(resume_json, match_result)
            source = f"fallback (AI error: {e})"

        return {
            "jd_keywords": jd_analysis["keywords"],
            "missing_keywords": match_result["missing_keywords"],
            "suggestions": suggestions,
            "source": source,
        }

    elif name == "apply_suggestions":
        latex_code = args["latex_code"]
        resume_json = args["resume_json"]
        accepted = args["accepted_suggestions"]

        updated_tex = latex_code
        applied = []
        failed = []

        patcher = _get_patcher()

        for s in accepted:
            try:
                updated_tex = patcher(
                    updated_tex,
                    resume_json,
                    s["bullet_id"],
                    s["new_text"],
                )
                applied.append(s["bullet_id"])
            except Exception as e:
                failed.append({"bullet_id": s["bullet_id"], "error": str(e)})

        return {
            "latex_code": updated_tex,
            "applied_count": len(applied),
            "applied_bullet_ids": applied,
            "failed": failed,
        }

    elif name == "compile_pdf":
        latex_code = args["latex_code"]
        return _compile_latex(latex_code)

    elif name == "list_resumes":
        return _list_resumes()

    elif name == "delete_resume":
        return _delete_resume(args["resume_id"])

    elif name == "generate_cover_letter":
        resume_json = args["resume_json"]
        jd_text = args["jd_text"]
        company_name = args.get("company_name", "")
        hiring_manager = args.get("hiring_manager", "Hiring Manager")

        jd_analysis = _get_jd_analyzer()(jd_text)
        matcher = _get_matcher()
        match_result = matcher(resume_json, jd_analysis)

        from app.services.cover_letter_generator import generate_cover_letter as gen_cl
        text = gen_cl(
            parsed_resume=resume_json,
            jd_analysis=jd_analysis,
            match_result=match_result,
            company_name=company_name or jd_analysis.get("company_name", ""),
            hiring_manager=hiring_manager,
            candidate_name=args.get("candidate_name", ""),
        )
        return {"text": text, "company_name": jd_analysis.get("company_name", ""), "status": "generated"}

    else:
        raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Resume management helpers
# ---------------------------------------------------------------------------

def _list_resumes() -> list:
    """Return all master resumes with summaries."""
    import glob, os, datetime
    from app.utils.file_helpers import RESUME_MASTER_DIR, RESUME_PARSED_DIR, load_json

    resumes = []
    for tex_path in sorted(
        glob.glob(os.path.join(RESUME_MASTER_DIR, "*.tex")),
        key=os.path.getmtime, reverse=True,
    ):
        filename = os.path.basename(tex_path)
        resume_id = filename.replace(".tex", "")
        parsed_path = os.path.join(RESUME_PARSED_DIR, f"{resume_id}.json")

        summary = {
            "resume_id": resume_id,
            "filename": filename,
            "companies": [],
            "bullet_count": 0,
            "skill_count": 0,
            "uploaded_at": datetime.datetime.fromtimestamp(os.path.getmtime(tex_path)).isoformat(),
        }
        if os.path.exists(parsed_path):
            try:
                p = load_json(parsed_path)
                summary["companies"] = [e["company"] for e in p.get("experience", [])]
                summary["bullet_count"] = sum(len(e.get("bullets", [])) for e in p.get("experience", [])) + sum(len(pr.get("bullets", [])) for pr in p.get("projects", []))
                summary["skill_count"] = len(p.get("skills", []))
            except Exception:
                pass
        resumes.append(summary)
    return resumes


def _delete_resume(resume_id: str) -> dict:
    """Delete a master resume and all linked data."""
    import glob, os
    from app.utils.file_helpers import RESUME_MASTER_DIR, RESUME_PARSED_DIR, RESUME_GENERATED_DIR

    deleted = []
    not_found = True

    for path in [
        os.path.join(RESUME_MASTER_DIR, f"{resume_id}.tex"),
        os.path.join(RESUME_PARSED_DIR, f"{resume_id}.json"),
    ]:
        if os.path.exists(path):
            os.remove(path)
            deleted.append(os.path.basename(path))
            not_found = False

    for path in glob.glob(os.path.join(RESUME_GENERATED_DIR, f"{resume_id}_*")):
        os.remove(path)
        deleted.append(os.path.basename(path))

    if not_found:
        raise ValueError(f"Resume {resume_id} not found")

    return {"resume_id": resume_id, "deleted_files": deleted, "count": len(deleted), "status": "deleted"}


# ---------------------------------------------------------------------------
# PDF compilation helper
# ---------------------------------------------------------------------------

def _compile_latex(latex_code: str) -> dict:
    """Compile LaTeX to PDF using pdflatex. Returns base64 PDF or error."""
    import base64

    # Check if pdflatex is available
    try:
        subprocess.run(["pdflatex", "--version"], capture_output=True, check=True, timeout=5)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {
            "status": "error",
            "error": (
                "pdflatex is not installed or not in PATH. "
                "Install a LaTeX distribution (TeX Live, MiKTeX) or compile in Overleaf."
            ),
        }

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "resume.tex")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_code)

        try:
            # First pass
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "resume.tex"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            # Second pass (for ToC, references, etc.)
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "resume.tex"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            pdf_path = os.path.join(tmpdir, "resume.pdf")
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                return {
                    "status": "success",
                    "pdf_base64": base64.b64encode(pdf_bytes).decode("utf-8"),
                    "size_bytes": len(pdf_bytes),
                }
            else:
                return {"status": "error", "error": "PDF was not generated — check LaTeX for errors"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "PDF compilation timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
