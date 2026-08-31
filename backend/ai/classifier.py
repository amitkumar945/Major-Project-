"""
Department classification.

HONEST SCOPE: a weighted keyword classifier, not a trained model. It is a
direct port of the frontend's keyword dictionary, upgraded to work on stemmed
tokens and to weight strong signals ("pipeline", "wiring") above weak ones
("system", "lab") that appear across several departments.

`classify()` returns the exact field names `analyseComplaint()` used to return,
so the AI card on the complaint form renders unchanged.

Replacing this with a trained model: implement `predict(text) -> (department,
confidence, alternatives)` and call it from `classify()`. Nothing else changes.
"""

from constants import CATEGORY_DEPARTMENT_MAP, DEPARTMENT_NAMES
from ai.nlp_processor import process, stem

# Keyword -> weight. Weight 3 = near-unambiguous, 2 = strong, 1 = weak/shared.
# The terms come from the frontend dictionary in complaintService.js plus the
# examples in the project brief.
DEPARTMENT_KEYWORDS = {
    "Jal Kal Vibhag": {
        "water": 3, "leak": 3, "leakage": 3, "pipe": 3, "pipeline": 3,
        "plumb": 3, "plumbing": 3, "drain": 3, "drainage": 3, "sewage": 3,
        "sewer": 3, "tap": 3, "faucet": 3, "manhole": 3, "sanitation": 3,
        "toilet": 2, "washroom": 2, "bathroom": 2, "flush": 2, "overflow": 2,
        "purifier": 2, "ro": 2, "tank": 2, "supply": 1, "cooler": 2,
        "seepage": 1, "clog": 2, "blockage": 2, "urinal": 2, "basin": 2,
    },
    "Vidyut Vibhag": {
        "electric": 3, "electricity": 3, "electrical": 3, "wiring": 3,
        "wire": 3, "voltage": 3, "mcb": 3, "fuse": 3, "transformer": 3,
        "generator": 3, "socket": 3, "switchboard": 3, "shortcircuit": 3,
        "short circuit": 3, "spark": 3, "power": 2, "light": 2, "bulb": 2,
        "tube": 2, "fan": 2, "switch": 2, "geyser": 2, "regulator": 2,
        "inverter": 2, "current": 2, "streetlight": 3, "ac": 1,
        "air conditioner": 2, "supply": 1, "meter": 1, "shock": 2,
    },
    "MCA Lab / Computer Lab": {
        "computer": 3, "pc": 3, "laptop": 3, "printer": 3, "projector": 3,
        "internet": 3, "wifi": 3, "wi-fi": 3, "lan": 3, "router": 3,
        "network": 3, "software": 3, "keyboard": 3, "mouse": 3, "monitor": 3,
        "server": 3, "cpu": 3, "ram": 3, "scanner": 3, "licence": 2,
        "license": 2, "install": 2, "windows": 2, "linux": 2, "terminal": 2,
        "lab": 1, "system": 1, "screen": 2, "cable": 1, "port": 2,
    },
    "Nirman Vibhag": {
        "building": 3, "wall": 3, "plaster": 3, "ceiling": 3, "roof": 3,
        "crack": 3, "construction": 3, "carpentry": 3, "furniture": 3,
        "bench": 3, "desk": 3, "chair": 3, "table": 2, "paint": 3,
        "painting": 3, "road": 3, "pothole": 3, "floor": 2, "tile": 3,
        "window": 2, "door": 2, "lock": 2, "hinge": 2, "civil": 3,
        "repair": 1, "renovation": 3, "masonry": 3, "cement": 3,
        "staircase": 2, "railing": 2, "seepage": 2, "damp": 2,
    },
}

# Pre-stem the dictionary once so lookups match stemmed complaint tokens.
_STEMMED_KEYWORDS = {
    department: {stem(word): weight for word, weight in words.items() if " " not in word}
    for department, words in DEPARTMENT_KEYWORDS.items()
}
_PHRASE_KEYWORDS = {
    department: {word: weight for word, weight in words.items() if " " in word}
    for department, words in DEPARTMENT_KEYWORDS.items()
}


def score_departments(text: str, processed: dict = None) -> list:
    """Weighted score per department, highest first.

    Each entry: {department, score, matched} where `matched` lists the terms
    that fired - which is what makes the prediction explainable in the UI.
    """
    processed = processed or process(text)
    stem_set = processed["stemSet"]
    cleaned = processed["cleaned"]

    results = []
    for department in DEPARTMENT_NAMES:
        stemmed = _STEMMED_KEYWORDS.get(department, {})
        phrases = _PHRASE_KEYWORDS.get(department, {})

        score, matched = 0, []
        for keyword_stem, weight in stemmed.items():
            if keyword_stem in stem_set:
                score += weight
                matched.append(keyword_stem)
        for phrase, weight in phrases.items():
            if phrase in cleaned:
                score += weight
                matched.append(phrase)

        results.append({"department": department, "score": score, "matched": matched})

    results.sort(key=lambda item: (-item["score"], item["department"]))
    return results


def _confidence(best: dict, runner_up: dict, token_count: int) -> float:
    """Confidence from the winning score and its margin over second place.

    A clear winner with several strong keywords approaches 0.95; a tie or a
    keyword-free text stays near the 0.35 floor. Deliberately never returns
    1.0 - a keyword rule should not claim certainty.
    """
    best_score = best["score"]
    if best_score == 0:
        return 0.35  # nothing matched; the category fallback decides

    margin = best_score - (runner_up["score"] if runner_up else 0)
    raw = 0.55 + min(best_score, 12) * 0.022 + min(margin, 10) * 0.030

    # Very short texts give the classifier little to work with.
    if token_count < 8:
        raw -= 0.08
    return round(max(0.35, min(raw, 0.95)), 2)


def _alternatives(scores: list, department: str, limit: int = 3) -> list:
    """The ranked list shown as "Department match strength".

    Always includes the predicted department, even when it did not win on
    keywords (a category fallback), so the card can never show a set of
    departments that excludes the one the complaint was actually routed to.
    """
    ranked = [{"department": item["department"], "score": item["score"]} for item in scores]
    top = ranked[:limit]

    if not any(entry["department"] == department for entry in top):
        predicted = next((e for e in ranked if e["department"] == department), None)
        if predicted:
            # Put it first: it is the routing decision, whatever it scored.
            top = [predicted] + top[: limit - 1]

    return top


def classify(title: str = "", description: str = "", category: str = "", processed: dict = None) -> dict:
    """Predict the department for a complaint.

    Returns predicted department, confidence, ranked alternatives and the
    keywords that drove the decision.
    """
    text = f"{title} {description}".strip()
    processed = processed or process(text)

    scores = score_departments(text, processed)
    best = scores[0]
    runner_up = scores[1] if len(scores) > 1 else None

    if best["score"] > 0:
        department = best["department"]
        source = "keyword"
    else:
        # No keyword matched - fall back to the category the user picked.
        department = CATEGORY_DEPARTMENT_MAP.get(category, "Nirman Vibhag")
        source = "category-fallback"

    confidence = _confidence(best, runner_up, processed["tokenCount"])

    # Keywords the user would recognise, not stems.
    original_terms = []
    for term in best["matched"]:
        for word in DEPARTMENT_KEYWORDS.get(best["department"], {}):
            if stem(word) == term or word == term:
                if word not in original_terms:
                    original_terms.append(word)
                break

    return {
        "department": department,
        "confidence": confidence,
        "source": source,
        "keywords": original_terms[:6],
        # The predicted department must always appear here: on a category
        # fallback every score is 0, so a plain top-3 slice sorted
        # alphabetically could drop the winner and leave the card showing only
        # departments the complaint was not routed to.
        "alternatives": _alternatives(scores, department),
        "scores": scores,
        "method": "weighted-keyword-rules",
        "modelTrained": False,
    }
