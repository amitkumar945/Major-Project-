"""
Priority / urgency prediction.

HONEST SCOPE: rule-based scoring, not a trained model. Ported from the
frontend's urgency keyword lists and extended with a reason string, because the
brief asks the service to explain *why* a priority was chosen.

Returns Low / Medium / High / Urgent - the four levels the frontend renders and
the SLA table keys off.
"""

from constants import (
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_URGENT,
    PRIORITY_SLA_DAYS,
)
from ai.nlp_processor import clean_text, process

# Safety-critical language: anything here forces Urgent on its own.
URGENT_KEYWORDS = {
    "fire", "spark", "sparking", "short circuit", "shortcircuit", "burnt",
    "burning", "smoke", "injury", "injured", "danger", "dangerous", "collapse",
    "collapsed", "falling", "shock", "electrocution", "emergency", "unsafe",
    "hazard", "server room", "gas leak", "flood", "flooding", "live wire",
    "exposed wire", "accident", "bleeding", "trapped",
}

# Service is broken and blocking people.
HIGH_KEYWORDS = {
    "leak", "leakage", "broken", "not working", "blocked", "overflow",
    "no water", "no power", "power cut", "dark", "stopped", "damaged",
    "seepage", "exam", "urgent", "immediately", "several days", "entire",
    "whole hostel", "all rooms", "cannot", "unable", "failed", "burst",
    "crack", "outage", "dead",
}

# Cosmetic or convenience requests.
LOW_KEYWORDS = {
    "slow", "minor", "sometimes", "occasionally", "suggestion", "cosmetic",
    "paint", "repaint", "polish", "improve", "would be nice", "request for",
    "whenever possible", "small", "slightly",
}

# Words implying many people are affected - a nudge upward, not a decision.
SCALE_KEYWORDS = {
    "everyone", "all students", "entire", "whole", "many students",
    "all rooms", "hostel", "department", "block", "floor", "class",
}

# Numeric priority so the levels can be compared and nudged.
_ORDER = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_URGENT]


def _matches(text: str, keywords: set) -> list:
    return sorted(word for word in keywords if word in text)


def predict(title: str = "", description: str = "", processed: dict = None) -> dict:
    """Predict priority with a human-readable reason.

    Rules run strongest-first: safety language wins outright, then breakage,
    then cosmetic wording; anything else is Medium. A scale signal can lift a
    Low/Medium complaint by one level, but never reaches Urgent on its own.
    """
    text = clean_text(f"{title} {description}")
    processed = processed or process(f"{title} {description}")

    urgent_hits = _matches(text, URGENT_KEYWORDS)
    high_hits = _matches(text, HIGH_KEYWORDS)
    low_hits = _matches(text, LOW_KEYWORDS)
    scale_hits = _matches(text, SCALE_KEYWORDS)

    if urgent_hits:
        priority = PRIORITY_URGENT
        reason = f"Safety-critical wording detected ({', '.join(urgent_hits[:3])})."
        confidence = 0.90
        triggers = urgent_hits
    elif high_hits:
        priority = PRIORITY_HIGH
        reason = f"Service failure reported ({', '.join(high_hits[:3])})."
        confidence = 0.78
        triggers = high_hits
    elif low_hits:
        priority = PRIORITY_LOW
        reason = f"Reads as a minor or cosmetic request ({', '.join(low_hits[:3])})."
        confidence = 0.70
        triggers = low_hits
    else:
        priority = PRIORITY_MEDIUM
        reason = "No urgency indicators found; assigned the default priority."
        confidence = 0.60
        triggers = []

    # Widespread impact lifts a mild complaint one level.
    if scale_hits and priority in (PRIORITY_LOW, PRIORITY_MEDIUM):
        lifted = _ORDER[min(_ORDER.index(priority) + 1, len(_ORDER) - 1)]
        if lifted != priority:
            reason += f" Raised to {lifted}: affects multiple people ({scale_hits[0]})."
            priority = lifted
            confidence = round(min(confidence + 0.05, 0.85), 2)

    return {
        "priority": priority,
        "reason": reason,
        "confidence": confidence,
        "triggers": triggers[:5],
        "slaDays": PRIORITY_SLA_DAYS.get(priority, 7),
        "method": "keyword-rules",
        "modelTrained": False,
    }
