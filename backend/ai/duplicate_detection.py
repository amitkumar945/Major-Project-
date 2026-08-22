"""
Duplicate complaint detection.

HONEST SCOPE: lexical similarity (Jaccard over stemmed tokens), not semantic
matching. Two complaints describing the same fault in different words will not
be caught; that needs embeddings, which this module is structured to accept
later via `_similarity()`.

The service never rejects a complaint on its own - it reports the similarity
and lets the caller decide, which is what the brief asks for.
"""

from ai.nlp_processor import process

# Below this, two complaints are unrelated. Matches the frontend's 0.18 gate.
SIMILARITY_THRESHOLD = 0.18
# At or above this, they are near-certainly the same report.
DUPLICATE_THRESHOLD = 0.55
# Same-fault reports usually arrive close together.
DEFAULT_WINDOW_DAYS = 30


def _similarity(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two stem sets, 0..1."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    if not intersection:
        return 0.0
    return intersection / len(set_a | set_b)


def compare(text_a: str, text_b: str) -> float:
    """Similarity between two raw texts."""
    return _similarity(process(text_a)["stemSet"], process(text_b)["stemSet"])


def find_duplicates(
    title: str = "",
    description: str = "",
    department: str = "",
    candidates: list = None,
    limit: int = 3,
    threshold: float = SIMILARITY_THRESHOLD,
    exclude_id: str = None,
) -> list:
    """Rank existing complaints by similarity to the text being written.

    `candidates` are complaint documents supplied by the caller (the service
    layer queries Mongo, so this module stays storage-agnostic and testable).
    """
    processed = process(f"{title} {description}")
    if len(processed["contentTokens"]) < 3:
        return []  # too little text to judge

    target = processed["stemSet"]
    matches = []

    for complaint in candidates or []:
        if exclude_id and complaint.get("id") == exclude_id:
            continue
        if department and complaint.get("department") != department:
            continue

        other = process(f"{complaint.get('title', '')} {complaint.get('description', '')}")
        score = _similarity(target, other["stemSet"])
        if score < threshold:
            continue

        matches.append(
            {
                "id": complaint.get("id"),
                "title": complaint.get("title"),
                "department": complaint.get("department"),
                "status": complaint.get("status"),
                "submittedAt": complaint.get("submittedAt"),
                # The frontend renders this as a percentage.
                "similarity": round(score * 100),
                "isDuplicate": score >= DUPLICATE_THRESHOLD,
            }
        )

    matches.sort(key=lambda item: -item["similarity"])
    return matches[:limit]


def duplicate_report(title: str, description: str, department: str, candidates: list, exclude_id: str = None) -> dict:
    """Summary the brief asks for: is-duplicate, the match, and the score."""
    matches = find_duplicates(
        title=title,
        description=description,
        department=department,
        candidates=candidates,
        exclude_id=exclude_id,
    )
    best = matches[0] if matches else None

    return {
        "isDuplicate": bool(best and best["similarity"] >= DUPLICATE_THRESHOLD * 100),
        "similarComplaintId": best["id"] if best else None,
        "similarityScore": best["similarity"] if best else 0,
        # Probability 0..1, the field name the frontend AI card reads.
        "duplicateProbability": round(best["similarity"] / 100, 2) if best else 0.04,
        "matches": matches,
        "method": "jaccard-stem-overlap",
        "modelTrained": False,
    }
