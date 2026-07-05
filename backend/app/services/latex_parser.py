"""
LaTeX resume parser — handles Overleaf-style templates with custom \\newcommand
macros as well as standard LaTeX.  Uses brace-aware extraction so that nested
braces (e.g. \\textbf{...} inside a bullet) are captured correctly.

Supports two common Overleaf resume formats:

Format A — Custom macros (e.g. Jake's Resume template on Overleaf):
    \\section{Experience}
    \\resumeSubHeadingListStart
      \\resumeSubheading{Company}{Location}{Role}{Dates}
      \\resumeItemListStart
        \\resumeItem{bullet text}
      \\resumeItemListEnd
    \\resumeSubHeadingListEnd

Format B — Standard LaTeX:
    \\section{Work Experience}
    \\begin{itemize}[leftmargin=0.15in]
      \\item{\\textbf{Company}} ...
      \\begin{itemize}
        \\item[$\\circ$] {bullet text}
      \\end{itemize}
    \\end{itemize}
"""

import re
from typing import List, Tuple

from app.models.schemas import (
    ResumeModel,
    ResumeBullet,
    ExperienceItem,
    ProjectItem,
    EducationItem,
)
from app.utils.latex_utils import (
    extract_braced_content,
    extract_command_arg,
    clean_latex_text,
)


# ---------------------------------------------------------------------------
# Comment stripping
# ---------------------------------------------------------------------------

def strip_comments(tex: str) -> str:
    """Remove LaTeX comments."""
    cleaned = []
    for line in tex.splitlines():
        stripped = line.strip()
        if stripped.startswith("%"):
            continue
        line = re.sub(r"(?<!\\)%.*", "", line)
        cleaned.append(line)
    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

SECTION_TITLES = {
    "experience": ["experience", "work experience", "employment"],
    "projects": ["projects", "project", "personal projects"],
    "education": ["education"],
    "skills": ["technical skills", "skills", "programming skills / coursework", "programming skills"],
    "achievements": ["achievements", "accomplishments"],
    "responsibility": ["positions of responsibility", "leadership"],
}


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _get_section_body(tex: str, section_names: list) -> str | None:
    """Return the body text between \\section{<name>} and the next \\section or \\end{document}."""
    for name in section_names:
        pattern = rf"\\section\{{{re.escape(name)}\}}"
        m = re.search(pattern, tex, re.IGNORECASE)
        if not m:
            continue

        body_start = m.end()
        remainder = tex[body_start:]

        # Find next \section or \end{document}
        next_sec = re.search(r"\\section\s*\{", remainder)
        end_doc = re.search(r"\\end\{document\}", remainder)

        body_end = len(remainder)
        if next_sec:
            body_end = next_sec.start()
        if end_doc and end_doc.start() < body_end:
            body_end = end_doc.start()

        return remainder[:body_end]

    return None


# ---------------------------------------------------------------------------
# Block finder — handles BOTH custom macros AND standard \\begin{itemize}
# ---------------------------------------------------------------------------

# Pairs of (start_marker, end_marker) for list-like environments
LIST_PAIRS = [
    # Custom Overleaf macros
    (r"\\resumeSubHeadingListStart", r"\\resumeSubHeadingListEnd"),
    (r"\\resumeItemListStart", r"\\resumeItemListEnd"),
    # Standard LaTeX
    (r"\\begin\{itemize\}(?:\[[^\]]*\])?", r"\\end\{itemize\}"),
    (r"\\begin\{enumerate\}(?:\[[^\]]*\])?", r"\\end\{enumerate\}"),
]


def _find_list_blocks(block: str) -> List[Tuple[int, int, str]]:
    """
    Find all top-level list blocks (itemize, enumerate, or custom macro equivalents).
    Returns [(start, end, marker_type), ...] where marker_type is 'itemize', 'enumerate', or 'custom'.
    Handles nesting correctly.
    """
    # Build combined patterns
    start_patterns = []
    for start_re, end_re in LIST_PAIRS:
        start_patterns.append((start_re, end_re))

    # Find all start/end markers
    markers = []
    for idx, (start_re, end_re) in enumerate(start_patterns):
        for m in re.finditer(start_re, block):
            markers.append((m.start(), "start", idx, m.group()))
        for m in re.finditer(end_re, block):
            markers.append((m.start(), "end", idx, m.group()))

    markers.sort(key=lambda x: x[0])

    # Match starts to ends (respecting nesting). Only return TOP-LEVEL blocks.
    blocks = []
    stack = []

    for pos, kind, pair_idx, text in markers:
        if kind == "start":
            stack.append((pos, pair_idx))
        elif kind == "end":
            # Find matching start on stack (search backwards for same type)
            for si in range(len(stack) - 1, -1, -1):
                if stack[si][1] == pair_idx:
                    start_pos, _ = stack.pop(si)
                    # Only include top-level blocks (when stack is now empty)
                    if len(stack) == 0:
                        blocks.append((start_pos, pos + len(text), "list"))
                    break

    return blocks


# ---------------------------------------------------------------------------
# Bullet extraction
# ---------------------------------------------------------------------------

def _find_bullets_in_block(block: str, prefix: str) -> List[ResumeBullet]:
    """
    Extract bullets from a block. Handles:
      \\resumeItem{text}
      \\resumeSubItem{text}
      \\item[$\\circ$] {text}
      \\item {text}
    """
    bullets = []
    bullet_idx = 1
    i = 0

    bullet_start_res = [
        r"\\resume(?:Sub)?Item\s*\{",
        r"\\item\s*\[\$\\circ\$\]\s*\{",
        r"\\item\s*\{(?!\\textbf)",  # \item{text} but not \item{\textbf{...}} (those are headers)
    ]

    while i < len(block):
        best_start = float("inf")
        best_match = None

        for pat in bullet_start_res:
            m = re.search(pat, block[i:])
            if m:
                abs_start = i + m.start()
                if abs_start < best_start:
                    best_start = abs_start
                    best_match = (m, pat)

        if best_match is None:
            break

        match, _ = best_match
        abs_start = i + match.start()

        # Find the opening brace for the bullet text
        # For \resumeItem{...} or \item[...] {...}, the text is in the last braced group
        cmd_end = i + match.end()  # right after the command name + optional [ ]

        # Find the opening { of the text content
        # Skip any [ ] optional args
        pos = cmd_end - 1  # position of the last char of the command pattern
        # Actually, the pattern ends right before the first { of the content
        # Let me re-find the { directly
        brace_pos = block.find("{", abs_start)
        if brace_pos == -1:
            i = abs_start + 1
            continue

        try:
            content, closing_pos = extract_braced_content(block, brace_pos)
        except ValueError:
            i = abs_start + 1
            continue

        end_pos = closing_pos + 1
        raw_latex = block[abs_start:end_pos]

        cleaned = clean_latex_text(content)
        if cleaned.strip():
            bullets.append(
                ResumeBullet(
                    id=f"{prefix}_bullet_{bullet_idx}",
                    text=cleaned,
                    raw_latex=raw_latex,
                )
            )
            bullet_idx += 1

        i = end_pos

    return bullets


# ---------------------------------------------------------------------------
# Experience parser
# ---------------------------------------------------------------------------

def _parse_experience(tex: str) -> List[ExperienceItem]:
    body = _get_section_body(tex, SECTION_TITLES["experience"])
    if not body:
        return []

    experience = []
    exp_idx = 1

    # Each experience entry starts with \resumeSubheading{...}{...}{...}{...}
    # Find all resumeSubheading calls
    subhead_pattern = r"\\resumeSubheading\s*\{"
    subhead_matches = list(re.finditer(subhead_pattern, body))

    for idx, match in enumerate(subhead_matches):
        pos = match.end() - 1  # position of opening {

        try:
            company, pos = extract_braced_content(body, pos)
            company = clean_latex_text(company)
            location, pos = extract_command_arg(body, pos + 1)
            role, pos = extract_command_arg(body, pos)
            role = clean_latex_text(role) if role else ""
            dates, pos = extract_command_arg(body, pos)
            duration = clean_latex_text(dates) if dates else None
        except (ValueError, IndexError):
            continue

        # Determine the span of this entry (from this \resumeSubheading to the next, or to end of list)
        entry_start = match.start()
        if idx + 1 < len(subhead_matches):
            entry_end = subhead_matches[idx + 1].start()
        else:
            # End at the \resumeSubHeadingListEnd or end of body
            end_match = re.search(r"\\resumeSubHeadingListEnd", body[entry_start:])
            if end_match:
                entry_end = entry_start + end_match.start()
            else:
                entry_end = len(body)

        entry_block = body[entry_start:entry_end]

        # Find the bullet list within this entry
        # Bullets are between \resumeItemListStart and \resumeItemListEnd
        bullets = []
        item_list_start = re.search(r"\\resumeItemListStart", entry_block)
        item_list_end = re.search(r"\\resumeItemListEnd", entry_block)

        if item_list_start and item_list_end:
            bullet_block = entry_block[item_list_start.end() : item_list_end.start()]
            bullets = _find_bullets_in_block(bullet_block, f"exp_{exp_idx}")

        # If no bullets via custom macros, try standard itemize
        if not bullets:
            list_blocks = _find_list_blocks(entry_block)
            for lb_start, lb_end, _ in list_blocks:
                inner_block = entry_block[lb_start:lb_end]
                # Skip the first level (it's the entry header)
                inner_list_blocks = _find_list_blocks(inner_block)
                for ilb_start, ilb_end, _ in inner_list_blocks:
                    bullet_block = inner_block[ilb_start:ilb_end]
                    found = _find_bullets_in_block(bullet_block, f"exp_{exp_idx}")
                    bullets.extend(found)

        if company.strip():
            experience.append(
                ExperienceItem(
                    id=f"exp_{exp_idx}",
                    company=company,
                    role=role,
                    duration=duration,
                    bullets=bullets,
                )
            )
            exp_idx += 1

    # If no \resumeSubheading found, try standard LaTeX format
    if not experience:
        experience = _parse_experience_standard(body, exp_idx)

    return experience


def _parse_experience_standard(body: str, start_idx: int) -> List[ExperienceItem]:
    """Parse standard-LaTeX experience section (Format B)."""
    experience = []
    exp_idx = start_idx

    list_blocks = _find_list_blocks(body)
    for lb_start, lb_end, _ in list_blocks:
        block = body[lb_start:lb_end]

        # Company: \item{\textbf{Company}}
        company_match = re.search(r"\\item\s*\{\s*\\textbf\{(.+?)\}\s*\}", block, re.DOTALL)
        if not company_match:
            continue

        company = clean_latex_text(company_match.group(1))

        # Role: \textit{...}
        role_match = re.search(r"\\textit\{(.+?)\}", block, re.DOTALL)
        role = clean_latex_text(role_match.group(1)) if role_match else ""

        # Duration
        date_match = re.search(
            r"(\w{3}\s*'?\d{2}\s*[-–—]\s*(?:\w{3}\s*'?\d{2}|Present))",
            block,
        )
        duration = date_match.group(1) if date_match else None

        # Bullets from nested itemize
        bullets = []
        nested_blocks = _find_list_blocks(block)
        for ns, ne, _ in nested_blocks:
            inner = block[ns:ne]
            found = _find_bullets_in_block(inner, f"exp_{exp_idx}")
            bullets.extend(found)

        if not bullets:
            bullets = _find_bullets_in_block(block, f"exp_{exp_idx}")

        if company.strip():
            experience.append(
                ExperienceItem(
                    id=f"exp_{exp_idx}",
                    company=company,
                    role=role,
                    duration=duration,
                    bullets=bullets,
                )
            )
            exp_idx += 1

    return experience


# ---------------------------------------------------------------------------
# Projects parser
# ---------------------------------------------------------------------------

def _parse_projects(tex: str) -> List[ProjectItem]:
    body = _get_section_body(tex, SECTION_TITLES["projects"])
    if not body:
        return []

    projects = []
    proj_idx = 1

    # Find \resumeProjectHeading{Name}{Link}
    proj_head_pattern = r"\\resumeProjectHeading\s*\{"
    proj_matches = list(re.finditer(proj_head_pattern, body))

    for idx, match in enumerate(proj_matches):
        pos = match.end() - 1
        try:
            name, pos = extract_braced_content(body, pos)
            name = clean_latex_text(name)
            link, pos = extract_command_arg(body, pos + 1)
            link = clean_latex_text(link) if link else ""
        except (ValueError, IndexError):
            continue

        entry_start = match.start()
        if idx + 1 < len(proj_matches):
            entry_end = proj_matches[idx + 1].start()
        else:
            end_match = re.search(r"\\resumeSubHeadingListEnd", body[entry_start:])
            if end_match:
                entry_end = entry_start + end_match.start()
            else:
                entry_end = len(body)

        entry_block = body[entry_start:entry_end]

        # Find bullets
        bullets = []
        item_list_start = re.search(r"\\resumeItemListStart", entry_block)
        item_list_end = re.search(r"\\resumeItemListEnd", entry_block)
        if item_list_start and item_list_end:
            bullet_block = entry_block[item_list_start.end() : item_list_end.start()]
            bullets = _find_bullets_in_block(bullet_block, f"proj_{proj_idx}")

        if not bullets:
            list_blocks = _find_list_blocks(entry_block)
            for lb_start, lb_end, _ in list_blocks:
                inner = entry_block[lb_start:lb_end]
                found = _find_bullets_in_block(inner, f"proj_{proj_idx}")
                bullets.extend(found)

        if name.strip():
            projects.append(
                ProjectItem(
                    id=f"proj_{proj_idx}",
                    name=name,
                    bullets=bullets,
                )
            )
            proj_idx += 1

    # Fallback: standard LaTeX format
    if not projects:
        projects = _parse_projects_standard(body, proj_idx)

    return projects


def _parse_projects_standard(body: str, start_idx: int) -> List[ProjectItem]:
    """Parse standard-LaTeX projects section."""
    projects = []
    proj_idx = start_idx

    list_blocks = _find_list_blocks(body)
    for lb_start, lb_end, _ in list_blocks:
        block = body[lb_start:lb_end]

        name_match = re.search(r"\\item\s*\{\s*\\textbf\{(.+?)\}\s*\}", block, re.DOTALL)
        if not name_match:
            continue

        name = clean_latex_text(name_match.group(1))

        bullets = []
        nested_blocks = _find_list_blocks(block)
        for ns, ne, _ in nested_blocks:
            inner = block[ns:ne]
            found = _find_bullets_in_block(inner, f"proj_{proj_idx}")
            bullets.extend(found)

        if not bullets:
            bullets = _find_bullets_in_block(block, f"proj_{proj_idx}")

        if name.strip():
            projects.append(
                ProjectItem(
                    id=f"proj_{proj_idx}",
                    name=name,
                    bullets=bullets,
                )
            )
            proj_idx += 1

    return projects


# ---------------------------------------------------------------------------
# Education parser
# ---------------------------------------------------------------------------

def _parse_education(tex: str) -> List[EducationItem]:
    body = _get_section_body(tex, SECTION_TITLES["education"])
    if not body:
        return []

    education = []
    edu_idx = 1

    # \resumeSubheading{Institution}{Location}{Degree}{Dates}
    subhead_matches = list(re.finditer(r"\\resumeSubheading\s*\{", body))

    for match in subhead_matches:
        pos = match.end() - 1
        try:
            institution, pos = extract_braced_content(body, pos)
            institution = clean_latex_text(institution)
            location, pos = extract_command_arg(body, pos + 1)
            degree, pos = extract_command_arg(body, pos)
            degree = clean_latex_text(degree) if degree else ""
            dates, pos = extract_command_arg(body, pos)
            details = clean_latex_text(dates) if dates else None
        except (ValueError, IndexError):
            continue

        if institution.strip():
            education.append(
                EducationItem(
                    id=f"edu_{edu_idx}",
                    institution=institution,
                    degree=degree,
                    details=details,
                )
            )
            edu_idx += 1

    # Fallback: standard LaTeX format
    if not education:
        # Parse each \item{\textbf{Institution} ... \textit{Degree}} entry
        # Pattern: \item {\textbf{Institution}}\hspace{...}{Location}
        #          \textit{{Degree}\hspace{...}{Dates}}
        item_pattern = r"\\item\s*\{\s*\\textbf\{([^}]+)\}"
        for match in re.finditer(item_pattern, body):
            institution = clean_latex_text(match.group(1))
            degree = ""
            details = None

            # Look for \textit{...} after this item
            after = body[match.end():]
            # Find the next \item or end of body
            next_item = re.search(r"\\item\s*\{", after)
            search_end = next_item.start() if next_item else len(after)
            after_segment = after[:search_end]

            # Extract degree from \textit{...} (multi-line aware)
            degree_match = re.search(r"\\textit\s*\{(.+?)\}", after_segment, re.DOTALL)
            if degree_match:
                degree = clean_latex_text(degree_match.group(1))

            # Extract dates (handle full month names like July, March, etc.)
            date_match = re.search(
                r"(\w{3,9}\s*'?\d{2}\s*[-–—]\s*(?:\w{3,9}\s*'?\d{2}|Present))",
                after_segment
            )
            if date_match:
                details = date_match.group(1).strip()

            if institution.strip():
                education.append(
                    EducationItem(
                        id=f"edu_{edu_idx}",
                        institution=institution,
                        degree=degree,
                        details=details,
                    )
                )
                edu_idx += 1

    return education


# ---------------------------------------------------------------------------
# Skills parser
# ---------------------------------------------------------------------------

def _parse_skills(tex: str) -> List[str]:
    body = _get_section_body(tex, SECTION_TITLES["skills"])
    if not body:
        return []

    skills = []

    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue

        cleaned = clean_latex_text(line)

        # Skip structural / LaTeX-noise lines
        if not cleaned:
            continue
        if cleaned.startswith("\\"):
            continue
        if cleaned.startswith("[") or cleaned.startswith("]"):
            continue
        if cleaned in ("}", "\\small{", "\\small"):
            continue

        # Lines with "Category: value1, value2, value3"
        if ":" in cleaned:
            parts = cleaned.split(":", 1)
            cat = parts[0].strip()
            values = parts[1].strip()

            # Skip if the category looks like a LaTeX command or arg
            if cat.startswith("\\") or cat.startswith("[") or cat.startswith("]"):
                continue

            for item in values.split(","):
                item = item.strip().rstrip("\\\\").strip()
                if item and len(item) > 1 and not item.startswith("\\"):
                    skills.append(item)
        elif "," in cleaned and not cleaned.startswith("\\"):
            # Comma-separated values without category
            for item in cleaned.split(","):
                item = item.strip().rstrip("\\\\").strip()
                if item and len(item) > 1 and not item.startswith("\\"):
                    skills.append(item)

    return skills


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_resume(tex_content: str, resume_id: str) -> ResumeModel:
    """
    Parse a LaTeX resume into a structured ResumeModel.

    Handles Overleaf-style templates that use custom \\newcommand macros
    (e.g. \\resumeItem, \\resumeSubheading) as well as standard LaTeX.
    """
    tex_content = strip_comments(tex_content)

    return ResumeModel(
        resume_id=resume_id,
        skills=_parse_skills(tex_content),
        experience=_parse_experience(tex_content),
        projects=_parse_projects(tex_content),
        education=_parse_education(tex_content),
    )
