import re
from typing import Dict, List


COMMON_SKILLS = [
    "go", "golang", "python", "java", "c++", "javascript", "typescript",
    "docker", "kubernetes", "redis", "postgresql", "mysql", "mongodb",
    "aws", "gcp", "azure", "linux", "grpc", "rest", "microservices",
    "distributed systems", "elasticsearch", "ci/cd", "mqtt", "auth0",
    "system design", "concurrency", "backend", "api", "iot"
]


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def extract_keywords(text: str) -> List[str]:
    normalized = normalize_text(text)
    found = []

    for skill in COMMON_SKILLS:
        if skill in normalized:
            found.append(skill)

    return sorted(list(set(found)))


def extract_bullet_lines(text: str) -> List[str]:
    lines = text.splitlines()
    bullets = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith(("-", "•", "*")):
            bullets.append(line.lstrip("-•* ").strip())
        else:
            bullets.append(line)

    return bullets


def analyze_jd(jd_text: str) -> Dict:
    normalized = normalize_text(jd_text)

    keywords = extract_keywords(jd_text)
    bullet_lines = extract_bullet_lines(jd_text)

    must_have = []
    preferred = []
    responsibilities = []

    for line in bullet_lines:
        l = line.lower().strip()

        # Skip section headers (lines that are just "Requirements:" or "Preferred:")
        if l in ("requirements:", "preferred:", "responsibilities:", "qualifications:",
                  "requirements", "preferred", "responsibilities", "qualifications",
                  "you will:", "what you'll do:", "about the role:"):
            continue

        if any(x in l for x in ["must", "required", "requirement", "need to have"]):
            must_have.append(line)
        elif any(x in l for x in ["preferred", "good to have", "nice to have", "plus"]):
            preferred.append(line)
        else:
            responsibilities.append(line)

    seniority = "unknown"
    if any(x in normalized for x in ["intern", "internship"]):
        seniority = "intern"
    elif any(x in normalized for x in ["junior", "sde 1", "entry level"]):
        seniority = "junior"
    elif any(x in normalized for x in ["sde 2", "mid-level", "2+ years"]):
        seniority = "mid"
    elif any(x in normalized for x in ["senior", "lead", "staff", "5+ years"]):
        seniority = "senior"

    # Try to extract company name from first few lines
    company_name = _extract_company_name(jd_text)

    return {
        "keywords": keywords,
        "must_have": must_have,
        "preferred": preferred,
        "responsibilities": responsibilities,
        "seniority": seniority,
        "company_name": company_name,
        "raw_text": jd_text,
    }


def _extract_company_name(jd_text: str) -> str:
    """
    Heuristically extract the company name from a job description.
    Looks for common patterns like 'About [Company]', 'at [Company]', etc.
    """
    import re as _re

    lines = jd_text.strip().splitlines()
    # Take first 15 lines for searching
    head = "\n".join(lines[:15])

    patterns = [
        r"(?:at|About|join)\s+([A-Z][A-Za-z0-9\s&.,]+?)(?:\s*(?:is|are|we|,|\.|—|–|\n|$))",
        r"([A-Z][A-Za-z0-9]+(?:\s[A-Z][A-Za-z0-9]+){0,3})\s+is\s+(?:a\s+)?(?:looking|seeking|hiring)",
        r"^([A-Z][A-Za-z0-9]+(?:\s[A-Z][A-Za-z0-9]+){0,3})\s*$",
    ]

    for pattern in patterns:
        match = _re.search(pattern, head)
        if match:
            name = match.group(1).strip().rstrip(".,;")
            if len(name) >= 2 and not any(
                kw in name.lower()
                for kw in ["senior", "junior", "engineer", "developer", "job", "position", "role"]
            ):
                return name

    return ""