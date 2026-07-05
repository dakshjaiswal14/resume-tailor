from typing import Dict, List


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def score_bullet_against_keywords(text: str, keywords: List[str]) -> int:
    normalized = normalize(text)
    score = 0

    for kw in keywords:
        if kw.lower() in normalized:
            score += 1

    return score


def match_resume_to_jd(parsed_resume: Dict, jd_analysis: Dict) -> Dict:
    keywords = jd_analysis.get("keywords", [])

    bullet_matches = []
    missing_keywords = set(keywords)

    for exp in parsed_resume.get("experience", []):
        for bullet in exp.get("bullets", []):
            score = score_bullet_against_keywords(bullet["text"], keywords)

            matched_keywords = [
                kw for kw in keywords if kw.lower() in normalize(bullet["text"])
            ]

            for kw in matched_keywords:
                if kw in missing_keywords:
                    missing_keywords.remove(kw)

            bullet_matches.append({
                "bullet_id": bullet["id"],
                "section": "experience",
                "parent": exp["company"],
                "text": bullet["text"],
                "score": score,
                "matched_keywords": matched_keywords
            })

    for proj in parsed_resume.get("projects", []):
        for bullet in proj.get("bullets", []):
            score = score_bullet_against_keywords(bullet["text"], keywords)

            matched_keywords = [
                kw for kw in keywords if kw.lower() in normalize(bullet["text"])
            ]

            for kw in matched_keywords:
                if kw in missing_keywords:
                    missing_keywords.remove(kw)

            bullet_matches.append({
                "bullet_id": bullet["id"],
                "section": "project",
                "parent": proj["name"],
                "text": bullet["text"],
                "score": score,
                "matched_keywords": matched_keywords
            })

    bullet_matches = sorted(bullet_matches, key=lambda x: x["score"], reverse=True)

    return {
        "jd_keywords": keywords,
        "top_matching_bullets": bullet_matches[:10],
        "weak_bullets": [b for b in bullet_matches if b["score"] == 0],
        "missing_keywords": sorted(list(missing_keywords))
    }