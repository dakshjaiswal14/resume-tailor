"""
LaTeX bullet patcher — replaces bullet text in .tex files using the raw_latex
snippets stored during parsing.  Falls back to fuzzy ID-based matching when
exact string match fails (e.g. after whitespace changes).
"""

import re

from app.utils.latex_utils import escape_latex, normalize_latex_formatting


def patch_bullet_in_tex(
    tex_content: str,
    parsed_resume: dict,
    bullet_id: str,
    new_text: str,
) -> str:
    """
    Replace a single bullet in `tex_content` identified by `bullet_id`.
    Uses the stored `raw_latex` for exact-match replacement; falls back to
    searching for the bullet by its ID pattern when exact match fails.
    """
    target_raw_latex = _find_raw_latex(parsed_resume, bullet_id)

    if not target_raw_latex:
        raise ValueError(f"Bullet ID {bullet_id} not found in parsed resume")

    # Normalize AI formatting mistakes, then escape for LaTeX safety
    clean_text = normalize_latex_formatting(new_text)
    safe_new_text = escape_latex(clean_text)
    updated_latex = f"\\item[$\\circ$] {{{safe_new_text}}}"

    # --- exact match ---
    if target_raw_latex in tex_content:
        return tex_content.replace(target_raw_latex, updated_latex, 1)

    # --- fuzzy fallback: try normalising whitespace ---
    import re as _re

    pattern = _re.escape(target_raw_latex)
    pattern = _re.sub(r"\\s+", r"\\\\s+", pattern)
    if _re.search(pattern, tex_content):
        return _re.sub(pattern, updated_latex, tex_content, count=1)

    # --- bullet-id fallback: search for the underlying \item / \resumeItem ---
    # Build a regex that looks for any bullet command and replaces it.
    bullet_fallback = _find_bullet_by_id(tex_content, parsed_resume, bullet_id)
    if bullet_fallback:
        return tex_content.replace(bullet_fallback, updated_latex, 1)

    raise ValueError(
        f"Could not locate bullet {bullet_id} in .tex file "
        f"(exact match, fuzzy match, and ID-based search all failed)"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_raw_latex(parsed_resume: dict, bullet_id: str) -> str | None:
    """Walk the parsed resume tree to find raw_latex for a bullet ID."""
    for section in ("experience", "projects"):
        for entry in parsed_resume.get(section, []):
            for bullet in entry.get("bullets", []):
                if bullet.get("id") == bullet_id:
                    return bullet.get("raw_latex")
    return None


def _find_bullet_by_id(
    tex_content: str,
    parsed_resume: dict,
    bullet_id: str,
) -> str | None:
    """
    Attempt to locate a bullet in the original .tex by walking through
    parsed entries in order and extracting the n-th bullet's raw LaTeX.
    This is a best-effort fallback when the stored raw_latex doesn't match.
    """
    parts = bullet_id.rsplit("_", 2)  # e.g. exp_1_bullet_3 → ["exp", "1", "bullet_3"]
    if len(parts) < 3:
        return None

    section_type = parts[0]  # "exp" or "proj"
    entry_idx = int(parts[1]) - 1  # 0-indexed
    bullet_num = int(parts[2].replace("bullet_", ""))

    if section_type == "exp":
        entries = parsed_resume.get("experience", [])
    elif section_type == "proj":
        entries = parsed_resume.get("projects", [])
    else:
        return None

    if entry_idx >= len(entries):
        return None

    bullets = entries[entry_idx].get("bullets", [])
    if bullet_num > len(bullets):
        return None

    # The raw_latex stored might be correct — try it
    raw = bullets[bullet_num - 1].get("raw_latex")
    if raw and raw in tex_content:
        return raw

    return None
