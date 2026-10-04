"""Integration coverage for the optional local UI demonstration dataset."""


def test_demo_seed_populates_chartable_data_and_is_idempotent(client, auth, admin_token):
    import seed
    from database import complaints

    first = seed.run(verbose=False, include_demo_data=True)
    second = seed.run(verbose=False, include_demo_data=True)

    assert first["demoComplaints"] == len(seed.DEMO_COMPLAINTS)
    assert second["demoComplaints"] == 0
    assert complaints().count_documents({"isDemoFixture": True}) == len(seed.DEMO_COMPLAINTS)

    headers = auth(admin_token)
    overview = client.get("/api/analytics/overview", headers=headers)
    assert overview.status_code == 200
    data = overview.get_json()["data"]

    assert data["metrics"]["total"] == len(seed.DEMO_COMPLAINTS)
    assert any(row["value"] for row in data["byDepartment"])
    assert any(row["value"] for row in data["byPriority"])
    assert any(row["registered"] for row in data["monthlyTrend"])
    assert data["feedbackCount"] > 0

    complaints_response = client.get("/api/complaints?pageSize=100", headers=headers)
    assert complaints_response.status_code == 200
    assert complaints_response.get_json()["data"]["total"] == len(seed.DEMO_COMPLAINTS)
