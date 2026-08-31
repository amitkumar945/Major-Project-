"""
CSV export for complaint lists and analytics.

Reporting is the one thing the analytics screens could not do: the figures were
visible but could not leave the browser. This turns any filtered complaint list
into a spreadsheet an administrator can attach to a report.

Security note: nothing here builds its own database query. Every export goes
through `complaint_service.get_complaints()` with the caller's own user object,
so the scoping rule that stops a student widening their view applies to exports
exactly as it does to the list screens.

CSV is written with the `csv` module rather than by joining strings, so a
description containing a comma, quote or newline cannot break the file apart.
"""

import csv
import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Hard ceiling on one export. Large enough for a full year of complaints, small
# enough that a request cannot exhaust memory.
MAX_ROWS = 10000

# (column header, key path into the decorated complaint)
COMPLAINT_COLUMNS = [
    ("Reference ID", "id"),
    ("Title", "title"),
    ("Description", "description"),
    ("Category", "category"),
    ("Department", "department"),
    ("Priority", "priority"),
    ("Status", "status"),
    ("Submitted By", "submittedBy.name"),
    ("Submitted Email", "submittedBy.email"),
    ("Assigned Officer", "assignedOfficer.name"),
    ("Location", "location.address"),
    ("Submitted At", "submittedAt"),
    ("Deadline", "deadline"),
    ("Resolved At", "resolvedAt"),
    ("Escalation Level", "escalationLevel"),
    ("Rating", "feedback.rating"),
]


def _dig(row: dict, path: str):
    """Read a dotted path, tolerating missing intermediate objects."""
    value = row
    for part in path.split("."):
        if not isinstance(value, dict):
            return ""
        value = value.get(part)
        if value is None:
            return ""
    return value


def _cell(value) -> str:
    """Render one value as spreadsheet-safe text.

    Guards against CSV injection: a value starting with =, +, - or @ is treated
    as a formula by Excel and Google Sheets, so it is prefixed with a quote.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return "; ".join(str(item) for item in value)
    text = str(value)
    if text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


def _write_csv(headers: list, rows: list) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def filename(prefix: str) -> str:
    """A dated filename, safe for Content-Disposition."""
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"


def complaints_csv(filters: dict, user: dict) -> str:
    """Export the complaint list the caller is allowed to see.

    `filters` takes the same keys as the list endpoint, so the export always
    matches what is on screen.
    """
    from services import complaint_service

    options = dict(filters or {})
    options["page"] = 1
    options["pageSize"] = MAX_ROWS
    # A CSV of the whole filtered set is the point of this endpoint, so it
    # opts out of the API page-size cap. Row-level scoping still applies.
    options["allow_bulk"] = True

    result = complaint_service.get_complaints(options, user)
    items = result.get("items", [])

    if result.get("total", 0) > MAX_ROWS:
        logger.warning(
            "Complaint export truncated to %s of %s rows for user %s.",
            MAX_ROWS, result["total"], user.get("id"),
        )

    headers = [label for label, _ in COMPLAINT_COLUMNS]
    rows = [[_cell(_dig(item, path)) for _, path in COMPLAINT_COLUMNS] for item in items]

    logger.info("Complaint CSV export: %s row(s) for user %s.", len(rows), user.get("id"))
    return _write_csv(headers, rows)


# Metric keys are camelCase; these read better as spreadsheet headings.
_METRIC_LABELS = {
    "total": "Total complaints",
    "today": "Submitted today",
    "pending": "Pending",
    "inProgress": "In progress",
    "resolved": "Resolved",
    "escalated": "Escalated",
    "reopened": "Reopened",
    "avgResolutionDays": "Average resolution (days)",
    "satisfactionRate": "Satisfaction rate (%)",
    "avgRating": "Average rating (out of 5)",
    "resolutionRate": "Resolution rate (%)",
}


def analytics_csv(scope: dict = None) -> str:
    """Export the dashboard headline metrics as a two-column sheet."""
    from services import analytics_service

    metrics = analytics_service.summary(scope) or {}
    rows = [
        [_cell(_METRIC_LABELS.get(key, key)), _cell(value)]
        for key, value in metrics.items()
        if not isinstance(value, (dict, list))
    ]

    logger.info("Analytics CSV export: %s row(s).", len(rows))
    return _write_csv(["Metric", "Value"], rows)
