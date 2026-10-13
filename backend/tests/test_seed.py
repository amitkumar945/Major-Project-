"""Coverage for idempotent account seeding."""


def test_seed_users_skips_an_existing_id_with_a_different_email(app):
    import seed
    from database import users

    users().update_one(
        {"id": "USR-1001"},
        {"$set": {"email": "legacy.student@dsvv.ac.in"}},
    )

    with app.app_context():
        created = seed.seed_users()

    existing = users().find_one({"id": "USR-1001"})
    assert created == 0
    assert existing["email"] == "legacy.student@dsvv.ac.in"
