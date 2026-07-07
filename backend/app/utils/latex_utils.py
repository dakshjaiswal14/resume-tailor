import re
from typing import Dict, Optional, Tuple


def escape_latex(text: str) -> str:
    """
    Escape LaTeX special characters for safe insertion into .tex files.
    Does NOT escape backslashes or braces — backslashes are LaTeX commands,
    and braces are structural (e.g. \\textbf{{text}}). The AI outputs
    properly-formatted LaTeX; we only escape truly unsafe literal chars.
    """
    if not text:
        return text

    replacements = [
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]

    for char, escaped in replacements:
        text = text.replace(char, escaped)

    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Brace-aware extraction — handles nested { } correctly
# ---------------------------------------------------------------------------

def find_matching_brace(text: str, start_pos: int) -> int:
    """
    Given the position of an opening '{', return the position of the
    matching closing '}'.  Handles arbitrarily nested braces.
    Raises ValueError if no matching brace is found.
    """
    if start_pos >= len(text) or text[start_pos] != "{":
        raise ValueError(f"No opening brace at position {start_pos}")

    depth = 0
    i = start_pos
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 1  # skip escaped character
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1

    raise ValueError(f"No matching closing brace for opening brace at {start_pos}")


def extract_braced_content(text: str, start_pos: int) -> Tuple[str, int]:
    """
    Extract content between '{' at start_pos and its matching '}'.
    Returns (content_between_braces, position_of_closing_brace).
    """
    end = find_matching_brace(text, start_pos)
    return text[start_pos + 1 : end], end


def extract_command_arg(text: str, cmd_start: int) -> Tuple[str, int]:
    """
    Starting just past a command name, extract the next braced argument.
    Handles optional [args] and mandatory {args}.
    Returns (content, position_after_closing_brace).
    Skips leading whitespace.
    """
    pos = cmd_start

    # skip whitespace
    while pos < len(text) and text[pos] in (" ", "\t", "\n", "\r"):
        pos += 1

    if pos >= len(text):
        raise ValueError("Expected argument but reached end of text")

    if text[pos] == "[":
        # optional argument — extract content between [ ]
        end = text.find("]", pos)
        if end == -1:
            raise ValueError("Unclosed optional argument")
        return text[pos + 1 : end], end + 1

    if text[pos] == "{":
        content, end = extract_braced_content(text, pos)
        return content, end + 1

    raise ValueError(f"Expected '{{' or '[' for argument, got '{text[pos]}'")


# ---------------------------------------------------------------------------
# Macro / \newcommand handling
# ---------------------------------------------------------------------------

# Known Overleaf resume-template macros and their standard-LaTeX expansions.
# Each entry is (regex_pattern, replacement_template).
# The replacement uses Python format-string style placeholders.
BUILTIN_MACRO_EXPANSIONS = {
    "resumeItem": lambda args: f"\\item[$\\circ$] {{{args[0]}}}",
    "resumeSubItem": lambda args: f"\\item[$\\circ$] {{{args[0]}}}",
    "resumeSubheading": lambda args: (
        f"\\item{{\\textbf{{{args[0]}}}}}  % company/name\n"
        f"\\textit{{{args[2]}}}  % role\n"
        f"{{{args[3]}}}  % dates"
    ),
    "resumeProjectHeading": lambda args: (
        f"\\item{{\\textbf{{{args[0]}}}}} {{{args[1]}}}"
    ),
    "resumeSubHeadingListStart": lambda args: "\\begin{{itemize}}[leftmargin=0.15in, label={{}}]",
    "resumeSubHeadingListEnd": lambda args: "\\end{{itemize}}",
    "resumeItemListStart": lambda args: "\\begin{{itemize}}[leftmargin=0.25in]",
    "resumeItemListEnd": lambda args: "\\end{{itemize}}\\vspace{{-5pt}}",
}


def parse_newcommands(tex_content: str) -> Dict[str, dict]:
    """
    Extract all \\newcommand (and \\renewcommand) definitions from the preamble.
    Returns a dict: macro_name -> {arg_count: int, definition: str}
    """
    macros = {}

    # Match \newcommand{\name}[n]{definition}  OR  \newcommand{\name}{definition}
    pattern = r"\\(?:re)?newcommand\s*\{\\([a-zA-Z]+)\}\s*(?:\[(\d+)\])?\s*\{"
    for match in re.finditer(pattern, tex_content):
        name = match.group(1)
        num_args = int(match.group(2)) if match.group(2) else 0

        # brace-aware extraction of definition
        defn_start = match.end() - 1  # position of opening {
        try:
            definition, _ = extract_braced_content(tex_content, defn_start)
        except ValueError:
            continue

        macros[name] = {"arg_count": num_args, "definition": definition}

    return macros


def _replace_macro_call(tex: str, macro_name: str, macro_info: dict) -> str:
    """
    Replace all calls to a custom macro with its expanded standard-LaTeX form.
    Handles macros with 0-4 arguments.
    """
    arg_count = macro_info["arg_count"]

    if macro_name in BUILTIN_MACRO_EXPANSIONS:
        expander = BUILTIN_MACRO_EXPANSIONS[macro_name]
    else:
        # Generic expansion using the stored definition
        definition = macro_info["definition"]
        expander = lambda args: _substitute_args(definition, args)

    result_parts = []
    i = 0
    cmd_pattern = re.compile(rf"\\{re.escape(macro_name)}\s*")

    while i < len(tex):
        match = cmd_pattern.search(tex, i)
        if not match:
            result_parts.append(tex[i:])
            break

        result_parts.append(tex[i : match.start()])
        pos = match.end()

        # Extract arguments
        args = []
        try:
            for _ in range(arg_count):
                arg, pos = extract_command_arg(tex, pos)
                args.append(arg)
        except ValueError:
            # Malformed call — keep original
            result_parts.append(match.group())
            i = match.end()
            continue

        # Expand
        try:
            expanded = expander(args)
        except Exception:
            expanded = match.group()

        result_parts.append(expanded)
        i = pos

    return "".join(result_parts)


def _substitute_args(definition: str, args: list) -> str:
    """Replace #1, #2, etc. in a macro definition with actual arguments."""
    result = definition
    for idx, arg in enumerate(args, start=1):
        result = result.replace(f"#{idx}", arg)
    return result


def expand_macros(tex_content: str) -> str:
    """
    Expand known resume-template macros into standard LaTeX.
    1. Auto-detect \\newcommand definitions
    2. Replace macro calls with standard \\item / \\begin{{itemize}} forms
    """
    macros = parse_newcommands(tex_content)
    expanded = tex_content

    # Expand macros that have definitions
    for name, info in macros.items():
        if name in BUILTIN_MACRO_EXPANSIONS:
            expanded = _replace_macro_call(expanded, name, info)

    # Also handle any BUILTIN_MACRO_EXPANSIONS not in the preamble
    # (some templates define these implicitly)
    for name in BUILTIN_MACRO_EXPANSIONS:
        if name not in macros:
            # Check if the macro is used anywhere
            if re.search(rf"\\{re.escape(name)}\b", expanded):
                info = {"arg_count": _guess_arg_count(name), "definition": ""}
                expanded = _replace_macro_call(expanded, name, info)

    return expanded


def _guess_arg_count(macro_name: str) -> int:
    """Guess argument count for known resume macros."""
    arg_counts = {
        "resumeItem": 1,
        "resumeSubItem": 1,
        "resumeSubheading": 4,
        "resumeProjectHeading": 2,
        "resumeSubHeadingListStart": 0,
        "resumeSubHeadingListEnd": 0,
        "resumeItemListStart": 0,
        "resumeItemListEnd": 0,
    }
    return arg_counts.get(macro_name, 0)


# ---------------------------------------------------------------------------
# Normalize AI-generated LaTeX — fix common formatting mistakes
# ---------------------------------------------------------------------------

def normalize_latex_formatting(text: str) -> str:
    """
    Fix common LaTeX formatting errors from AI-generated text:
    - Nested \\item wrapper (AI returns full bullet, patcher wraps again)
    - Double-backslash \\\\% → \\%
    - Escaped braces: \\textbf\\{{word\\}} → \\textbf{{word}}
    - Markdown bold: **word** → \\textbf{{word}}
    """
    if not text:
        return text

    # 0. STRIP OUTER \item WRAPPER (only if paired — both opening and closing exist)
    #    AI sometimes returns the full \item[$\circ$] {text} but patcher wraps again.
    #    Only strip the closing } if we actually stripped an opening \item wrapper.
    stripped_opening = False
    for pattern in [r"^\\item\s*\[\$\\circ\$\]\s*\{\s*", r"^\\item\s*\{\s*"]:
        m = re.match(pattern, text)
        if m:
            text = text[m.end():]
            stripped_opening = True
            break
    if stripped_opening:
        # Only strip trailing } if we removed the opening wrapper
        text = re.sub(r"\s*\}\s*$", "", text)

    # 1. FATAL: \\% → \%  (double backslash before % comments out closing brace)
    text = re.sub(r"\\\\%", r"\\%", text)

    # 2. Fix escaped braces inside LaTeX formatting commands
    for cmd in ["textbf", "textit", "emph", "underline", "texttt", "textsc"]:
        # \cmd\{word\} → \cmd{word}
        text = re.sub(rf"\\{cmd}\\{{", rf"\\{cmd}{{", text)
        text = re.sub(
            rf"(\\{cmd}\{{[^}}]+?)\\}}",
            rf"\1}}",
            text,
        )

    # 3. Fix Markdown bold: **text** → \textbf{text}
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)

    # 4. Fix Markdown italic (but not bullet * markers)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\\textit{\1}", text)

    # 5. Fix \hspace{...} → \hfill for large right-alignment hacks
    text = re.sub(r"\\hspace\{1[0-9]\.[0-9]+cm\}", r"\\hfill", text)

    return text


# ---------------------------------------------------------------------------
# Post-generation integrity check — validates & auto-fixes the complete .tex
# ---------------------------------------------------------------------------

def validate_and_fix_tex(tex_content: str) -> dict:
    """
    Final integrity check on the complete .tex file after all patches are applied.
    Auto-fixes common errors and returns a report of what was found/fixed.

    Returns: {"tex": fixed_content, "fixes": [...], "errors": [...]}
    """
    fixes = []
    errors = []
    fixed = tex_content

    # ---- 1. Fix \\\\% → \\% everywhere in the document ----
    count = fixed.count(chr(92) + chr(92) + '%')
    if count > 0:
        fixed = fixed.replace(chr(92) + chr(92) + '%', chr(92) + '%')
        fixes.append(f"Fixed {count} occurrence(s) of double-backslash-percent to single")

    # ---- 2. Fix escaped braces \\{ and \\} inside text ----
    for cmd in ["textbf", "textit", "emph", "underline", "texttt", "textsc"]:
        pattern_open = chr(92) + cmd + chr(92) + '{'   # \textbf\{
        if pattern_open in fixed:
            count = fixed.count(pattern_open)
            correct = chr(92) + cmd + '{'
            fixed = fixed.replace(pattern_open, correct)
            fixes.append(f"Fixed {count} escaped open-brace in \\{cmd}")

    # ---- 3. Fix Markdown bold: **text** → \\textbf{text} ----
    md_bold = re.findall(r"\*\*(.+?)\*\*", fixed)
    if md_bold:
        for match in set(md_bold):
            fixed = fixed.replace(f"**{match}**", f"\\textbf{{{match}}}")
        fixes.append(f"Fixed {len(md_bold)} Markdown **bold** to \\textbf{{}}")

    # ---- 4. Check brace balance ----
    open_count = fixed.count('{')
    close_count = fixed.count('}')
    if open_count != close_count:
        errors.append(
            f"Brace mismatch: {open_count} open vs {close_count} close "
            f"(diff={open_count - close_count:+d}). Check for missing/extra braces."
        )

    # ---- 5. Check \\begin / \\end pairs ----
    begins = re.findall(r"\\begin\{([^}]+)\}", fixed)
    ends = re.findall(r"\\end\{([^}]+)\}", fixed)
    begin_counts = {}
    end_counts = {}
    for b in begins:
        begin_counts[b] = begin_counts.get(b, 0) + 1
    for e in ends:
        end_counts[e] = end_counts.get(e, 0) + 1
    for env in set(list(begin_counts.keys()) + list(end_counts.keys())):
        bc = begin_counts.get(env, 0)
        ec = end_counts.get(env, 0)
        if bc != ec:
            errors.append(
                f"Environment '{env}': {bc} \\begin vs {ec} \\end"
            )

    # ---- 6. Check \\end{document} exists ----
    if r'\end{document}' not in fixed:
        errors.append("Missing \\end{document} — file will not compile")

    # ---- 7. Check no \item outside itemize ----
    # (basic check — look for \item not preceded by \begin{itemize} on same line or prior)
    items = re.findall(r"\\item", fixed)
    if items:
        itemize_envs = len(re.findall(r"\\begin\{itemize\}", fixed))
        if len(items) > 0 and itemize_envs == 0:
            errors.append(f"Found {len(items)} \\item commands but no itemize environments")

    return {"tex": fixed, "fixes": fixes, "errors": errors}



# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def clean_latex_text(text: str) -> str:
    """
    Strip LaTeX commands and formatting to produce plain, readable text.
    Used for keyword matching and AI prompts.
    Preserves content inside known commands like \\textbf, \\item, etc.
    """
    if not text:
        return ""

    # Step 1: Handle commands that WRAP content (keep the content)
    # These patterns extract the inner content from formatting commands
    wrap_commands = [
        (r"\\textbf\{(.*?)\}", r"\1"),
        (r"\\textit\{(.*?)\}", r"\1"),
        (r"\\emph\{(.*?)\}", r"\1"),
        (r"\\underline\{(.*?)\}", r"\1"),
        (r"\\texttt\{(.*?)\}", r"\1"),
        (r"\\textsc\{(.*?)\}", r"\1"),
        (r"\\textsf\{(.*?)\}", r"\1"),
        (r"\\textrm\{(.*?)\}", r"\1"),
    ]
    for pattern, repl in wrap_commands:
        text = re.sub(pattern, repl, text, flags=re.DOTALL)

    # Step 2: Handle \\href{url}{display} → display
    text = re.sub(r"\\href\{[^}]*\}\{(.*?)\}", r"\1", text, flags=re.DOTALL)

    # Step 3: Handle \\item{content} → content
    text = re.sub(r"\\item\s*\{", "", text)
    # Handle \\item[marker] {content} → content
    text = re.sub(r"\\item\s*\[[^\]]*\]\s*\{", "", text)

    # Step 4: Remove remaining LaTeX commands (keep their argument content)
    # \\command{arg} → arg
    text = re.sub(r"\\[a-zA-Z]+\*?\s*\{", "", text)
    # \\command[opt]{arg} → arg
    text = re.sub(r"\\[a-zA-Z]+\*?\s*\[[^\]]*\]\s*\{", "", text)

    # Step 5: Remove spacing/sizing commands that have no args
    text = re.sub(r"\\[a-zA-Z]+\*?\s+", " ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?\b", "", text)

    # Step 6: Handle special characters
    text = text.replace(r"\&", "&")
    text = text.replace(r"\'", "'")
    text = text.replace(r"\"", '"')
    text = text.replace(r"\_", "_")
    text = text.replace(r"\$", "$")
    text = text.replace(r"\%", "%")
    text = text.replace(r"\#", "#")
    text = text.replace(r"\textbackslash{}", "\\")

    # Step 7: Remove stray braces
    text = text.replace("{", "").replace("}", "")

    # Step 8: Normalize whitespace
    text = " ".join(text.split())
    return text.strip()
