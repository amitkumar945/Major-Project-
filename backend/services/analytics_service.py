"""
Analytics.

Every function returns data in the shape the existing hand-drawn SVG charts
already consume - mostly `[{name, value}]` - so `charts.js` needed no changes.

Unlike the prototype, the historical series (monthly trend, weekly load,
resolution time, satisfaction) are now computed from real complaint documents
rather than fixed arrays.
"""

from constants import (
    ACTIVE_STATUSES,
    CLOSED_STATUSES,
    DEPARTMENT_NAMES,
    PRIORITY_LIST,
    STATUS_LIST,
)
from database import complaints, feedback as feedback_collection
from services import escalation_service
from utils.helpers import (
    count_by,
    days_between,
    days_until,
    parse_iso,
    to_chart_data,
    utcnow,
)

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _scoped(scope: dict = None) -> list:
    """Complaints in scope: a student's own, an officer's queue, or all."""
    scope = scope or {}
    query = {}
    if scope.get("userId"):
        query["submittedBy.id"] = scope["userId"]
    if scope.get("officerId"):
        query["assignedOfficer.id"] = scope["officerId"]
    if scope.get("department"):
        query["department"] = scope["department"]
    return list(complaints().find(query, {"_id": 0}))


# ------------------------------------------------------------ distributions


def status_distribution(items: list) -> list:
    """Only non-zero statuses, matching the frontend's `.filter(d => d.value > 0)`."""
    return [row for row in to_chart_data(count_by(items, "status"), STATUS_LIST) if row["value"] > 0]


def department_distribution(items: list) -> list:
    return to_chart_data(count_by(items, "department"), DEPARTMENT_NAMES)


def priority_distribution(items: list) -> list:
    return to_chart_data(count_by(items, "priority"), PRIORITY_LIST)


# --------------------------------------------------------- historical series


def monthly_trend(items: list, months: int = 12) -> list:
    """Registered vs resolved per month over the last `months` months."""
    now = utcnow()
    buckets = []
    for offset in range(months - 1, -1, -1):
        month = (now.month - offset - 1) % 12
        year = now.year + ((now.month - offset - 1) // 12)
        buckets.append({"key": (year, month + 1), "month": MONTH_NAMES[month], "registered": 0, "resolved": 0})

    index = {bucket["key"]: bucket for bucket in buckets}

    for complaint in items:
        submitted = parse_iso(complaint.get("submittedAt"))
        if submitted and (submitted.year, submitted.month) in index:
            index[(submitted.year, submitted.month)]["registered"] += 1

        resolved = parse_iso(complaint.get("resolvedAt"))
        if resolved and (resolved.year, resolved.month) in index:
            index[(resolved.year, resolved.month)]["resolved"] += 1

    return [{"month": b["month"], "registered": b["registered"], "resolved": b["resolved"]} for b in buckets]


def weekly_load(items: list) -> list:
    """Complaints registered per weekday."""
    counts = {day: 0 for day in WEEKDAYS}
    for complaint in items:
        submitted = parse_iso(complaint.get("submittedAt"))
        if submitted:
            counts[WEEKDAYS[submitted.weekday()]] += 1
    return [{"day": day, "complaints": counts[day]} for day in WEEKDAYS]


def resolution_time_by_department(items: list) -> list:
    """Average days to resolve, per department, against the SLA target."""
    # Target = the average SLA of the complaints that department actually received.
    from constants import PRIORITY_SLA_DAYS

    totals = {name: {"days": 0.0, "count": 0, "target": 0.0, "targetCount": 0} for name in DEPARTMENT_NAMES}

    for complaint in items:
        department = complaint.get("department")
        if department not in totals:
            continue

        bucket = totals[department]
        bucket["target"] += PRIORITY_SLA_DAYS.get(complaint.get("priority"), 7)
        bucket["targetCount"] += 1

        if complaint.get("resolvedAt") and complaint.get("submittedAt"):
            bucket["days"] += max(days_between(complaint["submittedAt"], complaint["resolvedAt"]), 0)
            bucket["count"] += 1

    return [
        {
            "name": name,
            "avgDays": round(bucket["days"] / bucket["count"], 1) if bucket["count"] else 0,
            "targetDays": round(bucket["target"] / bucket["targetCount"], 1) if bucket["targetCount"] else 7,
        }
        for name, bucket in totals.items()
    ]


def satisfaction_distribution() -> list:
    """Feedback count at each star rating."""
    counts = {rating: 0 for rating in range(1, 6)}
    for entry in feedback_collection().find({}, {"_id": 0, "rating": 1}):
        rating = int(entry.get("rating") or 0)
        if rating in counts:
            counts[rating] += 1
    return [{"rating": f"{star} Star", "count": counts[star]} for star in (5, 4, 3, 2, 1)]


def officer_performance() -> list:
    """Per-officer scorecard, computed from real assignments."""
    from database import users

    pipeline = [
        {"$match": {"assignedOfficer.id": {"$ne": None}}},
        {
            "$group": {
                "_id": "$assignedOfficer.id",
                "name": {"$first": "$assignedOfficer.name"},
                "department": {"$first": "$assignedOfficer.department"},
                "assigned": {"$sum": 1},
                "resolved": {"$sum": {"$cond": [{"$in": ["$status", CLOSED_STATUSES]}, 1, 0]}},
                "active": {"$sum": {"$cond": [{"$in": ["$status", ACTIVE_STATUSES]}, 1, 0]}},
            }
        },
        {"$sort": {"resolved": -1}},
    ]
    rows = list(complaints().aggregate(pipeline))

    # Average resolution days and rating need the complaint bodies.
    detail = {}
    for complaint in complaints().find(
        {"assignedOfficer.id": {"$ne": None}},
        {"_id": 0, "assignedOfficer.id": 1, "submittedAt": 1, "resolvedAt": 1, "feedback": 1},
    ):
        officer_id = complaint["assignedOfficer"]["id"]
        bucket = detail.setdefault(officer_id, {"days": 0, "count": 0, "ratings": []})
        if complaint.get("resolvedAt"):
            bucket["days"] += max(days_between(complaint["submittedAt"], complaint["resolvedAt"]), 0)
            bucket["count"] += 1
        if complaint.get("feedback"):
            bucket["ratings"].append(complaint["feedback"].get("rating", 0))

    # Officers with no complaints yet should still appear on the scorecard.
    seen = {row["_id"] for row in rows}
    for officer in users().find({"role": "officer", "isActive": True}, {"_id": 0, "id": 1, "name": 1, "department": 1}):
        if officer["id"] not in seen:
            rows.append({"_id": officer["id"], "name": officer["name"], "department": officer["department"],
                         "assigned": 0, "resolved": 0, "active": 0})

    result = []
    for row in rows:
        bucket = detail.get(row["_id"], {"days": 0, "count": 0, "ratings": []})
        ratings = bucket["ratings"]
        result.append(
            {
                "id": row["_id"],
                "name": row.get("name", ""),
                "department": row.get("department", ""),
                "assigned": row.get("assigned", 0),
                "resolved": row.get("resolved", 0),
                "active": row.get("active", 0),
                "avgDays": round(bucket["days"] / bucket["count"], 1) if bucket["count"] else 0,
                "rating": round(sum(ratings) / len(ratings), 1) if ratings else 0,
            }
        )
    result.sort(key=lambda item: -item["resolved"])
    return result


def department_performance(items: list) -> list:
    """Volume, resolution rate and satisfaction per department."""
    rows = []
    for name in DEPARTMENT_NAMES:
        own = [c for c in items if c.get("department") == name]
        resolved = [c for c in own if c.get("status") in CLOSED_STATUSES]
        ratings = [c["feedback"]["rating"] for c in own if c.get("feedback")]

        rows.append(
            {
                "name": name,
                "total": len(own),
                "resolved": len(resolved),
                "pending": len(own) - len(resolved),
                "resolutionRate": round(len(resolved) / len(own) * 100) if own else 0,
                "satisfaction": round(sum(ratings) / len(ratings), 1) if ratings else 0,
            }
        )
    return rows


# -------------------------------------------------------------- key metrics


def key_metrics(items: list) -> dict:
    """Headline numbers for the dashboard cards."""
    by_status = count_by(items, "status")
    resolved = by_status.get("Resolved", 0) + by_status.get("Closed", 0)
    total = len(items)

    today = utcnow().date()
    today_count = sum(
        1 for c in items
        if (parsed := parse_iso(c.get("submittedAt"))) and parsed.date() == today
    )

    ratings = [c["feedback"]["rating"] for c in items if c.get("feedback")]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    durations = [
        max(days_between(c["submittedAt"], c["resolvedAt"]), 0)
        for c in items
        if c.get("resolvedAt") and c.get("submittedAt")
    ]

    return {
        "total": total,
        "today": today_count,
        "pending": by_status.get("Pending", 0) + by_status.get("Submitted", 0) + by_status.get("Under Review", 0),
        "inProgress": by_status.get("In Progress", 0) + by_status.get("Accepted", 0) + by_status.get("Assigned", 0),
        "resolved": resolved,
        "escalated": by_status.get("Escalated", 0),
        "reopened": by_status.get("Reopened", 0),
        "avgResolutionDays": round(sum(durations) / len(durations), 1) if durations else 0,
        "satisfactionRate": round((avg_rating / 5) * 100),
        "avgRating": round(avg_rating, 1),
        "resolutionRate": round(resolved / total * 100) if total else 0,
    }


# ------------------------------------------------------------- entry points


def dashboard_charts(scope: dict = None) -> dict:
    """The three charts every dashboard shows."""
    items = _scoped(scope)
    return {
        "byStatus": status_distribution(items),
        "byDepartment": department_distribution(items),
        "byPriority": priority_distribution(items),
    }


def analytics_overview() -> dict:
    """Everything the admin analytics page renders, in one call."""
    items = _scoped()
    entries = list(feedback_collection().find({}, {"_id": 0}).sort("at", -1))
    ratings = [entry.get("rating", 0) for entry in entries]

    return {
        "metrics": key_metrics(items),
        "byStatus": status_distribution(items),
        "byDepartment": department_distribution(items),
        "byPriority": priority_distribution(items),
        "monthlyTrend": monthly_trend(items),
        "resolutionTime": resolution_time_by_department(items),
        "officerPerformance": officer_performance(),
        "departmentPerformance": department_performance(items),
        "satisfaction": satisfaction_distribution(),
        "weeklyLoad": weekly_load(items),
        "averageRating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
        "feedbackCount": len(entries),
    }


def feedback_entries(limit: int = 200) -> list:
    return list(feedback_collection().find({}, {"_id": 0}).sort("at", -1).limit(limit))


def sla_report() -> dict:
    return escalation_service.get_sla_report()
