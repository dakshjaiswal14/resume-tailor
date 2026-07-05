import re
from typing import List, Dict, Any


STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "for", "of", "in", "on", "with",
    "using", "by", "through", "from", "into", "at", "as", "is", "are",
    "was", "were", "be", "been", "being", "that", "this", "it", "its"
}


def tokenize(text: str) -> List[str]:
    words = re.findall(r"\b[a-zA-Z0-9\+\#]+\b", text.lower())
    return [w for w in words if w not in STOPWORDS]


def keyword_alignment_score(added_keywords: List[str], missing_keywords: List[str]) -> float:
    if not missing_keywords:
        return 10.0

    matched = len(set(k.lower() for k in added_keywords) & set(k.lower() for k in missing_keywords))
    ratio = matched / max(len(set(missing_keywords)), 1)
    return round(min(ratio * 10, 10), 2)


def semantic_preservation_score(original: str, suggested: str) -> float:
    orig_tokens = set(tokenize(original))
    sugg_tokens = set(tokenize(suggested))

    if not orig_tokens:
        return 5.0

    overlap = len(orig_tokens & sugg_tokens) / len(orig_tokens)
    return round(min(overlap * 10, 10), 2)


def conciseness_score(original: str, suggested: str) -> float:
    orig_len = len(original.split())
    sugg_len = len(suggested.split())

    if orig_len == 0:
        return 5.0

    ratio = sugg_len / orig_len

    if ratio <= 1.25:
        return 10.0
    elif ratio <= 1.5:
        return 8.0
    elif ratio <= 1.8:
        return 6.0
    elif ratio <= 2.0:
        return 4.0
    else:
        return 2.0


def believability_score(original: str, suggested: str, added_keywords: List[str]) -> float:
    score = 10.0

    # Too many added keywords = likely stuffing
    if len(added_keywords) >= 4:
        score -= 2.0
    elif len(added_keywords) >= 3:
        score -= 1.0

    # Penalize if suggested is dramatically longer
    if len(suggested.split()) > len(original.split()) * 1.8:
        score -= 2.0

    # Penalize obvious stuffing phrases
    stuffing_patterns = [
        "robust api",
        "distributed systems architecture",
        "backend systems",
        "scalable architecture",
        "secure apis"
    ]

    lowered = suggested.lower()
    for pattern in stuffing_patterns:
        if pattern in lowered and pattern not in original.lower():
            score -= 1.0

    return max(round(score, 2), 1.0)


def generate_notes(final_score: float) -> str:
    if final_score >= 8.5:
        return "Strong rewrite with high keyword relevance and preserved technical meaning."
    elif final_score >= 7.0:
        return "Good rewrite with improved JD alignment and acceptable resume quality."
    elif final_score >= 5.5:
        return "Moderate rewrite; useful but may require manual refinement."
    return "Weak rewrite; likely too forced or insufficiently aligned."


def validate_suggestions(suggestions: List[Dict[str, Any]], missing_keywords: List[str]) -> List[Dict[str, Any]]:
    validated = []

    for s in suggestions:
        original = s.get("original_text", "")
        suggested = s.get("suggested_text", "")
        added_keywords = s.get("added_keywords", [])

        kas = keyword_alignment_score(added_keywords, missing_keywords)
        sps = semantic_preservation_score(original, suggested)
        cs = conciseness_score(original, suggested)
        bs = believability_score(original, suggested, added_keywords)

        final_score = round(
            (kas * 0.30) +
            (sps * 0.30) +
            (cs * 0.15) +
            (bs * 0.25),
            2
        )

        validated.append({
            **s,
            "keyword_alignment_score": kas,
            "semantic_preservation_score": sps,
            "conciseness_score": cs,
            "believability_score": bs,
            "final_score": final_score,
            "final_acceptance": final_score >= 7.0,
            "notes": generate_notes(final_score)
        })

    return validated