from typing import Dict, List


def enrich_bullet_with_keywords(bullet_text: str, missing_keywords: List[str], jd_keywords: List[str]) -> Dict:
    """
    Placeholder rewrite engine before LLM integration.
    Generates a structured suggestion shell.
    """

    added_keywords = []
    suggestion = bullet_text.strip()

    # simple keyword-aware enrichments
    keyword_phrases = {
        "backend": "backend systems",
        "api": "APIs",
        "distributed systems": "distributed systems",
        "docker": "containerized deployment",
        "iot": "IoT infrastructure",
        "microservices": "microservices architecture",
        "aws": "AWS cloud environment",
        "redis": "Redis-backed workflows",
        "postgresql": "PostgreSQL-backed persistence",
        "go": "Go services"
    }

    for kw in jd_keywords:
        if kw.lower() not in suggestion.lower() and kw in keyword_phrases:
            if kw in missing_keywords:
                suggestion += f", contributing to {keyword_phrases[kw]}"
                added_keywords.append(kw)

        if len(added_keywords) >= 2:
            break

    return {
        "original_text": bullet_text,
        "suggested_text": suggestion,
        "added_keywords": added_keywords,
        "reason": "Improves alignment with the JD by incorporating missing or underrepresented role-relevant terminology.",
        "confidence": "medium"
    }


def generate_rewrite_suggestions(parsed_resume: Dict, match_result: Dict, max_suggestions: int = 5) -> List[Dict]:
    weak_bullets = match_result.get("weak_bullets", [])
    missing_keywords = match_result.get("missing_keywords", [])
    jd_keywords = match_result.get("jd_keywords", [])

    suggestions = []

    for bullet in weak_bullets[:max_suggestions]:
        rewrite = enrich_bullet_with_keywords(
            bullet_text=bullet["text"],
            missing_keywords=missing_keywords,
            jd_keywords=jd_keywords
        )

        suggestions.append({
            "bullet_id": bullet["bullet_id"],
            "section": bullet["section"],
            "parent": bullet["parent"],
            **rewrite
        })

    return suggestions