"""
CSV export.

Covers the two things an export must never get wrong: it must contain exactly
the rows the caller is allowed to see, and it must survive hostile text without
breaking the file apart or handing Excel a formula to run.
"""

import csv
import io

import pytest


def _rows(response):
    """Parse an export response into a list of CSV rows, BOM stripped."""
    text = response.get_data(as_text=True).lstrip("\ufeff")
    return list(csv.reader(io.StringIO(text)))


def _submit(client, auth, token, complaint, title=None):
    payload = {**complaint}
    if title:
        payload["title"] = title
    response = client.post("/api/complaints", headers=auth(token), json=payload)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]["id"]


# --------------------------------------------------------------- transport


def test_export_returns_a_csv_attachment(client, auth, admin_token, student_token, water_complaint):
    _submit(client, auth, student_token, water_complaint)

    response = client.get("/api/complaints/export", headers=auth(admin_token))

    assert response.status_code == 200
    assert "text/csv" in response.headers["Content-Type"]
    assert "attachment;" in response.headers["Content-Disposition"]
    assert ".csv" in response.headers["Content-Disposition"]


def test_the_file_starts_with_a_bom_so_excel_reads_utf8(client, auth, admin_token):
    response = client.get("/api/complaints/export", headers=auth(admin_token))
    assert response.get_data(as_text=True).startswith("\ufeff")


def test_the_header_row_is_present(client, auth, admin_token):
    rows = _rows(client.get("/api/complaints/export", headers=auth(admin_token)))
    assert rows[0][0] == "Reference ID"
    assert "Status" in rows[0]


# ------------------------------------------------------------------ access


def test_export_requires_authentication(client):
    assert client.get("/api/complaints/export").status_code == 401


def test_the_token_may_arrive_in_the_query_string(client, admin_token):
    """A browser download cannot set an Authorization header."""
    response = client.get(f"/api/complaints/export?token={admin_token}")
    assert response.status_code == 200


def test_a_student_only_exports_their_own_complaints(
    client, auth, student_token, admin_token, water_complaint
):
    """The scoping that protects the list view must protect the export too."""
    _submit(client, auth, student_token, water_complaint, "Student's own leaking tap report")

    rows = _rows(client.get("/api/complaints/export", headers=auth(student_token)))
    admin_rows = _rows(client.get("/api/complaints/export", headers=auth(admin_token)))

    # The admin sees at least what the student sees...
    assert len(rows) - 1 >= 1
    assert len(admin_rows) >= len(rows)

    # ...and every row in the student's export was submitted by them.
    me = client.get("/api/auth/me", headers=auth(student_token)).get_json()["data"]["email"]
    assert {row[8] for row in rows[1:]} <= {me}


# ----------------------------------------------------------------- content


def test_filters_apply_to_the_export(client, auth, admin_token, student_token, water_complaint):
    _submit(client, auth, student_token, water_complaint)

    everything = _rows(client.get("/api/complaints/export", headers=auth(admin_token)))
    filtered = _rows(
        client.get("/api/complaints/export?status=Closed", headers=auth(admin_token))
    )

    assert len(everything) > len(filtered) or len(filtered) == 1


def test_pagination_does_not_truncate_the_export(
    client, auth, admin_token, student_token, water_complaint
):
    """A user on page 2 still exports the whole filtered set, not one page."""
    for index in range(4):
        _submit(client, auth, student_token, water_complaint, f"Water problem report number {index}")

    full = _rows(client.get("/api/complaints/export", headers=auth(admin_token)))
    paged = _rows(
        client.get("/api/complaints/export?page=2&pageSize=2", headers=auth(admin_token))
    )

    assert len(paged) == len(full)
    assert len(full) - 1 >= 4


# --------------------------------------------------------------- injection


def test_a_formula_is_neutralised_so_excel_will_not_run_it(
    client, auth, admin_token, student_token, water_complaint
):
    _submit(client, auth, student_token, water_complaint, "=cmd|'/c calc'!A1 spreadsheet attack")

    rows = _rows(client.get("/api/complaints/export", headers=auth(admin_token)))
    titles = [row[1] for row in rows[1:]]
    attack = [title for title in titles if "calc" in title]

    assert attack, "the test complaint should be in the export"
    assert attack[0].startswith("'="), "a leading = must be quoted"


def test_commas_quotes_and_newlines_do_not_break_the_row(
    client, auth, admin_token, student_token, water_complaint
):
    payload = {
        **water_complaint,
        "title": 'Leak, "major", in D-block',
        "description": water_complaint["description"] + "\nSecond line, with a comma.",
    }
    response = client.post("/api/complaints", headers=auth(student_token), json=payload)
    assert response.status_code == 201

    rows = _rows(client.get("/api/complaints/export", headers=auth(admin_token)))

    # Every row must have the same column count as the header - proof that the
    # embedded comma, quote and newline stayed inside their cells.
    assert len({len(row) for row in rows}) == 1
    assert any('"major"' in row[1] for row in rows[1:])


# --------------------------------------------------------------- analytics


def test_analytics_export_is_a_two_column_sheet(client, auth, admin_token):
    response = client.get("/api/analytics/export", headers=auth(admin_token))

    assert response.status_code == 200
    rows = _rows(response)
    assert rows[0] == ["Metric", "Value"]
    assert all(len(row) == 2 for row in rows)
    assert any(row[0] == "Total complaints" for row in rows)


def test_analytics_export_requires_authentication(client):
    assert client.get("/api/analytics/export").status_code == 401
