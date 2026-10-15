"""Complaint creation, tracking, status flow, remarks, resolution, feedback."""

import io


def test_create_complaint_returns_a_reference_id(client, make_complaint):
    complaint = make_complaint()
    assert complaint["id"].startswith("DSVV-GRV-")
    assert complaint["status"] in ("Submitted", "Assigned")


def test_create_complaint_auto_routes_and_assigns(client, make_complaint):
    complaint = make_complaint()
    assert complaint["department"] == "Jal Kal Vibhag"
    assert complaint["assignedOfficer"] is not None
    assert complaint["assignedOfficer"]["department"] == "Jal Kal Vibhag"
    assert complaint["status"] == "Assigned"


def test_create_complaint_sets_the_sla_deadline(client, make_complaint):
    complaint = make_complaint()
    assert complaint["deadline"]
    assert complaint["priority"] in ("Low", "Medium", "High", "Urgent")


def test_create_complaint_builds_the_timeline(client, make_complaint):
    complaint = make_complaint()
    assert len(complaint["timeline"]) == 7
    assert complaint["timeline"][0]["label"] == "Complaint Submitted"


def test_reference_ids_are_sequential_and_unique(client, make_complaint):
    ids = {make_complaint()["id"] for _ in range(3)}
    assert len(ids) == 3


def test_create_complaint_requires_authentication(client, water_complaint):
    assert client.post("/api/complaints", json=water_complaint).status_code == 401


def test_create_complaint_validates_input(client, auth, student_token):
    response = client.post(
        "/api/complaints",
        json={"title": "sh", "description": "too short", "category": "Water"},
        headers=auth(student_token),
    )
    assert response.status_code == 422
    assert "title" in response.get_json()["error"]["fields"]


def test_client_cannot_dictate_its_own_priority(client, auth, student_token, water_complaint):
    """The server classifies; a client must not be able to pick a longer SLA."""
    response = client.post(
        "/api/complaints", json={**water_complaint, "priority": "Low"}, headers=auth(student_token)
    )
    assert response.get_json()["data"]["priority"] != "Low"


def test_computer_lab_complaints_require_lab_and_system(client, auth, student_token, water_complaint):
    base_payload = {
        **water_complaint,
        "title": "Computer system will not start",
        "description": "The affected computer will not start during the practical session.",
        "category": "Computer/Lab",
        "department": "MCA Lab / Computer Lab",
        "lab": "BCA Lab",
        "systemNumber": "System 15",
    }

    for missing_fields in (("lab",), ("systemNumber",), ("lab", "systemNumber")):
        payload = {**base_payload}
        for field in missing_fields:
            payload.pop(field)
        response = client.post("/api/complaints", json=payload, headers=auth(student_token))
        assert response.status_code == 422
        assert set(response.get_json()["error"]["fields"]) == set(missing_fields)


def test_computer_lab_and_system_number_persist_and_track(client, auth, student_token, water_complaint):
    for lab in ("BCA Lab", "BIT Lab", "MCA Lab"):
        payload = {
            **water_complaint,
            "title": f"Computer system issue in {lab}",
            "description": "The affected computer is not working during the practical session.",
            "category": "Computer/Lab",
            "department": "MCA Lab / Computer Lab",
            "lab": lab,
            "systemNumber": "System 15",
        }
        response = client.post("/api/complaints", json=payload, headers=auth(student_token))
        assert response.status_code == 201
        complaint = response.get_json()["data"]
        assert complaint["lab"] == lab
        assert complaint["systemNumber"] == "System 15"

        details = client.get(f"/api/complaints/{complaint['id']}", headers=auth(student_token))
        assert details.get_json()["data"]["lab"] == lab
        assert details.get_json()["data"]["systemNumber"] == "System 15"

        tracked = client.get(f"/api/complaints/track/{complaint['id']}").get_json()["data"]
        assert tracked["lab"] == lab
        assert tracked["systemNumber"] == "System 15"

        filtered = client.get(
            f"/api/complaints?lab={lab.replace(' ', '%20')}&systemNumber=System%2015",
            headers=auth(student_token),
        ).get_json()["data"]["items"]
        assert any(item["id"] == complaint["id"] for item in filtered)


def test_computer_lab_fields_persist_when_classifier_routes_to_another_department(
    client, auth, student_token, water_complaint
):
    payload = {
        **water_complaint,
        "title": "Computer/Lab water leak near the server rack",
        "description": "Water is leaking from the pipeline beside the computer lab server rack.",
        "category": "Computer/Lab",
        "department": "MCA Lab / Computer Lab",
        "lab": "BCA Lab",
        "systemNumber": "System 12",
    }
    response = client.post("/api/complaints", json=payload, headers=auth(student_token))

    assert response.status_code == 201, response.get_json()
    complaint = response.get_json()["data"]
    assert complaint["department"] == "Jal Kal Vibhag"
    assert complaint["lab"] == "BCA Lab"
    assert complaint["systemNumber"] == "System 12"

    tracked = client.get(f"/api/complaints/track/{complaint['id']}").get_json()["data"]
    assert tracked["lab"] == "BCA Lab"
    assert tracked["systemNumber"] == "System 12"


def test_other_categories_do_not_store_computer_lab_fields(
    client, auth, student_token, water_complaint
):
    for category in ("Water", "Electricity", "Building", "Hostel", "Classroom", "Other"):
        payload = {
            **water_complaint,
            "title": f"General campus issue for {category}",
            "description": "A general campus facility issue needs inspection and repair.",
            "category": category,
            "lab": "BCA Lab",
            "systemNumber": "System 12",
        }
        response = client.post("/api/complaints", json=payload, headers=auth(student_token))
        assert response.status_code == 201, response.get_json()
        complaint = response.get_json()["data"]
        assert complaint["category"] == category
        assert "lab" not in complaint
        assert "systemNumber" not in complaint


# ------------------------------------------------------------------ reading


def test_student_sees_only_their_own_complaints(client, auth, student_token, make_complaint):
    make_complaint()
    response = client.get("/api/complaints", headers=auth(student_token))
    items = response.get_json()["data"]["items"]

    assert items
    assert all(item["submittedBy"]["email"] == "student@dsvv.ac.in" for item in items)


def test_student_cannot_read_another_students_complaint(client, auth, make_complaint):
    complaint = make_complaint()

    other = client.post(
        "/api/auth/login",
        json={"identifier": "sneha.bhardwaj@dsvv.ac.in", "password": "student123"},
    ).get_json()["data"]["token"]

    response = client.get(f"/api/complaints/{complaint['id']}", headers=auth(other))
    assert response.status_code == 403


def test_filters_and_pagination(client, auth, student_token, make_complaint):
    make_complaint()
    make_complaint()

    response = client.get(
        "/api/complaints?department=Jal Kal Vibhag&page=1&pageSize=1", headers=auth(student_token)
    )
    data = response.get_json()["data"]

    assert len(data["items"]) == 1
    assert data["total"] >= 2
    assert data["totalPages"] >= 2


def test_dashboard_status_group_filters_match_summary_counts(
    client, auth, student_token, admin_token, make_complaint
):
    """Dashboard status groups open a list containing every counted status."""
    groups = {
        "pending": ["Submitted", "Under Review", "Pending"],
        "in-progress": ["Accepted", "In Progress"],
        "resolved": ["Resolved", "Closed"],
    }

    for statuses in groups.values():
        for status in statuses:
            complaint = make_complaint()
            changed = client.put(
                f"/api/complaints/{complaint['id']}/status",
                json={"status": status},
                headers=auth(admin_token),
            )
            assert changed.status_code == 200, changed.get_json()

    summary = client.get("/api/complaints/statistics", headers=auth(student_token)).get_json()["data"]
    counters = {"pending": "pending", "in-progress": "inProgress", "resolved": "resolved"}

    for group, statuses in groups.items():
        response = client.get(
            f"/api/complaints?statusGroup={group}", headers=auth(student_token)
        )
        data = response.get_json()["data"]
        assert response.status_code == 200
        assert data["total"] == summary[counters[group]] == len(statuses)
        assert {item["status"] for item in data["items"]} == set(statuses)

    # The existing dropdown filter remains an exact single-status match.
    exact = client.get("/api/complaints?status=Pending", headers=auth(student_token))
    assert exact.get_json()["data"]["total"] == 1


def test_dashboard_feedback_urgent_and_reopened_counts_follow_records(
    client, auth, student_token, officer_token, admin_token, make_complaint
):
    rated = make_complaint()
    pending_feedback = make_complaint()
    reopened = make_complaint()
    urgent = make_complaint()

    changed_priority = client.put(
        f"/api/complaints/{urgent['id']}/priority",
        json={"priority": "Urgent"},
        headers=auth(admin_token),
    )
    assert changed_priority.status_code == 200

    for complaint in (rated, pending_feedback, reopened):
        assert _resolve(client, auth, officer_token, complaint["id"]).status_code == 200

    submitted_feedback = client.post(
        f"/api/complaints/{rated['id']}/feedback",
        json={"rating": 5, "comment": "Resolved correctly."},
        headers=auth(student_token),
    )
    assert submitted_feedback.status_code == 201

    reopened_response = client.post(
        f"/api/complaints/{reopened['id']}/reopen",
        json={"reason": "The problem came back."},
        headers=auth(student_token),
    )
    assert reopened_response.status_code == 200

    summary = client.get("/api/complaints/statistics", headers=auth(student_token)).get_json()["data"]
    feedback = client.get("/api/feedback/my", headers=auth(student_token)).get_json()["data"]
    all_complaints = client.get("/api/complaints", headers=auth(student_token)).get_json()["data"]
    urgent_list = client.get("/api/complaints?priority=Urgent", headers=auth(student_token)).get_json()["data"]
    reopened_list = client.get("/api/complaints?status=Reopened", headers=auth(student_token)).get_json()["data"]
    resolved_list = client.get("/api/complaints?statusGroup=resolved", headers=auth(student_token)).get_json()["data"]

    assert summary["total"] == all_complaints["total"] == 4
    assert summary["resolved"] == resolved_list["total"] == 2
    assert summary["reopened"] == reopened_list["total"] == 1
    assert len([item for item in all_complaints["items"] if item["priority"] == "Urgent"]) == urgent_list["total"] == 1
    assert feedback["pendingCount"] == 1
    assert feedback["givenCount"] == 1


def test_search_matches_the_title(client, auth, student_token, make_complaint):
    make_complaint()
    response = client.get("/api/complaints?search=Gayatri", headers=auth(student_token))
    assert response.get_json()["data"]["total"] >= 1


# ----------------------------------------------------------------- tracking


def test_public_tracking_needs_no_token(client, make_complaint):
    complaint = make_complaint()
    response = client.get(f"/api/complaints/track/{complaint['id']}")

    assert response.status_code == 200
    assert response.get_json()["data"]["id"] == complaint["id"]


def test_public_tracking_hides_personal_details(client, make_complaint):
    complaint = make_complaint()
    data = client.get(f"/api/complaints/track/{complaint['id']}").get_json()["data"]

    assert "email" not in data["submittedBy"]
    assert "hostel" not in data["submittedBy"]
    assert "remarks" not in data


def test_tracking_an_unknown_reference_returns_404(client):
    assert client.get("/api/complaints/track/DSVV-GRV-2026-99999").status_code == 404


def test_tracking_is_case_insensitive(client, make_complaint):
    complaint = make_complaint()
    assert client.get(f"/api/complaints/track/{complaint['id'].lower()}").status_code == 200


def test_public_tracking_exposes_the_location_for_the_map(client, make_complaint):
    complaint = make_complaint()
    data = client.get(f"/api/complaints/track/{complaint['id']}").get_json()["data"]

    assert data["location"]["latitude"] == 29.99965
    assert data["location"]["longitude"] == 78.1946
    assert data["location"]["address"] == "Gayatri Bhavan main entrance"


def test_public_tracking_withholds_the_gps_accuracy(client, make_complaint):
    """Accuracy describes the reporter's device, not the complaint."""
    complaint = make_complaint({"location": {
        "latitude": 29.99965,
        "longitude": 78.1946,
        "address": "Gayatri Bhavan main entrance",
        "accuracy": 12,
    }})
    data = client.get(f"/api/complaints/track/{complaint['id']}").get_json()["data"]

    assert "accuracy" not in data["location"]


# ------------------------------------------------------------- geo-tagging


def test_location_is_stored_for_the_map(client, make_complaint):
    complaint = make_complaint({"location": {
        "latitude": 29.99995,
        "longitude": 78.1942,
        "address": "Academic Block C, Second Floor",
        "block": "Academic Zone",
        "accuracy": 8,
    }})

    assert complaint["location"]["latitude"] == 29.99995
    assert complaint["location"]["longitude"] == 78.1942
    assert complaint["location"]["accuracy"] == 8
    assert complaint["location"]["block"] == "Academic Zone"


def test_string_coordinates_are_stored_as_numbers(client, auth, student_token, water_complaint):
    """Multipart form submissions deliver every field as a string."""
    payload = {**water_complaint, "location": {
        "latitude": "29.99965",
        "longitude": "78.1946",
        "address": "Gayatri Bhavan main entrance",
        "accuracy": "15",
    }}
    response = client.post("/api/complaints", json=payload, headers=auth(student_token))

    location = response.get_json()["data"]["location"]
    assert isinstance(location["latitude"], float)
    assert isinstance(location["longitude"], float)
    assert location["latitude"] == 29.99965
    assert location["accuracy"] == 15.0


def test_out_of_range_coordinates_are_rejected(client, auth, student_token, water_complaint):
    payload = {**water_complaint, "location": {
        "latitude": 200,
        "longitude": 78.1946,
        "address": "Somewhere impossible",
    }}
    response = client.post("/api/complaints", json=payload, headers=auth(student_token))

    assert response.status_code == 422
    assert "location" in response.get_json()["error"]["fields"]


def test_coordinates_without_a_landmark_are_rejected(client, auth, student_token, water_complaint):
    payload = {**water_complaint, "location": {
        "latitude": 29.99965,
        "longitude": 78.1946,
        "address": "   ",
    }}
    response = client.post("/api/complaints", json=payload, headers=auth(student_token))

    assert response.status_code == 422
    assert "address" in response.get_json()["error"]["fields"]


# ------------------------------------------------------------ status flow


def test_officer_updates_status(client, auth, officer_token, make_complaint):
    complaint = make_complaint()
    response = client.put(
        f"/api/complaints/{complaint['id']}/status",
        json={"status": "In Progress", "note": "Plumber dispatched."},
        headers=auth(officer_token),
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "In Progress"


def test_status_change_appends_to_the_timeline(client, auth, officer_token, make_complaint):
    complaint = make_complaint()
    before = len(complaint["timeline"])

    response = client.put(
        f"/api/complaints/{complaint['id']}/status",
        json={"status": "In Progress"},
        headers=auth(officer_token),
    )
    assert len(response.get_json()["data"]["timeline"]) == before + 1


def test_officer_cannot_set_an_admin_only_status(client, auth, officer_token, make_complaint):
    complaint = make_complaint()
    response = client.put(
        f"/api/complaints/{complaint['id']}/status",
        json={"status": "Closed"},
        headers=auth(officer_token),
    )
    assert response.status_code == 403


def test_student_cannot_change_status(client, auth, student_token, make_complaint):
    complaint = make_complaint()
    response = client.put(
        f"/api/complaints/{complaint['id']}/status",
        json={"status": "Resolved"},
        headers=auth(student_token),
    )
    assert response.status_code == 403


def test_unknown_status_is_rejected(client, auth, officer_token, make_complaint):
    complaint = make_complaint()
    response = client.put(
        f"/api/complaints/{complaint['id']}/status",
        json={"status": "Teleported"},
        headers=auth(officer_token),
    )
    assert response.status_code == 422


def test_every_frontend_status_is_accepted(client, auth, admin_token, make_complaint):
    """The frontend renders ten statuses; the API must accept all of them."""
    from constants import STATUS_LIST

    for status in STATUS_LIST:
        complaint = make_complaint()
        response = client.put(
            f"/api/complaints/{complaint['id']}/status",
            json={"status": status},
            headers=auth(admin_token),
        )
        assert response.status_code == 200, f"{status} rejected"
        assert response.get_json()["data"]["status"] == status


# ------------------------------------------------------- remarks & resolution


def test_officer_adds_a_remark(client, auth, officer_token, make_complaint):
    complaint = make_complaint()
    response = client.post(
        f"/api/complaints/{complaint['id']}/remarks",
        json={"message": "Leak located at the underground joint."},
        headers=auth(officer_token),
    )

    assert response.status_code == 201
    remarks = response.get_json()["data"]["remarks"]
    assert len(remarks) == 1
    assert remarks[0]["role"] == "officer"
    assert remarks[0]["at"]


def test_empty_remark_is_rejected(client, auth, officer_token, make_complaint):
    complaint = make_complaint()
    response = client.post(
        f"/api/complaints/{complaint['id']}/remarks", json={"message": "   "},
        headers=auth(officer_token),
    )
    assert response.status_code == 422


def test_officer_resolves_a_complaint(client, auth, officer_token, make_complaint):
    complaint = make_complaint()
    response = client.post(
        f"/api/complaints/{complaint['id']}/resolve",
        json={"notes": "Replaced the damaged pipeline joint and sealed the walkway."},
        headers=auth(officer_token),
    )

    data = response.get_json()["data"]
    assert response.status_code == 200
    assert data["status"] == "Resolved"
    assert data["resolvedAt"]
    assert data["resolution"]["notes"]


def test_resolving_twice_is_rejected(client, auth, officer_token, make_complaint):
    complaint = make_complaint()
    body = {"notes": "Fixed the leaking pipeline joint properly."}

    client.post(f"/api/complaints/{complaint['id']}/resolve", json=body, headers=auth(officer_token))
    second = client.post(
        f"/api/complaints/{complaint['id']}/resolve", json=body, headers=auth(officer_token)
    )
    assert second.status_code == 409


# ------------------------------------------------------- feedback & reopen


def _resolve(client, auth, officer_token, complaint_id):
    return client.post(
        f"/api/complaints/{complaint_id}/resolve",
        json={"notes": "Replaced the damaged pipeline joint."},
        headers=auth(officer_token),
    )


def test_feedback_after_resolution(client, auth, student_token, officer_token, make_complaint):
    complaint = make_complaint()
    _resolve(client, auth, officer_token, complaint["id"])

    response = client.post(
        f"/api/complaints/{complaint['id']}/feedback",
        json={"rating": 5, "comment": "Fixed quickly, thank you very much.", "satisfied": True},
        headers=auth(student_token),
    )

    assert response.status_code == 201
    assert response.get_json()["data"]["feedback"]["rating"] == 5


def test_feedback_before_resolution_is_rejected(client, auth, student_token, make_complaint):
    complaint = make_complaint()
    response = client.post(
        f"/api/complaints/{complaint['id']}/feedback",
        json={"rating": 5, "comment": "Rating this far too early."},
        headers=auth(student_token),
    )
    assert response.status_code == 409


def test_feedback_cannot_be_submitted_twice(client, auth, student_token, officer_token, make_complaint):
    complaint = make_complaint()
    _resolve(client, auth, officer_token, complaint["id"])
    body = {"rating": 4, "comment": "Good work overall, thanks."}

    client.post(f"/api/complaints/{complaint['id']}/feedback", json=body, headers=auth(student_token))
    second = client.post(
        f"/api/complaints/{complaint['id']}/feedback", json=body, headers=auth(student_token)
    )
    assert second.status_code == 409


def test_only_the_complainant_can_rate(client, auth, officer_token, make_complaint):
    complaint = make_complaint()
    _resolve(client, auth, officer_token, complaint["id"])

    other = client.post(
        "/api/auth/login",
        json={"identifier": "sneha.bhardwaj@dsvv.ac.in", "password": "student123"},
    ).get_json()["data"]["token"]

    response = client.post(
        f"/api/complaints/{complaint['id']}/feedback",
        json={"rating": 1, "comment": "Not my complaint at all."},
        headers=auth(other),
    )
    assert response.status_code in (403, 409)


def test_invalid_rating_is_rejected(client, auth, student_token, officer_token, make_complaint):
    complaint = make_complaint()
    _resolve(client, auth, officer_token, complaint["id"])

    response = client.post(
        f"/api/complaints/{complaint['id']}/feedback",
        json={"rating": 9, "comment": "Rating outside the allowed range."},
        headers=auth(student_token),
    )
    assert response.status_code == 422


def test_reopen_after_an_unsatisfactory_resolution(client, auth, student_token, officer_token, make_complaint):
    complaint = make_complaint()
    _resolve(client, auth, officer_token, complaint["id"])

    response = client.post(
        f"/api/complaints/{complaint['id']}/reopen",
        json={"reason": "The leakage restarted the next morning."},
        headers=auth(student_token),
    )

    data = response.get_json()["data"]
    assert response.status_code == 200
    assert data["status"] == "Reopened"
    assert data["resolvedAt"] is None


def test_reopen_requires_a_reason(client, auth, student_token, officer_token, make_complaint):
    complaint = make_complaint()
    _resolve(client, auth, officer_token, complaint["id"])

    response = client.post(
        f"/api/complaints/{complaint['id']}/reopen", json={"reason": ""}, headers=auth(student_token)
    )
    assert response.status_code == 422


def test_an_unresolved_complaint_cannot_be_reopened(client, auth, student_token, make_complaint):
    complaint = make_complaint()
    response = client.post(
        f"/api/complaints/{complaint['id']}/reopen",
        json={"reason": "Trying to reopen something still open."},
        headers=auth(student_token),
    )
    assert response.status_code == 409


# ------------------------------------------------------ assignment & admin


def test_admin_reassigns_to_another_officer(client, auth, admin_token, make_complaint):
    """Reassignment also moves the complaint into the new officer's department."""
    complaint = make_complaint()

    officers = client.get("/api/officers", headers=auth(admin_token)).get_json()["data"]
    target = next(o for o in officers if o["id"] != complaint["assignedOfficer"]["id"])

    response = client.put(
        f"/api/complaints/{complaint['id']}/reassign",
        json={"officerId": target["id"], "reason": "Balancing the workload."},
        headers=auth(admin_token),
    )

    data = response.get_json()["data"]
    assert response.status_code == 200
    assert data["assignedOfficer"]["id"] == target["id"]
    assert data["department"] == target["department"]

    # The move is recorded as a reassignment in the history.
    history = client.get(
        f"/api/complaints/{complaint['id']}/history", headers=auth(admin_token)
    ).get_json()["data"]
    assert history["assignments"][-1]["type"] == "reassignment"


def test_student_cannot_assign_officers(client, auth, student_token, make_complaint):
    complaint = make_complaint()
    response = client.post(
        f"/api/complaints/{complaint['id']}/assign",
        json={"officerId": "OFF-2001"},
        headers=auth(student_token),
    )
    assert response.status_code == 403


def test_priority_change_recalculates_the_deadline(client, auth, admin_token, make_complaint):
    complaint = make_complaint()
    original = complaint["deadline"]

    response = client.put(
        f"/api/complaints/{complaint['id']}/priority",
        json={"priority": "Urgent"},
        headers=auth(admin_token),
    )

    data = response.get_json()["data"]
    assert data["priority"] == "Urgent"
    assert data["deadline"] != original


def test_assigned_officer_can_change_priority(client, auth, officer_token, make_complaint):
    """Department officers can adjust SLA priority for work in their queue."""
    complaint = make_complaint()

    response = client.put(
        f"/api/complaints/{complaint['id']}/priority",
        json={"priority": "Urgent"}, headers=auth(officer_token),
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["priority"] == "Urgent"


def test_officer_cannot_change_priority_outside_their_department(client, auth, make_complaint):
    complaint = make_complaint()
    other_officer = client.post(
        "/api/auth/login",
        json={"identifier": "officer@dsvv.ac.in", "password": "officer123"},
    ).get_json()["data"]["token"]

    response = client.put(
        f"/api/complaints/{complaint['id']}/priority",
        json={"priority": "Urgent"}, headers=auth(other_officer),
    )

    assert response.status_code == 403


def test_escalation_raises_the_level(client, auth, admin_token, make_complaint):
    complaint = make_complaint()
    response = client.post(
        f"/api/complaints/{complaint['id']}/escalate",
        json={"reason": "Deadline missed."},
        headers=auth(admin_token),
    )

    data = response.get_json()["data"]
    assert data["status"] == "Escalated"
    assert data["escalationLevel"] == 1
    assert data["escalationAuthority"]


def test_complaint_history_endpoint(client, auth, student_token, officer_token, make_complaint):
    complaint = make_complaint()
    client.post(
        f"/api/complaints/{complaint['id']}/remarks",
        json={"message": "Work has started on site."},
        headers=auth(officer_token),
    )

    data = client.get(
        f"/api/complaints/{complaint['id']}/history", headers=auth(student_token)
    ).get_json()["data"]

    assert data["timeline"]
    assert len(data["remarks"]) == 1
    assert data["assignments"]


# -------------------------------------------------------------- file upload


def _png():
    return io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)


def test_complaint_with_a_valid_image(client, auth, student_token, water_complaint):
    import json as json_module

    response = client.post(
        "/api/complaints",
        data={
            "title": water_complaint["title"],
            "description": water_complaint["description"],
            "category": "Water",
            "location": json_module.dumps(water_complaint["location"]),
            "files": (_png(), "leak.png"),
        },
        content_type="multipart/form-data",
        headers=auth(student_token),
    )

    assert response.status_code == 201
    evidence = response.get_json()["data"]["evidence"]
    assert len(evidence) == 1
    assert evidence[0]["kind"] == "image"
    assert evidence[0]["url"].startswith("/api/files/")


def test_upload_rejects_a_disallowed_extension(client, auth, student_token, water_complaint):
    response = client.post(
        "/api/complaints",
        data={
            "title": water_complaint["title"],
            "description": water_complaint["description"],
            "category": "Water",
            "files": (io.BytesIO(b"MZ\x90\x00malware"), "payload.exe"),
        },
        content_type="multipart/form-data",
        headers=auth(student_token),
    )
    assert response.status_code == 400


def test_upload_rejects_a_file_whose_bytes_contradict_its_name(client, auth, student_token, water_complaint):
    """A renamed executable must not pass as a PNG."""
    response = client.post(
        "/api/complaints",
        data={
            "title": water_complaint["title"],
            "description": water_complaint["description"],
            "category": "Water",
            "files": (io.BytesIO(b"MZ\x90\x00this-is-an-exe"), "disguised.png"),
        },
        content_type="multipart/form-data",
        headers=auth(student_token),
    )
    assert response.status_code == 400
    assert "PNG" in response.get_json()["message"]


def test_uploaded_file_requires_authentication_to_download(client, auth, student_token, water_complaint):
    import json as json_module

    created = client.post(
        "/api/complaints",
        data={
            "title": water_complaint["title"],
            "description": water_complaint["description"],
            "category": "Water",
            "location": json_module.dumps(water_complaint["location"]),
            "files": (_png(), "leak.png"),
        },
        content_type="multipart/form-data",
        headers=auth(student_token),
    )
    url = created.get_json()["data"]["evidence"][0]["url"]

    assert client.get(url).status_code == 401
    download = client.get(url, headers=auth(student_token))
    assert download.status_code == 200
    assert download.headers["Content-Disposition"].startswith("attachment;")


# ---------------------------------------------------- guest & snapshot tests


def test_registered_complaint_has_complete_submitter_snapshot(app, client, make_complaint):
    complaint = make_complaint()
    submitter = complaint["submittedBy"]

    assert submitter["type"] == "registered"
    assert submitter["isVerified"] is True
    assert submitter["id"] == "USR-1001"
    assert submitter["name"] == "Rakesh Patidar"
    assert submitter["email"] == "student@dsvv.ac.in"
    assert submitter["userId"] == "MCA/2024/018"
    assert submitter["scholarId"] == "MCA/2024/018"


def test_registered_service_creation_uses_account_snapshot(app):
    from database import users
    from services import complaint_service

    account = users().find_one({"id": "USR-1001"}, {"_id": 0, "passwordHash": 0})
    payload = {
        "title": "Water cooler leaking near library gate",
        "description": "Continuous water leakage near the central library water cooler for the past three hours.",
        "category": "Water",
        "submitter": {
            "type": "guest",
            "name": "Forged Name",
            "scholarId": "FORGED/2026/001",
            "email": "forged@example.com",
            "mobile": "9876543210",
        },
    }

    complaint = complaint_service.create_complaint(payload, user=account)

    submitter = complaint["submittedBy"]
    assert submitter["type"] == "registered"
    assert submitter["isVerified"] is True
    assert submitter["id"] == account["id"]
    assert submitter["name"] == account["name"]
    assert submitter["scholarId"] == account["userId"]
    assert submitter["email"] == account["email"]
    assert submitter["mobile"] == account["mobile"]


def test_guest_complaint_creation_does_not_create_account(app):
    from database import users
    from services import complaint_service

    initial_user_count = users().count_documents({})

    payload = {
        "title": "Water cooler leaking near library gate",
        "description": "Continuous water leakage near the central library water cooler for the past three hours.",
        "category": "Water",
        "location": {"latitude": 29.99965, "longitude": 78.1946, "address": "Central Library Gate"},
        "submitter": {
            "name": "Arjun Sharma",
            "scholarId": "GUEST/2026/999",
            "email": "arjun.guest@example.com",
            "mobile": "9876543210",
        },
    }

    complaint = complaint_service.create_complaint(payload, user=None)

    assert complaint["id"].startswith("DSVV-GRV-")
    assert complaint["status"] in ("Submitted", "Assigned")
    assert users().count_documents({}) == initial_user_count

    submitter = complaint["submittedBy"]
    assert submitter["type"] == "guest"
    assert submitter["id"] is None
    assert submitter["isVerified"] is False
    assert submitter["name"] == "Arjun Sharma"
    assert submitter["email"] == "arjun.guest@example.com"
    assert submitter["mobile"] == "9876543210"
    assert submitter["scholarId"] == "GUEST/2026/999"


def test_malformed_submitter_snapshot_does_not_crash_guest_creation(app):
    from services import complaint_service

    payload = {
        "title": "Broken window in hostel corridor",
        "description": "The window glass in the corridor is completely shattered and dangerous.",
        "category": "Building",
        "submitter": ["unexpected", "shape"],
    }

    complaint = complaint_service.create_complaint(payload, user=None)

    assert complaint["submittedBy"]["type"] == "guest"
    assert complaint["submittedBy"]["id"] is None
    assert complaint["submittedBy"]["isVerified"] is False


def test_guest_personal_details_never_leak_in_public_tracking(app):
    from services import complaint_service

    payload = {
        "title": "Broken window in hostel corridor",
        "description": "The window glass in the corridor is completely shattered and dangerous.",
        "category": "Building",
        "location": {"latitude": 29.99965, "longitude": 78.1946, "address": "Gayatri Bhavan Corridor"},
        "submitter": {
            "name": "Guest Visitor",
            "scholarId": "SCH-GUEST-001",
            "email": "private.guest@example.com",
            "mobile": "9876543210",
        },
    }

    complaint = complaint_service.create_complaint(payload, user=None)
    tracked = complaint_service.track(complaint["id"])

    assert tracked["submittedBy"]["name"] == "Guest"
    assert "Guest Visitor" not in str(tracked)
    assert "email" not in tracked["submittedBy"]
    assert "mobile" not in tracked["submittedBy"]
    assert "userId" not in tracked["submittedBy"]
    assert "scholarId" not in tracked["submittedBy"]
    assert "id" not in tracked["submittedBy"]


def test_computer_lab_fields_preserved_when_routed_elsewhere(app):
    from services import complaint_service

    payload = {
        "title": "Severe water leakage above computer lab ceiling",
        "description": "Continuous water dripping directly from the ceiling onto computer workstations in BCA Lab.",
        "category": "Computer/Lab",
        "lab": "BCA Lab",
        "systemNumber": "System 12",
        "location": {"latitude": 29.99965, "longitude": 78.1946, "address": "BCA Lab Room 101"},
    }

    user = {
        "id": "USR-1001",
        "name": "Rakesh Patidar",
        "userId": "MCA/2024/018",
        "email": "student@dsvv.ac.in",
        "role": "student",
    }
    complaint = complaint_service.create_complaint(payload, user=user)

    # Classification keyword "water" routes it to Jal Kal Vibhag
    assert complaint["department"] == "Jal Kal Vibhag"
    # But Computer/Lab metadata must remain preserved
    assert complaint["lab"] == "BCA Lab"
    assert complaint["systemNumber"] == "System 12"


def test_assignment_history_failure_does_not_abort_complaint_creation(app, monkeypatch):
    from services import assignment_service, complaint_service

    def fail_record(*args, **kwargs):
        raise RuntimeError("Database connection glitch while recording assignment")

    monkeypatch.setattr(assignment_service, "record_assignment", fail_record)

    payload = {
        "title": "Water leakage in canteen washroom",
        "description": "Water tap is broken and water is flowing all over the floor in the canteen washroom.",
        "category": "Water",
        "location": {"latitude": 29.99965, "longitude": 78.1946, "address": "Canteen washroom"},
    }

    complaint = complaint_service.create_complaint(payload, user=None)
    assert complaint["id"].startswith("DSVV-GRV-")
    assert complaint_service.track(complaint["id"])["id"] == complaint["id"]
