# RoleTailor AI

Tailor your LaTeX resume and generate cover letters for any job description using Gemini AI. Built with FastAPI + Next.js + MCP.

## Features

- **Resume Parsing** — Upload LaTeX from Overleaf, auto-extract sections, bullets, skills
- **JD Analysis** — Paste a job description, get keywords, requirements, seniority level
- **AI Suggestions** — Gemini rewrites bullet points to match JD keywords and tone
- **Accept/Reject** — Review each suggestion, accept only what you want
- **LaTeX Output** — Download the tailored `.tex` file, paste back into Overleaf
- **Cover Letters** — Generate plain-text cover letters, download as PDF
- **Resume Library** — Manage multiple resumes, delete with one click
- **MCP Server** — Use all features directly from Claude Code

---

## Prerequisites

| Tool | Mac (Homebrew) | Windows |
|------|---------------|---------|
| Python 3.11+ | `brew install python@3.11` | [python.org](https://python.org) |
| Node.js 18+ | `brew install node` | [nodejs.org](https://nodejs.org) |
| pnpm | `npm install -g pnpm` | `npm install -g pnpm` |
| Git | `brew install git` | [git-scm.com](https://git-scm.com) |
| pdflatex *(optional)* | `brew install --cask mactex` | [miktex.org](https://miktex.org) |
| Gemini API key | [aistudio.google.com](https://aistudio.google.com) | Same |

> **pdflatex is optional** — You can compile `.tex` files directly in Overleaf instead.

---

## Quick Start

### 1. Clone & enter

```bash
git clone <repo-url> role-tailor-ai
cd role-tailor-ai
```

### 2. Create `.env`

```bash
# Mac / Linux
cat > .env << 'EOF'
GEMINI_API_KEY=your_gemini_api_key_here
CANDIDATE_NAME=Your Full Name
LATEX_COMPILER=pdflatex
UPLOAD_DIR=./resumes
EOF
```

```powershell
# Windows PowerShell
@"
GEMINI_API_KEY=your_gemini_api_key_here
CANDIDATE_NAME=Your Full Name
LATEX_COMPILER=pdflatex
UPLOAD_DIR=./resumes
"@ | Out-File -FilePath .env -Encoding UTF8
```

### 3. Backend setup

```bash
cd backend

# Create virtual environment (Mac)
python3 -m venv venv
source venv/bin/activate

# Create virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Frontend setup

```bash
cd ../frontend
pnpm install
```

### 5. Start both servers

**Terminal 1 — Backend:**
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npx next dev --port 3000
```

### 6. Open the app

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend**: [http://localhost:8000](http://localhost:8000)

---

## MCP Server (Claude Code Integration)

Add to `~/.claude/mcp.json` (Mac) or `%USERPROFILE%\.claude\mcp.json` (Windows):

```json
{
  "mcpServers": {
    "roletailor": {
      "command": "python",
      "args": ["mcp-server/server.py"],
      "cwd": "/path/to/role-tailor-ai"
    }
  }
}
```

**MCP Tools available:**
| Tool | Description |
|------|-------------|
| `parse_resume` | Parse LaTeX resume → structured JSON |
| `analyze_job_description` | Extract keywords, seniority, requirements from JD |
| `match_resume_to_jd` | Score resume bullets against JD keywords |
| `generate_suggestions` | AI-powered bullet rewrites |
| `apply_suggestions` | Apply accepted changes → new LaTeX |
| `generate_cover_letter` | Create a tailored plain-text cover letter |
| `list_resumes` | List all uploaded resumes |
| `delete_resume` | Delete a resume and all linked files |
| `compile_pdf` | Compile LaTeX → PDF (needs pdflatex) |

---

## Usage Guide

### Tailor a Resume

1. **Upload** — Open [http://localhost:3000](http://localhost:3000), paste your Overleaf LaTeX or upload a `.tex` file. Give it a name.
2. **JD** — Paste the job description. The AI auto-detects the company name.
3. **Review** — Gemini suggests rewrites. Original is struck through, suggestion highlighted. Accept or reject each one.
4. **Apply** — Click "Apply Changes" → download the tailored `.tex` file.
5. **Overleaf** — Paste the new `.tex` into Overleaf and compile.

### Generate a Cover Letter

- After Step 4 above, click **"Generate Cover Letter"**
- Plain text appears — ready to copy-paste into application forms
- Click **"Download PDF"** to get a formatted PDF (requires pdflatex)

### Manage Resumes

- **Homepage** shows all your resumes with company tags, bullet counts
- **Click** a card to re-use a resume (no re-upload needed)
- **Hover** and click ✕ to delete (with confirmation)
- **Clear All** button wipes everything

---

## Project Structure

```
role-tailor-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + CORS
│   │   ├── models/schemas.py    # Pydantic data models
│   │   ├── routes/
│   │   │   ├── resume.py        # Upload, parse, patch, cover letter, delete
│   │   │   └── jd.py            # JD analysis, match, suggestions
│   │   ├── services/
│   │   │   ├── latex_parser.py           # Parse Overleaf LaTeX → JSON
│   │   │   ├── latex_patcher.py          # Replace bullets in .tex
│   │   │   ├── jd_analyzer.py            # Extract keywords, company, seniority
│   │   │   ├── resume_matcher.py         # Score bullets against JD
│   │   │   ├── ai_rewrite_engine.py      # Gemini-powered suggestions
│   │   │   ├── cover_letter_generator.py  # Gemini cover letter
│   │   │   ├── llm_client.py             # Gemini API wrapper
│   │   │   ├── resume_output_service.py  # Apply suggestions + compile PDF
│   │   │   └── ...                       # Heuristic fallback, validator
│   │   └── utils/
│   │       ├── file_helpers.py   # Path constants, JSON helpers
│   │       └── latex_utils.py    # Brace parsing, escaping, normalizer
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx              # Full multi-step UI
│   │   ├── layout.tsx            # Root layout
│   │   └── globals.css           # Tailwind styles
│   └── package.json
├── mcp-server/
│   ├── server.py                 # 9 MCP tools
│   └── requirements.txt
├── prompts/
│   ├── rewrite_generator.txt     # Resume bullet rewrite prompt
│   └── cover_letter.txt          # Cover letter generation prompt
├── resumes/                      # Created on first run
│   ├── master/                   # Uploaded .tex files
│   ├── parsed/                   # Extracted JSON
│   └── generated/                # Tailored output
├── .env                          # API keys (gitignored)
└── .gitignore
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | Google Gemini API key from [aistudio.google.com](https://aistudio.google.com) |
| `CANDIDATE_NAME` | No | Your full name (used in cover letters). Can also be set via the UI. |
| `LATEX_COMPILER` | No | `pdflatex` (default). Used for PDF compilation. |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `GEMINI_API_KEY not found` | Create `.env` in project root with `GEMINI_API_KEY=...` |
| Gemini call fails / fallback used | Check your API key is valid and has credits at [aistudio.google.com](https://aistudio.google.com) |
| `pdflatex not found` | Install LaTeX (`brew install --cask mactex` on Mac, MiKTeX on Windows) or compile in Overleaf |
| Frontend won't start | Run `pnpm install` in `frontend/` first |
| `No module named 'app'` | Make sure you're running `uvicorn` from the `backend/` directory |
| Cover letter has random name | Set `CANDIDATE_NAME` in `.env` or edit via the input on the homepage |
| `**bold**` instead of LaTeX | This is auto-fixed now — the normalizer catches and converts Markdown |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python) |
| Frontend | Next.js 16 + Tailwind CSS 4 (TypeScript) |
| AI | Google Gemini 2.5 Flash |
| MCP | Python MCP SDK |
| LaTeX | pdflatex (optional) |
