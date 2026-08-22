"""
Shared pure helpers: timestamps, ids, deadlines, pagination.

The date format matters: the frontend parses every timestamp with
`new Date(value)` and renders it with `toLocaleDateString`, so all timestamps
leave the API as UTC ISO-8601 strings ending in `Z` - exactly the shape the
mock data used.
"""

import random
import re
import string
from datetime import datetime, timedelta, timezone

from constants import (
    ESCALATION_LEVELS,
    PRIORITY_SLA_DAYS,
    UNIVERSITY_SHORT,
)


# ---------------------------------------------------------------- datetime


def utcnow() -> datetime:
    """Timezone-aware current time. Always use this instead of datetime.now()."""
    return datetime.now(timezone.utc)


def iso(value: datetime = None) -> str:
    """Datetime -> '2026-02-14T09:30:00.000Z' (what the frontend expects)."""
    if value is None:
        value = utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def parse_iso(value) -> datetime:
    """Parse an ISO string (or pass a datetime through). Returns None on junk."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def add_days(value, days: int) -> str:
    base = parse_iso(value) or utcnow()
    return iso(base + timedelta(days=days))


def calculate_deadline(submitted_at, priority: str) -> str:
    """Deadline derived from the submission date and the priority SLA."""
    return add_days(submitted_at, PRIORITY_SLA_DAYS.get(priority, 7))


def days_between(start, end) -> int:
    """Whole days between two dates (end - start), comparing calendar days the
    same way the frontend's `daysBetween` does."""
    a, b = parse_iso(start), parse_iso(end)
    if a is None or b is None:
        return 0
    a = a.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    b = b.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return round((b - a).total_seconds() / 86400)


def days_until(deadline) -> int:
    """Days remaining until a deadline. Negative once it has passed."""
    return days_between(utcnow(), deadline)


def escalation_level_for_overdue(days_overdue: int) -> int:
    level = 1
    for rule in ESCALATION_LEVELS:
        if days_overdue >= rule["afterDays"]:
            level = rule["level"]
    return level


def escalation_authority(level: int) -> str:
    for rule in ESCALATION_LEVELS:
        if rule["level"] == level:
            return rule["authority"]
    return "Department Officer"


# --------------------------------------------------------------------- ids


def uid(prefix: str = "id", length: int = 7) -> str:
    """Short random id, matching the frontend's `uid()` shape (e.g. 'rm-a1b2c3')."""
    alphabet = string.ascii_lowercase + string.digits
    return f"{prefix}-{''.join(random.choices(alphabet, k=length))}"


def complaint_reference(sequence: int, year: int = None) -> str:
    """Build the complaint reference, e.g. DSVV-GRV-2026-00125.

    The frontend's `generateComplaintId()` produces this exact format and the
    tracking page matches on it, so the pattern must not change.
    """
    year = year or utcnow().year
    return f"{UNIVERSITY_SHORT}-GRV-{year}-{sequence:05d}"


REFERENCE_RE = re.compile(r"^[A-Z]{2,6}-GRV-\d{4}-\d{4,6}$")


def looks_like_reference(value: str) -> bool:
    return bool(REFERENCE_RE.match((value or "").strip().upper()))


# -------------------------------------------------------------- collections


def count_by(items, key: str) -> dict:
    counts = {}
    for item in items:
        value = item.get(key)
        if value is None:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def to_chart_data(counts: dict, order=None) -> list:
    """countBy result -> [{ name, value }], the shape every chart consumes."""
    keys = order if order is not None else list(counts.keys())
    return [{"name": name, "value": counts.get(name, 0)} for name in keys]


def paginate(items, page: int, page_size: int):
    start = (page - 1) * page_size
    return items[start : start + page_size]


def clean_document(doc):
    """Strip Mongo's `_id` so responses contain only frontend-facing fields."""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [clean_document(item) for item in doc]
    if isinstance(doc, dict):
        return {k: clean_document(v) for k, v in doc.items() if k != "_id"}
    return doc


def to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def pick(source: dict, keys) -> dict:
    """Whitelist copy - used so clients cannot patch arbitrary fields."""
    return {key: source[key] for key in keys if key in source}
