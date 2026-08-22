"""
NLP pre-processing for complaint text.

HONEST SCOPE: this is rule-based text processing, not a trained model. It does
cleaning, tokenisation, stopword removal, light stemming and regex-based entity
extraction. Nothing here has been trained on data, and no module in this package
claims otherwise.

The classifier and priority modules consume `process()` output, so replacing
this with a real pipeline (spaCy, a transformer tokenizer) later means changing
this file alone.
"""

import re

# Common English stopwords plus the filler words that dominate campus
# complaints and carry no routing signal.
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "doing", "done", "for", "from", "had",
    "has", "have", "having", "he", "her", "here", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "me", "my", "no", "nor", "not",
    "of", "on", "or", "our", "ours", "out", "over", "own", "same", "she",
    "should", "since", "so", "some", "such", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "will", "with", "would",
    "you", "your", "yours",
    # campus-complaint filler
    "please", "kindly", "sir", "madam", "respected", "request", "requesting",
    "complaint", "complain", "issue", "problem", "regarding", "also", "get",
    "getting", "got", "give", "given", "take", "taken", "make", "made", "due",
    "last", "days", "day", "time", "times", "many", "much", "still", "yet",
    "even", "one", "two", "three", "already", "soon", "please",
}

# Suffix rules, longest first. A crude Porter-style stemmer: enough to make
# "leaking"/"leakage"/"leaks" collide on "leak", which is what matters for
# keyword matching and duplicate detection.
_SUFFIXES = (
    ("ization", "ize"), ("iveness", "ive"), ("fulness", "ful"),
    ("ousness", "ous"), ("ational", "ate"), ("tional", "tion"),
    ("alism", "al"), ("aliti", "al"), ("iviti", "ive"),
    ("ement", ""), ("ments", ""), ("ement", ""), ("ance", ""), ("ence", ""),
    ("able", ""), ("ible", ""), ("ally", "al"), ("ness", ""), ("ings", ""),
    ("ment", ""), ("ages", "age"), ("age", ""), ("ing", ""), ("ies", "y"),
    ("ied", "y"), ("ies", "y"), ("ers", ""), ("est", ""), ("ely", ""),
    ("ed", ""), ("es", ""), ("er", ""), ("ly", ""), ("s", ""),
)

# Regex patterns for the entities a campus complaint usually contains.
ENTITY_PATTERNS = {
    "roomNumber": re.compile(r"\b(?:room|kaksh)\s*(?:no\.?|number|#)?\s*([a-z]?-?\d{1,4}[a-z]?)\b", re.I),
    "block": re.compile(r"\b(?:block|wing)\s*[-#]?\s*([a-z]-?\d{0,3})\b", re.I),
    "floor": re.compile(r"\b(ground|first|second|third|fourth|fifth|\d{1,2}(?:st|nd|rd|th))\s+floor\b", re.I),
    "building": re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:Bhavan|Bhawan|Hostel|Block|Building|Hall|Lab|Library|Canteen))\b"),
    "phone": re.compile(r"\b(?:\+?91[\-\s]?)?[6-9]\d{9}\b"),
    "date": re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"),
    "duration": re.compile(r"\b(\d{1,3})\s*(day|days|week|weeks|month|months|hour|hours)\b", re.I),
}

# Multi-word phrases that must survive tokenisation as a single signal.
PHRASES = (
    "short circuit", "no water", "no power", "not working", "air conditioner",
    "water supply", "power cut", "street light", "fire hazard", "server room",
    "wi-fi", "washing machine", "water cooler", "computer lab", "drinking water",
)


def clean_text(text: str) -> str:
    """Lowercase, strip URLs/emails/punctuation and collapse whitespace."""
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\S+@\S+\.\S+", " ", text)
    # Keep hyphens so "wi-fi" and "short-circuit" survive to phrase detection.
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str, min_length: int = 3) -> list:
    """Clean then split into tokens longer than `min_length - 1` characters."""
    return [t for t in clean_text(text).split() if len(t) >= min_length]


def remove_stopwords(tokens: list) -> list:
    return [t for t in tokens if t not in STOPWORDS]


def stem(word: str) -> str:
    """Strip the longest matching suffix, never shortening below 3 characters."""
    if len(word) <= 3:
        return word
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) + len(replacement) >= 3:
            return word[: -len(suffix)] + replacement
    return word


def stem_tokens(tokens: list) -> list:
    return [stem(t) for t in tokens]


def extract_phrases(text: str) -> list:
    """Multi-word signals present in the text, as they appear in PHRASES."""
    lowered = clean_text(text)
    return [phrase for phrase in PHRASES if phrase in lowered]


def extract_entities(text: str) -> dict:
    """Regex entity extraction: room numbers, buildings, floors, durations."""
    raw = str(text or "")
    found = {}
    for name, pattern in ENTITY_PATTERNS.items():
        matches = pattern.findall(raw)
        if not matches:
            continue
        values = []
        for match in matches:
            value = " ".join(m for m in match if m) if isinstance(match, tuple) else match
            value = str(value).strip()
            if value and value not in values:
                values.append(value)
        if values:
            found[name] = values
    return found


def process(text: str) -> dict:
    """Full pipeline. Everything downstream consumes this single result.

    Returns cleaned text, raw/filtered/stemmed tokens, the stem set used for
    similarity, detected phrases and extracted entities.
    """
    cleaned = clean_text(text)
    raw_tokens = tokenize(cleaned)
    content_tokens = remove_stopwords(raw_tokens)
    stems = stem_tokens(content_tokens)

    return {
        "original": text or "",
        "cleaned": cleaned,
        "tokens": raw_tokens,
        "contentTokens": content_tokens,
        "stems": stems,
        "stemSet": set(stems),
        "phrases": extract_phrases(cleaned),
        "entities": extract_entities(text or ""),
        "tokenCount": len(raw_tokens),
        "wordCount": len(cleaned.split()) if cleaned else 0,
    }


def keyword_frequency(text: str, top: int = 10) -> list:
    """Most frequent content stems, as [(stem, count)] - used for explanations."""
    stems = process(text)["stems"]
    counts = {}
    for stem_value in stems:
        counts[stem_value] = counts.get(stem_value, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:top]
