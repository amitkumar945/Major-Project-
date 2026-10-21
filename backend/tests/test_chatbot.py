"""FAQ behavior and permission checks for the conversational assistant."""

import os

import pytest


def ask(client, question, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/api/chatbot/message", json={"message": question}, headers=headers)


def test_chatbot_falls_back_to_grounded_faq_without_provider(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "CHATBOT_AI_API_KEY", "")
    response = ask(client, "There is water leakage near my hostel")

    assert response.status_code == 200
    assert response.get_json()["data"]["method"] == "faq"
    assert response.get_json()["data"]["source"] == "local_faq"
    assert "not configured" in response.get_json()["data"]["sourceNotice"]
    assert "Jal Kal Vibhag" in response.get_json()["data"]["reply"]


def test_chatbot_falls_back_when_provider_times_out(app, monkeypatch):
    from openai import APITimeoutError
    from services import chatbot_service

    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "configured-test-key")

    timeout = APITimeoutError.__new__(APITimeoutError)
    BaseException.__init__(timeout, "test timeout")

    class FailingClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        @property
        def chat(self):
            raise timeout

    monkeypatch.setattr(chatbot_service, "OpenAI", FailingClient)

    reply, method = chatbot_service.answer("How do I track my complaint?", app.config)

    assert method == "faq"
    assert "/track.html" in reply


def test_chatbot_provider_receives_only_redacted_current_question(app, monkeypatch):
    from services import chatbot_service

    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "test-only-key")
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["request"] = kwargs
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": type("Message", (), {"content": "Use the secure reset page."})()},
                        )()
                    ]
                },
            )()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setitem(app.config, "OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setattr(chatbot_service, "OpenAI", FakeClient)
    reply, method = chatbot_service.answer(
        "My password is secret123, email me@private.test, phone 9876543210, "
        "complaint DSVV-GRV-2026-00123, student ID GUEST/2026/001; how reset?",
        app.config,
    )
    request = captured["request"]
    sent = request["messages"][-1]["content"]

    assert method == "ai"
    assert reply == "Use the secure reset page."
    assert request["model"] == "gpt-4o-mini"
    assert captured["client"]["api_key"] == "test-only-key"
    assert all(value not in sent for value in (
        "secret123", "me@private.test", "9876543210",
        "DSVV-GRV-2026-00123", "GUEST/2026/001",
    ))


def test_chatbot_provider_receives_redacted_follow_up_history(app, monkeypatch):
    from services import chatbot_service

    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "test-only-key")
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["messages"] = kwargs["messages"]
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": type("Message", (), {"content": "Use the tracking page."})()},
                        )()
                    ]
                },
            )()

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(chatbot_service, "OpenAI", FakeClient)
    reply, method = chatbot_service.answer(
        "Can I see its status?",
        app.config,
        [
            {"role": "user", "content": "How do I track DSVV-GRV-2026-00123?"},
            {"role": "assistant", "content": "Use /track.html or email me@private.test."},
        ],
    )

    history = captured["messages"][1:-1]
    assert method == "ai"
    assert reply == "Use the tracking page."
    assert history[0]["role"] == "user"
    assert "DSVV-GRV-2026-00123" not in history[0]["content"]
    assert "me@private.test" not in history[1]["content"]


def test_chatbot_persists_and_reuses_only_redacted_ai_history(client, app, monkeypatch):
    from services import chatbot_service

    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "test-only-key")
    captured = []

    class FakeCompletions:
        def create(self, **kwargs):
            captured.append(kwargs["messages"])
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": type("Message", (), {"content": "Use the grievance portal."})()},
                        )()
                    ]
                },
            )()

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(chatbot_service, "OpenAI", FakeClient)
    first = ask(client, "How can I use the portal? My email is me@private.test.")
    session_id = first.get_json()["data"]["sessionId"]
    second = client.post(
        "/api/chatbot/message",
        json={"message": "What about tracking?", "sessionId": session_id},
    )

    follow_up = captured[1][1:-1]
    assert first.get_json()["data"]["source"] == "ai"
    assert second.get_json()["data"]["source"] == "ai"
    assert follow_up[0]["role"] == "user"
    assert "me@private.test" not in follow_up[0]["content"]


@pytest.mark.parametrize("failure", ["invalid_key", "quota", "rate_limit", "timeout"])
def test_chatbot_provider_errors_return_faq_without_exposing_error(
    client, app, monkeypatch, failure
):
    from openai import APITimeoutError, AuthenticationError, RateLimitError
    from services import chatbot_service

    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "invalid-test-key")

    def provider_error():
        error_type = {
            "invalid_key": AuthenticationError,
            "quota": RateLimitError,
            "rate_limit": RateLimitError,
            "timeout": APITimeoutError,
        }[failure]
        error = error_type.__new__(error_type)
        BaseException.__init__(error, "private provider error and invalid-test-key")
        return error

    class FailingClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        @property
        def chat(self):
            raise provider_error()

    monkeypatch.setattr(chatbot_service, "OpenAI", FailingClient)
    response = ask(client, "What can I do on the grievance portal?")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["data"]["method"] == "faq"
    assert payload["data"]["source"] == "local_faq"
    assert "unavailable" in payload["data"]["sourceNotice"]
    assert "invalid-test-key" not in response.get_data(as_text=True)
    assert "private provider detail" not in response.get_data(as_text=True)


def test_chatbot_understands_hindi_and_hinglish_faqs(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "CHATBOT_AI_API_KEY", "")
    hindi = ask(client, "नल से पानी leak हो रहा है, किस विभाग में जाऊँ?").get_json()["data"]["reply"]
    hinglish = ask(client, "Mere room ki light aur fan ke liye kis vibhag me jaun?").get_json()["data"]["reply"]

    assert "Jal Kal Vibhag" in hindi
    assert "Vidyut Vibhag" in hinglish


def test_chatbot_treats_whitespace_provider_key_as_unconfigured(app, monkeypatch):
    from services import chatbot_service

    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "   ")
    monkeypatch.setitem(app.config, "CHATBOT_AI_API_KEY", "")

    def unexpected_provider_call(**kwargs):
        raise AssertionError("Provider must not be called with a blank key")

    monkeypatch.setattr(chatbot_service, "OpenAI", unexpected_provider_call)
    reply, method = chatbot_service.answer("How do I track a complaint?", app.config)

    assert method == "faq"
    assert "/track.html" in reply


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Mere room ki light aur fan ke liye kis vibhag me jaun?", "hinglish"),
        ("Aapki complaint ka status kya hai?", "hinglish"),
        ("नल से पानी नहीं आ रहा है", "hi"),
        ("How do I track a complaint?", "en"),
    ],
)
def test_chatbot_detects_common_language_styles(message, expected):
    from services.chatbot_service import _language_style

    assert _language_style(message) == expected


@pytest.mark.parametrize(
    ("question", "expected_text", "expected_language"),
    [
        ("मेरी शिकायत कैसे दर्ज करें?", "/student/new-complaint.html", "hi"),
        ("मेरी शिकायत की स्थिति बताओ।", "reference number", "hi"),
        ("How can I register a complaint?", "/student/new-complaint.html", "en"),
        ("How do I track my grievance?", "reference number", "en"),
        ("Mujhe apni complaint register karni hai, kaise karu?", "Complaint register", "hinglish"),
        ("Meri electricity complaint ka status kya hai?", "reference number", "hinglish"),
        ("Meri water leakage complaint ka status batao.", "reference number", "hinglish"),
        ("Computer lab ka system kaam nahi kar raha, complaint kaise karun?", "Computer/Lab", "hinglish"),
        ("नल से पानी नहीं आ रहा है, किस विभाग से संपर्क करूँ?", "Jal Kal Vibhag", "hi"),
        ("Mere kamre ki light kaam nhi kar rahi, konsa vibhag?", "Vidyut Vibhag", "hinglish"),
        ("Complaint ka status kaha dekhu?", "reference number", "hinglish"),
    ],
)
def test_chatbot_localized_faq_covers_requested_messages(
    client, app, monkeypatch, question, expected_text, expected_language
):
    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "")
    response = ask(client, question)
    data = response.get_json()["data"]

    assert response.status_code == 200
    assert data["source"] == "local_faq"
    assert expected_text.lower() in data["reply"].lower()
    if expected_language == "hi":
        assert any("\u0900" <= character <= "\u097f" for character in data["reply"])
    elif expected_language == "hinglish":
        assert not any("\u0900" <= character <= "\u097f" for character in data["reply"])


def test_chatbot_remembers_hinglish_style_and_asks_for_reference(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "")
    first = ask(client, "Maine complaint register ki hai.").get_json()["data"]
    follow_up = client.post(
        "/api/chatbot/message",
        json={"message": "Ab iska status kaise check karu?", "sessionId": first["sessionId"]},
    ).get_json()["data"]

    assert "reference number" in first["reply"].lower()
    assert "reference number" in follow_up["reply"].lower()
    assert not any("\u0900" <= character <= "\u097f" for character in follow_up["reply"])
    assert follow_up["source"] == "local_faq"


@pytest.mark.parametrize(
    ("start_message", "category_message", "expected_prompt", "expected_script"),
    [
        ("नई शिकायत दर्ज करें", "पानी", "कैंपस में समस्या कहाँ है", "hi"),
        ("shikayat darj karo", "pani", "Campus mein issue kahan hai", "hinglish"),
    ],
)
def test_guided_complaint_flow_uses_hindi_and_hinglish(
    client, student_token, start_message, category_message, expected_prompt, expected_script
):
    # Unauthenticated visitor must be asked to log in first
    unauth = ask(client, start_message).get_json()["data"]
    assert unauth["step"] == "auth_required"
    assert unauth["authRequired"] is True
    if expected_script == "hi":
        assert "लॉग इन" in unauth["reply"] or "खाते" in unauth["reply"]
    else:
        assert "login" in unauth["reply"].lower()

    # Authenticated student can proceed with complaint flow
    first = ask(client, start_message, token=student_token).get_json()["data"]
    category = client.post(
        "/api/chatbot/message",
        json={"message": category_message, "sessionId": first["sessionId"]},
        headers={"Authorization": f"Bearer {student_token}"},
    ).get_json()["data"]

    assert first["method"] == "complaint_flow"
    assert category["draft"]["category"] == "Water"
    assert expected_prompt in category["reply"]
    assert (
        any("\u0900" <= character <= "\u097f" for character in category["reply"])
        if expected_script == "hi"
        else not any("\u0900" <= character <= "\u097f" for character in category["reply"])
    )


@pytest.mark.parametrize(
    ("start_message", "category_message", "confirmation"),
    [
        ("I want to register a complaint", "Water", "yes"),
        ("मुझे शिकायत दर्ज करनी है", "पानी", "हाँ"),
        ("Mujhe complaint register karni hai", "pani", "haan"),
    ],
)
def test_voice_transcript_complaint_flow_requires_spoken_confirmation(
    client, student_token, start_message, category_message, confirmation
):
    from database import complaints

    started = _chat_step(client, start_message, token=student_token)
    session_id = started["sessionId"]
    assert started["step"] == "category"

    category = _chat_step(
        client, category_message, session_id=session_id, token=student_token
    )
    assert category["draft"]["category"] == "Water"
    assert category["step"] == "location"
    _chat_step(
        client, "Gayatri Bhavan hostel entrance", session_id=session_id, token=student_token
    )
    desc_step = _chat_step(
        client,
        "Water has been leaking from the pipe near the hostel entrance for two days.",
        session_id=session_id,
        token=student_token,
    )
    assert desc_step["step"] == "scholarId"
    id_step = _chat_step(
        client, "MCA/2024/018", session_id=session_id, token=student_token
    )
    assert id_step["step"] == "mobile"
    mob_step = _chat_step(
        client, "9876543210", session_id=session_id, token=student_token
    )
    assert mob_step["step"] == "confirm_identity"
    summary = _chat_step(
        client, confirmation, session_id=session_id, token=student_token
    )
    assert summary["step"] == "confirm"
    assert complaints().find_one({"_chatbotSessionId": session_id}) is None

    not_confirmed = _chat_step(
        client, "maybe", session_id=session_id, token=student_token
    )
    assert not_confirmed["step"] == "confirm"
    assert complaints().find_one({"_chatbotSessionId": session_id}) is None

    submitted = _chat_step(
        client,
        confirmation,
        session_id=session_id,
        token=student_token,
        expected_status=201,
    )
    assert submitted["step"] == "done"
    assert submitted["created"] is True
    assert complaints().find_one({"_chatbotSessionId": session_id})["id"] == submitted["complaint"]["id"]


def test_chatbot_tracks_follow_up_from_authorized_session(
    client, auth, make_complaint, student_token
):
    complaint = make_complaint()
    first = ask(
        client,
        f"Meri complaint ka status kya hai? {complaint['id']}",
        student_token,
    ).get_json()["data"]
    follow_up = client.post(
        "/api/chatbot/message",
        json={"message": "Ab iska status batao.", "sessionId": first["sessionId"]},
        headers=auth(student_token),
    ).get_json()["data"]

    assert first["method"] == "verified_record"
    assert follow_up["method"] == "verified_record"
    assert follow_up["complaint"]["id"] == complaint["id"]


def test_chatbot_provider_receives_original_hindi_message(app, monkeypatch):
    from services import chatbot_service

    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "test-only-key")
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["request"] = kwargs
            return type(
                "Response",
                (),
                {
                    "choices": [
                        type(
                            "Choice",
                            (),
                            {"message": type("Message", (), {"content": "शिकायत फॉर्म खोलें।"})()},
                        )()
                    ]
                },
            )()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(chatbot_service, "OpenAI", FakeClient)
    prompt = "मेरी शिकायत कैसे दर्ज करें?"
    reply, method = chatbot_service.answer(prompt, app.config)

    assert method == "ai"
    assert reply == "शिकायत फॉर्म खोलें।"
    assert captured["request"]["messages"][-1]["content"] == prompt
    assert captured["request"]["model"] == app.config["OPENAI_MODEL"]


def test_chatbot_validates_message_length_and_empty_questions(client):
    assert ask(client, " ").status_code == 422
    assert ask(client, "x" * 1201).status_code == 422
    assert client.post("/api/chatbot/message", json=["not", "an", "object"]).status_code == 422


def test_chatbot_status_requires_login(client, make_complaint):
    complaint = make_complaint()
    response = ask(client, f"What is the status of {complaint['id']}?")

    assert response.status_code == 200
    assert response.get_json()["data"]["action"]["href"] == "/login.html"
    assert "status" not in response.get_json()["data"]


def test_chatbot_returns_only_the_signed_in_users_complaint(client, make_complaint, student_token):
    complaint = make_complaint()
    owner = ask(client, f"Track status for {complaint['id']}", student_token)
    stranger_login = client.post(
        "/api/auth/login",
        json={"identifier": "sneha.bhardwaj@dsvv.ac.in", "password": "student123"},
    )
    stranger_token = stranger_login.get_json()["data"]["token"]
    stranger = ask(client, f"Track status for {complaint['id']}", stranger_token)

    assert owner.status_code == 200
    assert owner.get_json()["data"]["method"] == "verified_record"
    assert owner.get_json()["data"]["complaint"]["id"] == complaint["id"]
    assert stranger.status_code == 200
    assert "couldn't find" in stranger.get_json()["data"]["reply"]


def test_chatbot_rate_limit_is_applied(client, app, monkeypatch):
    from utils import rate_limit

    rate_limit.reset()
    monkeypatch.setitem(app.config, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setitem(app.config, "RATE_LIMIT_CHATBOT", 30)
    for _ in range(30):
        assert ask(client, "How do I register a grievance?").status_code == 200
    limited = ask(client, "How do I register a grievance?")

    assert limited.status_code == 429


def test_chatbot_rate_limit_ignores_untrusted_forwarded_for(client, app, monkeypatch):
    from utils import rate_limit

    rate_limit.reset()
    monkeypatch.setitem(app.config, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setitem(app.config, "RATE_LIMIT_CHATBOT", 1)
    headers = {"X-Forwarded-For": "198.51.100.1"}
    first = client.post(
        "/api/chatbot/message",
        json={"message": "Hello"},
        headers=headers,
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
    )
    second = client.post(
        "/api/chatbot/message",
        json={"message": "Hello again"},
        headers={"X-Forwarded-For": "198.51.100.2"},
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
    )

    assert first.status_code == 200
    assert second.status_code == 429


def test_shared_chatbot_rate_limit_survives_local_counter_reset(app, monkeypatch):
    from database import rate_limit_windows
    from utils import rate_limit

    monkeypatch.setitem(app.config, "CHATBOT_SHARED_RATE_LIMIT", True)
    monkeypatch.setitem(app.config, "RATE_LIMIT_ENABLED", True)
    client_key = "test-client-key-that-is-not-an-ip"

    with app.app_context():
        assert rate_limit.check(
            "chatbot", limit=1, window=60, client_key=client_key
        ) == (True, 0)
        # Clearing process memory simulates the next worker handling the turn.
        rate_limit.reset()
        allowed, retry_after = rate_limit.check(
            "chatbot", limit=1, window=60, client_key=client_key
        )

        assert allowed is False
        assert retry_after > 0
        saved = rate_limit_windows().find_one({"count": 2}, {"_id": 1})
        assert saved is not None
        assert client_key not in saved["_id"]


def test_chatbot_rejects_oversized_requests(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setitem(app.config, "CHATBOT_MAX_REQUEST_BYTES", 32)

    response = client.post("/api/chatbot/message", json={"message": "x" * 100})

    assert response.status_code == 413
    assert "too large" in response.get_json()["message"].lower()


@pytest.mark.skipif(
    os.environ.get("RUN_OPENAI_INTEGRATION_TESTS") != "1",
    reason="Set RUN_OPENAI_INTEGRATION_TESTS=1 to make billable OpenAI requests.",
)
def test_chatbot_live_openai_integration(app):
    from config import Config
    from services import chatbot_service

    provider_config = {
        "OPENAI_API_KEY": Config.OPENAI_API_KEY,
        "OPENAI_MODEL": Config.OPENAI_MODEL,
        "OPENAI_BASE_URL": Config.OPENAI_BASE_URL,
        "OPENAI_TIMEOUT": Config.OPENAI_TIMEOUT,
    }
    if not provider_config["OPENAI_API_KEY"]:
        pytest.skip("OPENAI_API_KEY is not configured.")

    prompts = [
        "Explain how to track a grievance in English.",
        "कृपया grievance track करने का तरीका Hindi में बताइए।",
        "Hinglish mein batao, complaint ka status kaise dekhun?",
        "And where can I submit feedback?",
    ]
    history = []
    for prompt in prompts:
        reply, method = chatbot_service.answer(prompt, provider_config, history)
        assert method == "ai"
        assert reply.strip()
        history.extend(
            [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": reply},
            ]
        )


# ------------------------------------------------ Phase 2: State Machine Tests


def _chat_step(client, message, session_id=None, token=None, action=None, expected_status=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body = {"message": message}
    if session_id:
        body["sessionId"] = session_id
    if action:
        body["action"] = action
    res = client.post("/api/chatbot/message", json=body, headers=headers)
    assert res.status_code in (200, 201), res.get_json()
    if expected_status is not None:
        assert res.status_code == expected_status, res.get_json()
    return res.get_json()["data"]


def test_registered_user_complaint_flow(client, auth, student_token, admin_token):
    # 1. Start complaint flow
    step1 = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = step1["sessionId"]
    assert step1["step"] == "category"
    assert "Computer/Lab" in step1["quickReplies"]

    # 2. Category: Computer/Lab
    step2 = _chat_step(client, "Computer/Lab", session_id=session_id, token=student_token)
    assert step2["step"] == "lab"
    assert "MCA Lab" in step2["quickReplies"]

    # 3. Lab: MCA Lab
    step3 = _chat_step(client, "MCA Lab", session_id=session_id, token=student_token)
    assert step3["step"] == "systemNumber"

    # 4. System number: System 14
    step4 = _chat_step(client, "System 14", session_id=session_id, token=student_token)
    assert step4["step"] == "description"

    # 5. Description: >= 25 chars
    desc = "The monitor display has heavy green flickering and powers off intermittently during lab practicals."
    step5 = _chat_step(client, desc, session_id=session_id, token=student_token)
    assert step5["step"] == "scholarId"

    # 6. Scholar ID (matches student account)
    step6 = _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)
    assert step6["step"] == "mobile"

    # 7. Mobile (account has no mobile registered)
    step7 = _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    assert step7["step"] == "confirm_identity"

    # 8. Confirm identity details
    step8 = _chat_step(client, "Yes, details are correct", session_id=session_id, token=student_token)
    assert step8["step"] == "confirm"
    assert "Submit" in step8["quickReplies"]

    # 9. Submit
    step9 = _chat_step(client, "Submit", session_id=session_id, token=student_token, action="submit")
    assert step9["step"] == "done"
    ref = step9["complaint"]["id"]
    assert ref.startswith("DSVV-GRV-")
    assert step9["complaint"]["department"] == "MCA Lab / Computer Lab"

    # Verify complaint in database
    from database import complaints

    doc = complaints().find_one({"id": ref})
    assert doc is not None
    assert doc["submittedBy"]["type"] == "registered"
    assert doc["submittedBy"]["id"] == "USR-1001"
    assert doc["lab"] == "MCA Lab"
    assert doc["systemNumber"] == "System 14"

    # Verify admin can see it
    admin_res = client.get(f"/api/complaints/{ref}", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_res.status_code == 200
    assert admin_res.get_json()["data"]["id"] == ref
    student_res = client.get("/api/complaints/my", headers=auth(student_token))
    assert student_res.status_code == 200
    assert student_res.get_json()["data"]["items"][0]["id"] == ref


def test_computer_lab_metadata_survives_department_rerouting(client, student_token):
    step1 = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = step1["sessionId"]
    _chat_step(client, "Computer/Lab", session_id=session_id, token=student_token)
    _chat_step(client, "MCA Lab", session_id=session_id, token=student_token)
    _chat_step(client, "System 14", session_id=session_id, token=student_token)
    _chat_step(
        client,
        "The water supply pipe has burst inside the computer lab and is flooding the workstations.",
        session_id=session_id,
        token=student_token,
    )
    _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)
    _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    _chat_step(client, "Yes, details are correct", session_id=session_id, token=student_token)
    created = _chat_step(
        client, "Submit", session_id=session_id, token=student_token,
        action="submit", expected_status=201,
    )

    from database import complaints

    saved = complaints().find_one({"id": created["complaint"]["id"]})
    assert saved["category"] == "Computer/Lab"
    assert saved["department"] == "Jal Kal Vibhag"
    assert saved["lab"] == "MCA Lab"
    assert saved["systemNumber"] == "System 14"


def test_guest_user_complaint_flow(client, student_token):
    # 1. Guest starts without logging in -> rejected with auth_required
    step1 = _chat_step(client, "Raise a complaint")
    session_id = step1["sessionId"]
    assert step1["step"] == "auth_required"
    assert step1["authRequired"] is True
    assert "Please register or log in to your account before raising a complaint." in step1["reply"]
    assert step1["action"]["href"] == "/login.html"
    assert step1["action"]["target"] == "_blank"

    from database import complaints
    assert complaints().count_documents({"_chatbotSessionId": session_id}) == 0

    # 2. After logging in, student can continue and complete the complaint flow
    s1 = _chat_step(client, "Raise a complaint", session_id=session_id, token=student_token)
    assert s1["step"] == "category"

    s2 = _chat_step(client, "Water", session_id=session_id, token=student_token)
    assert s2["step"] == "location"

    s3 = _chat_step(client, "Gayatri Bhavan, Hostel Zone A", session_id=session_id, token=student_token)
    assert s3["step"] == "description"

    desc = "Drinking water cooler on the second floor has been leaking continuously since morning."
    s4 = _chat_step(client, desc, session_id=session_id, token=student_token)
    assert s4["step"] == "scholarId"

    s5 = _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)
    assert s5["step"] == "mobile"

    s6 = _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    assert s6["step"] == "confirm_identity"

    s7 = _chat_step(client, "Yes, details are correct", session_id=session_id, token=student_token)
    assert s7["step"] == "confirm"
    assert "Submit" in s7["quickReplies"]

    step9 = _chat_step(
        client, "Submit", session_id=session_id, token=student_token, action="submit"
    )
    assert step9["step"] == "done"
    ref = step9["complaint"]["id"]
    assert ref.startswith("DSVV-GRV-")

    created = complaints().find_one({"id": ref})
    assert created["submittedBy"]["type"] == "registered"
    assert created["submittedBy"]["id"] == "USR-1001"
    assert created["location"]["address"] == "Gayatri Bhavan, Hostel Zone A"


def test_guest_with_registered_scholar_id_still_asks_contact_details(client, student_token):
    # Unauthenticated visitor typing "Raise a complaint" is blocked
    step1 = _chat_step(client, "Raise a complaint")
    assert step1["step"] == "auth_required"
    assert step1["authRequired"] is True

    # Even sending a Scholar ID without login cannot start a complaint or leak user data
    step_id = _chat_step(client, "MCA/2024/018")
    assert step_id["step"] != "confirm"
    assert "Rakesh Patidar" not in step_id["reply"]

    # When authenticated, student can raise a complaint and verify contact details
    auth_step1 = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = auth_step1["sessionId"]
    assert auth_step1["step"] == "category"
    _chat_step(client, "Electricity", session_id=session_id, token=student_token)
    _chat_step(client, "Academic Block C, Second Floor", session_id=session_id, token=student_token)
    _chat_step(client, "Ceiling fan regulator sparking and not turning off in classroom 204.", session_id=session_id, token=student_token)

    step = _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)
    assert step["step"] == "mobile"
    step_mob = _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    assert step_mob["step"] == "confirm_identity"
    step_conf = _chat_step(client, "Yes, details are correct", session_id=session_id, token=student_token)
    assert step_conf["step"] == "confirm"


def test_legacy_autofill_when_ask_identity_false(client, app, monkeypatch, student_token):
    monkeypatch.setitem(app.config, "CHATBOT_ASK_IDENTITY", False)
    # Unauthenticated visitor cannot raise a complaint
    unauth = _chat_step(client, "Raise a complaint")
    assert unauth["step"] == "auth_required"

    # Authenticated student has account details autofilled without asking identity fields
    step1 = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = step1["sessionId"]
    _chat_step(client, "Electricity", session_id=session_id, token=student_token)
    _chat_step(client, "Academic Block C, Second Floor", session_id=session_id, token=student_token)
    step = _chat_step(client, "Ceiling fan regulator sparking and not turning off in classroom 204.", session_id=session_id, token=student_token)
    assert step["step"] == "confirm"
    assert "Rakesh Patidar" in step["reply"]


def test_fast_path_classification_and_confirmation(client, student_token):
    # Unauthenticated problem statement asks user to log in first
    unauth = _chat_step(client, "Mera computer lab me chal nahi raha hai, screen kharab ho gayi hai")
    assert unauth["step"] == "auth_required"
    assert unauth["authRequired"] is True

    # Authenticated user triggers fast path confirmation
    step1 = _chat_step(client, "Mera computer lab me chal nahi raha hai, screen kharab ho gayi hai", token=student_token)
    session_id = step1["sessionId"]

    assert step1["step"] == "confirm_fast_path"
    assert "Computer/Lab" in step1["reply"]

    # Confirm proposed category
    step2 = _chat_step(client, "Yes, Computer/Lab", session_id=session_id, token=student_token)
    assert step2["step"] == "lab"
    assert "MCA Lab" in step2["quickReplies"]


@pytest.mark.parametrize(
    ("problem", "category"),
    [
        ("mera computer kaam nahi kar raha hai", "Computer/Lab"),
        ("pani nahi aa raha hai", "Water"),
        ("bijli chali gayi hai", "Electricity"),
        ("deewar toot gayi hai", "Building"),
        ("पानी नहीं आ रहा है", "Water"),
        ("कंप्यूटर काम नहीं कर रहा है", "Computer/Lab"),
    ],
)
def test_fast_path_recognizes_hinglish_problem_statements(client, student_token, problem, category):
    # Unauthenticated user receives login prompt
    unauth = _chat_step(client, problem)
    assert unauth["step"] == "auth_required"
    assert unauth["authRequired"] is True

    # Authenticated user gets fast path confirmation
    result = _chat_step(client, problem, token=student_token)
    assert result["step"] == "confirm_fast_path"
    assert result["draft"]["description"] == problem
    assert category in result["reply"]


def test_fast_path_low_confidence_offers_categories(client, monkeypatch, student_token):
    from services import chatbot_service

    monkeypatch.setattr(
        chatbot_service.ai_service,
        "classify_department",
        lambda **kwargs: {"department": "Nirman Vibhag", "confidence": 0.35},
    )

    # Unauthenticated
    unauth = _chat_step(client, "My unusual issue affects several campus rooms.")
    assert unauth["step"] == "auth_required"

    # Authenticated
    result = _chat_step(client, "My unusual issue affects several campus rooms.", token=student_token)
    assert result["step"] == "category"
    assert all(cat in result["quickReplies"] for cat in chatbot_service.ALLOWED_CATEGORIES)
    assert result["draft"]["description"] == "My unusual issue affects several campus rooms."


def test_fast_path_uses_existing_urgent_priority_logic(client, student_token):
    # Unauthenticated submit attempt fails
    unauth_start = _chat_step(client, "Mere lab computer me short circuit se smoke aa raha hai")
    assert unauth_start["step"] == "auth_required"

    # Authenticated submit succeeds with urgent priority
    first = _chat_step(client, "Mere lab computer me short circuit se smoke aa raha hai", token=student_token)
    session_id = first["sessionId"]
    accepted = _chat_step(client, "Yes, Computer/Lab", session_id=session_id, token=student_token)
    assert accepted["step"] == "lab"
    _chat_step(client, "MCA Lab", session_id=session_id, token=student_token)
    _chat_step(client, "System 03", session_id=session_id, token=student_token)
    _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)
    _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    confirm = _chat_step(client, "Yes, details are correct", session_id=session_id, token=student_token)
    assert confirm["step"] == "confirm"
    created = _chat_step(client, "Submit", session_id=session_id, token=student_token, action="submit")

    assert created["step"] == "done"
    assert created["complaint"]["priority"] == "Urgent"


def test_invalid_inputs_repeat_questions(client, student_token):
    step1 = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = step1["sessionId"]

    # Invalid category
    invalid_cat = _chat_step(client, "Spacecraft", session_id=session_id, token=student_token)
    assert invalid_cat["step"] == "category"
    assert "not a recognised category" in invalid_cat["reply"]

    # Valid category
    _chat_step(client, "Water", session_id=session_id, token=student_token)

    # Invalid location (too short)
    invalid_loc = _chat_step(client, "ab", session_id=session_id, token=student_token)
    assert invalid_loc["step"] == "location"

    # Valid location
    _chat_step(client, "Central Library", session_id=session_id, token=student_token)

    # Invalid description (too short)
    invalid_desc = _chat_step(client, "leak", session_id=session_id, token=student_token)
    assert invalid_desc["step"] == "description"
    assert "too short" in invalid_desc["reply"]


def test_edit_and_cancel_in_state_machine(client, student_token):
    step1 = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = step1["sessionId"]
    _chat_step(client, "Water", session_id=session_id, token=student_token)

    # Cancel
    cancelled = _chat_step(client, "Cancel", session_id=session_id, token=student_token)
    assert cancelled["step"] == "idle"
    assert "cancelled" in cancelled["reply"].lower()

    # Restart
    _chat_step(client, "Raise a complaint", session_id=session_id, token=student_token)
    _chat_step(client, "Building", session_id=session_id, token=student_token)
    _chat_step(client, "Central Library", session_id=session_id, token=student_token)
    _chat_step(client, "Cracked plaster on the west corridor wall needs inspection and repair.", session_id=session_id, token=student_token)
    _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)
    _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    _chat_step(client, "Yes, details are correct", session_id=session_id, token=student_token)

    # Edit description
    edit_step = _chat_step(client, "Edit", session_id=session_id, token=student_token, action="edit")
    assert edit_step["step"] == "edit"

    choose_desc = _chat_step(client, "Description", session_id=session_id, token=student_token)
    assert choose_desc["step"] == "description"
    updated = _chat_step(
        client,
        "The west corridor wall has new cracks and loose plaster that need repair.",
        session_id=session_id,
        token=student_token,
    )
    assert updated["step"] == "confirm"
    assert "new cracks" in updated["reply"]

    # Submit succeeds with updated description
    submitted = _chat_step(
        client, "Submit", session_id=session_id, token=student_token, action="submit", expected_status=201
    )

    from database import complaints

    saved = complaints().find_one({"id": submitted["complaint"]["id"]})
    assert saved["description"] == (
        "The west corridor wall has new cracks and loose plaster that need repair."
    )


def test_collecting_flow_rechecks_the_first_missing_slot_on_resume(client, student_token):
    started = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = started["sessionId"]

    from database import chatbot_sessions

    chatbot_sessions().update_one(
        {"sessionId": session_id},
        {"$set": {"step": "description"}},
    )
    resumed = _chat_step(client, "Water", session_id=session_id, token=student_token)

    assert resumed["step"] == "location"
    assert resumed["draft"]["category"] == "Water"


def test_guest_mobile_and_email_answers_are_validated(client, student_token):
    # Unauthenticated visitor cannot reach slot collection
    unauth = _chat_step(client, "Raise a complaint")
    assert unauth["step"] == "auth_required"

    # Authenticated user whose account needs mobile: validation applies
    step = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = step["sessionId"]
    _chat_step(client, "Water", session_id=session_id, token=student_token)
    _chat_step(client, "Gayatri Bhavan, Room 214", session_id=session_id, token=student_token)
    _chat_step(
        client,
        "The drinking water tap has been leaking continuously since this morning.",
        session_id=session_id,
        token=student_token,
    )
    _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)

    invalid_mobile = _chat_step(client, "12345", session_id=session_id, token=student_token)
    assert invalid_mobile["step"] == "mobile"
    valid_mobile = _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    assert valid_mobile["step"] == "confirm_identity"


def test_expired_session_starts_a_new_chat_session(client):
    from datetime import timedelta

    from database import chatbot_sessions
    from utils.helpers import utcnow

    first = _chat_step(client, "Raise a complaint")
    chatbot_sessions().update_one(
        {"sessionId": first["sessionId"]},
        {"$set": {"expiresAt": utcnow() - timedelta(minutes=31)}},
    )

    resumed = _chat_step(client, "How do I track a complaint?", session_id=first["sessionId"])

    assert resumed["sessionId"] != first["sessionId"]
    assert resumed["step"] == "idle"
    assert chatbot_sessions().find_one({"sessionId": first["sessionId"]}) is None


def test_guest_submit_is_rate_limited_by_mobile_and_ip(client):
    """Guest complaint and submit attempts are blocked with auth_required without writing to MongoDB."""
    step = _chat_step(client, "Raise a complaint")
    session_id = step["sessionId"]
    assert step["step"] == "auth_required"
    assert step["authRequired"] is True

    res = _chat_step(client, "Submit", session_id=session_id, action="submit")
    assert res["step"] == "auth_required"
    assert res["authRequired"] is True
    from database import complaints
    assert complaints().count_documents({"_chatbotSessionId": session_id}) == 0


def test_idempotent_submit_returns_same_reference(client, student_token):
    step1 = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = step1["sessionId"]
    _chat_step(client, "Electricity", session_id=session_id, token=student_token)
    _chat_step(client, "Central Library, Ground Floor", session_id=session_id, token=student_token)
    _chat_step(client, "Corridor light switch is loose and sparking when touched.", session_id=session_id, token=student_token)
    _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)
    _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    _chat_step(client, "Yes, details are correct", session_id=session_id, token=student_token)

    # Submit 1
    sub1 = _chat_step(client, "Submit", session_id=session_id, action="submit", expected_status=201, token=student_token)
    ref1 = sub1["complaint"]["id"]

    # Submit 2 (retry or double click)
    sub2 = _chat_step(client, "Submit", session_id=session_id, action="submit", expected_status=200, token=student_token)
    ref2 = sub2["complaint"]["id"]

    assert ref1 == ref2
    assert "already been" in sub2["reply"].lower() or "already" in sub2["reply"].lower()
    from database import complaints

    assert complaints().count_documents({"_chatbotSessionId": session_id}) == 1


def test_submitted_session_is_immutable_and_new_complaint_gets_new_session(client, student_token):
    step = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = step["sessionId"]
    _chat_step(client, "Water", session_id=session_id, token=student_token)
    _chat_step(client, "Central Library, Ground Floor", session_id=session_id, token=student_token)
    _chat_step(
        client,
        "The drinking water tap has been leaking continuously since this morning.",
        session_id=session_id,
        token=student_token,
    )
    _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)
    _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    _chat_step(client, "Yes, details are correct", session_id=session_id, token=student_token)
    submitted = _chat_step(client, "Submit", session_id=session_id, action="submit", token=student_token, expected_status=201)

    after_cancel = _chat_step(client, "Cancel", session_id=session_id, action="cancel", token=student_token)
    new_complaint = _chat_step(client, "Raise another complaint", session_id=session_id, token=student_token)

    assert after_cancel["step"] == "done"
    assert after_cancel["complaint"]["reference"] == submitted["complaint"]["reference"]
    assert new_complaint["step"] == "category"
    assert new_complaint["sessionId"] != session_id


def test_guest_complaint_appears_in_admin_and_department_officer_queue(
    client, auth, admin_token, officer_token
):
    from services.complaint_service import create_complaint
    from services import notification_service

    created = create_complaint(
        payload={
            "title": "The drinking water tap has been leaking continuously since this morning.",
            "description": "The drinking water tap has been leaking continuously since this morning.",
            "category": "Water",
            "location": {"address": "Gayatri Bhavan, Hostel Zone A"},
            "submitter": {
                "name": "Guest Reporter",
                "email": "guest.reporter@example.com",
                "mobile": "9876543210",
                "scholarId": "UNREGISTERED/2026/05",
            },
        },
        user=None,
    )
    reference = created["id"]
    notification_service.notify_admins(
        "New complaint submitted",
        f"Grievance {reference} has been registered.",
        complaint_id=reference,
    )

    admin_list = client.get(
        "/api/complaints",
        query_string={"department": "Jal Kal Vibhag", "search": reference},
        headers=auth(admin_token),
    )
    officer_list = client.get(
        "/api/complaints",
        query_string={"search": reference},
        headers=auth(officer_token),
    )

    assert admin_list.status_code == 200
    assert admin_list.get_json()["data"]["items"][0]["id"] == reference
    assert officer_list.status_code == 200
    assert officer_list.get_json()["data"]["items"][0]["id"] == reference

    admin_detail = client.get(
        f"/api/complaints/{reference}", headers=auth(admin_token)
    )
    officer_detail = client.get(
        f"/api/complaints/{reference}", headers=auth(officer_token)
    )
    assert admin_detail.status_code == 200
    assert officer_detail.status_code == 200
    assert admin_detail.get_json()["data"]["submittedBy"]["isVerified"] is False
    assert officer_detail.get_json()["data"]["submittedBy"]["email"] == "guest.reporter@example.com"

    from database import notifications
    from database import users

    admin = users().find_one({"email": "admin@dsvv.ac.in"})
    assert notifications().find_one(
        {"complaintId": reference, "recipientId": admin["id"]}
    ) is not None


def test_failed_complaint_creation_keeps_draft_for_retry(client, student_token, monkeypatch):
    from database import chatbot_sessions, complaints
    from services import complaint_service

    started = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = started["sessionId"]
    _chat_step(client, "Water", session_id=session_id, token=student_token)
    _chat_step(client, "Central Library, Ground Floor", session_id=session_id, token=student_token)
    _chat_step(
        client,
        "The drinking water tap has been leaking continuously since this morning.",
        session_id=session_id,
        token=student_token,
    )
    _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)
    _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    _chat_step(client, "Yes, details are correct", session_id=session_id, token=student_token)
    assert chatbot_sessions().find_one({"sessionId": session_id})["step"] == "confirm"

    create_complaint = complaint_service.create_complaint
    monkeypatch.setattr(
        complaint_service,
        "create_complaint",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    failed = client.post(
        "/api/chatbot/message",
        json={"message": "Submit", "sessionId": session_id, "action": "submit"},
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert failed.status_code == 500
    session = chatbot_sessions().find_one({"sessionId": session_id})
    assert session["state"] == "confirming_submission"
    assert session["draft"]["description"].startswith("The drinking water tap")
    assert complaints().count_documents({"_chatbotSessionId": session_id}) == 0

    monkeypatch.setattr(complaint_service, "create_complaint", create_complaint)
    retried = _chat_step(
        client, "Submit", session_id=session_id, token=student_token, action="submit",
        expected_status=201,
    )
    assert retried["step"] == "done"
    assert retried["complaint"]["reference"]


def test_admin_notification_failure_does_not_hide_created_reference(client, student_token, monkeypatch):
    from services import notification_service

    monkeypatch.setattr(
        notification_service,
        "notify_admins",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("notification unavailable")),
    )
    step = _chat_step(client, "Raise a complaint", token=student_token)
    session_id = step["sessionId"]
    _chat_step(client, "Water", session_id=session_id, token=student_token)
    _chat_step(client, "Central Library, Ground Floor", session_id=session_id, token=student_token)
    _chat_step(
        client,
        "The drinking water tap has been leaking continuously since this morning.",
        session_id=session_id,
        token=student_token,
    )
    _chat_step(client, "MCA/2024/018", session_id=session_id, token=student_token)
    _chat_step(client, "9876543210", session_id=session_id, token=student_token)
    _chat_step(client, "Yes, details are correct", session_id=session_id, token=student_token)

    created = _chat_step(client, "Submit", session_id=session_id, action="submit", token=student_token, expected_status=201)

    assert created["step"] == "done"
    assert created["complaint"]["reference"].startswith("DSVV-GRV-")


# ------------------------------------------------ Systematic Flow & Edge Case Tests


def test_tap_raise_complaint_starts_with_category_not_mobile(client, student_token):
    """Bug fix verification: 'Raise a complaint' starts at Category, never Mobile."""
    # Authenticated student
    res = _chat_step(client, "Raise a complaint", token=student_token)
    assert res["step"] == "category"
    assert "mobile" not in res["reply"].lower()
    assert "category" in res["reply"].lower() or "श्रेणी" in res["reply"]
    assert any("Water" in qr or "Electricity" in qr for qr in res["quickReplies"])
    assert "Cancel" in res["quickReplies"] or "रद्द करें" in res["quickReplies"]

    # Unauthenticated visitor
    unauth = _chat_step(client, "Raise a complaint")
    assert unauth["step"] == "auth_required"
    assert unauth["authRequired"] is True
    assert "Please register or log in to your account before raising a complaint." in unauth["reply"]


def test_systematic_registered_user_flow_with_step_counters(client, auth, student_token):
    """Full registered flow: Category -> Location -> Description -> Scholar ID -> Confirm Identity -> Confirm -> Submit."""
    # 1. Category
    s1 = _chat_step(client, "Raise a complaint", token=student_token)
    assert s1["step"] == "category"
    assert "[Step 1 of " in s1["reply"]

    # 2. Location
    s2 = _chat_step(client, "Electricity", session_id=s1["sessionId"], token=student_token)
    assert s2["step"] == "location"
    assert "[Step 2 of " in s2["reply"]

    # 3. Description
    s3 = _chat_step(client, "Central Library, Ground Floor", session_id=s1["sessionId"], token=student_token)
    assert s3["step"] == "description"
    assert "[Step 3 of " in s3["reply"]

    # 4. Scholar ID
    s4 = _chat_step(
        client,
        "Corridor light is flickering rapidly and making a buzzing noise.",
        session_id=s1["sessionId"],
        token=student_token,
    )
    assert s4["step"] == "scholarId"
    assert "[Step 4 of " in s4["reply"]

    # 5. Scholar ID
    s5 = _chat_step(client, "MCA/2024/018", session_id=s1["sessionId"], token=student_token)
    assert s5["step"] == "mobile"
    assert "[Step 5 of " in s5["reply"]

    # 6. Mobile (since student account has no mobile)
    s6 = _chat_step(client, "9876543210", session_id=s1["sessionId"], token=student_token)
    assert s6["step"] == "confirm_identity"
    assert "[Step 6 of " in s6["reply"]
    assert "Are these details correct?" in s6["reply"]
    assert "Yes, details are correct" in s6["quickReplies"]
    assert "Change details" in s6["quickReplies"]

    # 7. Confirm Summary
    s7 = _chat_step(client, "Yes, details are correct", session_id=s1["sessionId"], token=student_token)
    assert s7["step"] == "confirm"
    assert "Submit" in s7["quickReplies"]
    assert "Edit" in s7["quickReplies"]
    assert "Cancel" in s7["quickReplies"]
    assert "MCA/2024/018" in s7["reply"]
    assert "******3210" in s7["reply"]
    assert "9876543210" not in s7["reply"]

    # 8. Submit
    s8 = _chat_step(client, "Submit", session_id=s1["sessionId"], token=student_token, action="submit", expected_status=201)
    assert s8["step"] == "done"
    assert s8["complaint"]["id"].startswith("DSVV-GRV-")


def test_registered_user_scholar_id_mismatch_rejected(client, student_token):
    """If typed Scholar ID does not match logged-in account, reject without creating complaint."""
    s1 = _chat_step(client, "Raise a complaint", token=student_token)
    _chat_step(client, "Electricity", session_id=s1["sessionId"], token=student_token)
    _chat_step(client, "Central Library", session_id=s1["sessionId"], token=student_token)
    _chat_step(
        client,
        "Power socket on table 3 is completely dead and has scorch marks.",
        session_id=s1["sessionId"],
        token=student_token,
    )

    # Type someone else's Scholar ID
    mismatch = _chat_step(client, "MCA/2024/999", session_id=s1["sessionId"], token=student_token)
    assert mismatch["step"] == "scholarId"
    assert "does not match your signed-in account" in mismatch["reply"]
    # Draft is kept intact
    assert mismatch["draft"]["category"] == "Electricity"
    from database import complaints
    assert complaints().count_documents({"_chatbotSessionId": s1["sessionId"]}) == 0


def test_registered_user_badlein_changes_field_for_complaint_only(client, student_token):
    """'Badlein' allows updating a field for this complaint without modifying account."""
    from database import users

    s1 = _chat_step(client, "Raise a complaint", token=student_token)
    _chat_step(client, "Water", session_id=s1["sessionId"], token=student_token)
    _chat_step(client, "Academic Block C", session_id=s1["sessionId"], token=student_token)
    _chat_step(
        client,
        "Drinking water dispenser is dispensing hot water instead of normal water.",
        session_id=s1["sessionId"],
        token=student_token,
    )
    _chat_step(client, "MCA/2024/018", session_id=s1["sessionId"], token=student_token)
    _chat_step(client, "9876543210", session_id=s1["sessionId"], token=student_token)

    # Click 'Badlein' / 'Change details'
    change_choice = _chat_step(client, "Change details", session_id=s1["sessionId"], token=student_token)
    assert change_choice["step"] == "choose_identity_field"
    assert "Mobile" in change_choice["quickReplies"]

    # Choose Mobile
    ask_mob = _chat_step(client, "Mobile", session_id=s1["sessionId"], token=student_token)
    assert ask_mob["step"] == "mobile"

    # Enter new mobile
    reconfirm_step = _chat_step(client, "9123456789", session_id=s1["sessionId"], token=student_token)
    assert reconfirm_step["step"] == "confirm_identity"
    assert "6789" in reconfirm_step["reply"]

    # Confirm updated identity
    conf_step = _chat_step(client, "Yes, details are correct", session_id=s1["sessionId"], token=student_token)
    assert conf_step["step"] == "confirm"
    assert "6789" in conf_step["reply"]

    # Submit
    done = _chat_step(client, "Submit", session_id=s1["sessionId"], token=student_token, action="submit", expected_status=201)
    assert done["step"] == "done"

    # Verify user account in DB does not get modified with this complaint's mobile
    user_doc = users().find_one({"id": "USR-1001"})
    assert user_doc.get("mobile") != "9123456789"


def test_systematic_guest_flow_complete_sequence(client, student_token):
    """Guest flow: unauthenticated rejected, then completes complaint flow upon login."""
    s1 = _chat_step(client, "Raise a complaint")
    assert s1["step"] == "auth_required"
    assert s1["authRequired"] is True
    assert s1["action"]["href"] == "/login.html"

    from database import complaints
    assert complaints().count_documents({"_chatbotSessionId": s1["sessionId"]}) == 0

    # Once authenticated with valid token, user completes the complaint flow
    token = student_token
    s2 = _chat_step(client, "Raise a complaint", session_id=s1["sessionId"], token=token)
    assert s2["step"] == "category"

    s3 = _chat_step(client, "Water", session_id=s1["sessionId"], token=token)
    assert s3["step"] == "location"

    s4 = _chat_step(client, "Gayatri Bhavan, Room 101", session_id=s1["sessionId"], token=token)
    assert s4["step"] == "description"

    s5 = _chat_step(
        client,
        "Water tap is constantly dripping and splashing all over the floor.",
        session_id=s1["sessionId"],
        token=token,
    )
    assert s5["step"] == "scholarId"

    s6 = _chat_step(client, "MCA/2024/018", session_id=s1["sessionId"], token=token)
    assert s6["step"] == "mobile"

    s7 = _chat_step(client, "9876543210", session_id=s1["sessionId"], token=token)
    assert s7["step"] == "confirm_identity"

    s8 = _chat_step(client, "Yes, details are correct", session_id=s1["sessionId"], token=token)
    assert s8["step"] == "confirm"
    assert "MCA/2024/018" in s8["reply"]
    assert "******3210" in s8["reply"]
    assert "9876543210" not in s8["reply"]

    done = _chat_step(client, "Submit", session_id=s1["sessionId"], token=token, action="submit", expected_status=201)
    assert done["step"] == "done"
    assert done["complaint"]["id"].startswith("DSVV-GRV-")
    saved = complaints().find_one({"id": done["complaint"]["id"]})
    assert saved["submittedBy"]["type"] == "registered"
    assert saved["submittedBy"]["id"] == "USR-1001"


def test_chip_label_or_command_not_validated_as_free_text_answer(client, student_token):
    """Guard: sending chip labels or commands at a free-text step does not count as answer."""
    token = student_token
    s1 = _chat_step(client, "Raise a complaint", token=token)
    _chat_step(client, "Water", session_id=s1["sessionId"], token=token)
    _chat_step(client, "Gayatri Bhavan, Room 101", session_id=s1["sessionId"], token=token)
    _chat_step(
        client,
        "Water tap is constantly dripping and splashing all over the floor.",
        session_id=s1["sessionId"],
        token=token,
    )
    _chat_step(client, "MCA/2024/018", session_id=s1["sessionId"], token=token)

    # Send a command word at mobile step
    guard_res = _chat_step(client, "Help & FAQs", session_id=s1["sessionId"], token=token)
    assert guard_res["step"] == "mobile"
    assert "requested information" in guard_res["reply"]
    # Draft mobile is NOT set to 'Help & FAQs'
    assert "mobile" not in guard_res["draft"]


def test_active_flow_restart_prompt_continue_and_start_new(client, student_token):
    """If 'Raise a complaint' is sent mid-flow, ask 'Continue' or 'Start new'."""
    token = student_token
    s1 = _chat_step(client, "Raise a complaint", token=token)
    _chat_step(client, "Water", session_id=s1["sessionId"], token=token)
    _chat_step(client, "Gayatri Bhavan, Room 101", session_id=s1["sessionId"], token=token)

    # User taps "Raise a complaint" again while at description step
    prompt_restart = _chat_step(client, "Raise a complaint", session_id=s1["sessionId"], token=token)
    assert prompt_restart["step"] == "confirm_restart"
    assert "Continue" in prompt_restart["quickReplies"]
    assert "Start new" in prompt_restart["quickReplies"]

    # Case 1: Continue
    continued = _chat_step(client, "Continue", session_id=s1["sessionId"], token=token)
    assert continued["step"] == "description"
    assert continued["draft"]["category"] == "Water"

    # Mid-flow again: choose 'Start new'
    _chat_step(client, "Raise a complaint", session_id=s1["sessionId"], token=token)
    restarted = _chat_step(client, "Start new", session_id=s1["sessionId"], token=token)
    assert restarted["step"] == "category"
    assert not restarted["draft"].get("category")


def test_three_invalid_attempts_offers_help_and_back_works(client, student_token):
    """After 3 invalid attempts, bot offers Help & Cancel; Back returns to previous question."""
    token = student_token
    s1 = _chat_step(client, "Raise a complaint", token=token)
    _chat_step(client, "Water", session_id=s1["sessionId"], token=token)
    _chat_step(client, "Gayatri Bhavan, Room 101", session_id=s1["sessionId"], token=token)
    _chat_step(
        client,
        "Water tap is constantly dripping and splashing all over the floor.",
        session_id=s1["sessionId"],
        token=token,
    )
    _chat_step(client, "MCA/2024/018", session_id=s1["sessionId"], token=token)

    # Invalid mobile attempt 1
    inv1 = _chat_step(client, "123", session_id=s1["sessionId"], token=token)
    assert inv1["step"] == "mobile"

    # Invalid mobile attempt 2
    inv2 = _chat_step(client, "invalid-num", session_id=s1["sessionId"], token=token)
    assert inv2["step"] == "mobile"

    # Invalid mobile attempt 3 -> triggers Help & Cancel
    inv3 = _chat_step(client, "0000", session_id=s1["sessionId"], token=token)
    assert inv3["step"] == "mobile"
    assert "Help" in inv3["quickReplies"]
    assert "Cancel" in inv3["quickReplies"]
    assert "Back" in inv3["quickReplies"]
    assert "trouble" in inv3["reply"].lower() or "help" in inv3["reply"].lower()

    # Click Back -> goes back to Scholar ID step
    backed = _chat_step(client, "Back", session_id=s1["sessionId"], token=token, action="back")
    assert backed["step"] == "scholarId"


def test_faq_interrupt_mid_flow_preserves_draft_and_resumes(client, student_token):
    """FAQ asked during slot collection is answered in one message and pending question repeated."""
    token = student_token
    s1 = _chat_step(client, "Raise a complaint", token=token)
    _chat_step(client, "Water", session_id=s1["sessionId"], token=token)
    _chat_step(client, "Gayatri Bhavan, Room 101", session_id=s1["sessionId"], token=token)

    # Mid-flow FAQ question
    faq_interruption = _chat_step(client, "How do I upload a photo?", session_id=s1["sessionId"], token=token)
    assert faq_interruption["step"] == "description"
    assert "Photo" in faq_interruption["reply"]
    assert "Returning to your complaint" in faq_interruption["reply"]
    assert faq_interruption["draft"]["category"] == "Water"


def test_language_purity_hindi_hinglish_english(client, student_token):
    """Pure Hindi, Hinglish, or English without mixing languages in replies."""
    token = student_token
    # Hindi
    hi_step = _chat_step(client, "शिकायत दर्ज करें", token=token)
    assert hi_step["step"] == "category"
    assert any("\u0900" <= c <= "\u097f" for c in hi_step["reply"])
    assert "रद्द करें" in hi_step["quickReplies"]

    # Hinglish
    hing_step = _chat_step(client, "shikayat darj karo", token=token)
    assert hing_step["step"] == "category"
    assert not any("\u0900" <= c <= "\u097f" for c in hing_step["reply"])
    assert "Cancel" in hing_step["quickReplies"]

    # English
    en_step = _chat_step(client, "Raise a complaint", token=token)
    assert en_step["step"] == "category"
    assert not any("\u0900" <= c <= "\u097f" for c in en_step["reply"])
    assert "Cancel" in en_step["quickReplies"]


# ------------------------------------------------ Session Identity Memory & Second Complaint Tests


def test_guest_second_complaint_same_session_uses_stored_identity(client, student_token):
    """Replay exact chat: Water complaint as student with MCA/2024/018, then 'Raise another complaint'
    with Computer/Lab, MCA Lab, L425 -> bot asks only single 'Wahi details use karein?' confirmation,
    then summary, then submit creates separate complaint.
    """
    from database import complaints

    # Complaint 1: Water issue as student
    token = student_token
    s1 = _chat_step(client, "Raise a complaint", token=token)
    sess_id = s1["sessionId"]
    _chat_step(client, "Water", session_id=sess_id, token=token)
    _chat_step(client, "Central Library, Ground Floor", session_id=sess_id, token=token)
    _chat_step(
        client,
        "Drinking water tap is leaking continuously near the main entrance.",
        session_id=sess_id,
        token=token,
    )
    _chat_step(client, "MCA/2024/018", session_id=sess_id, token=token)
    _chat_step(client, "9876543210", session_id=sess_id, token=token)
    _chat_step(client, "Yes, details are correct", session_id=sess_id, token=token)
    c1_summary = _chat_step(client, "Submit", session_id=sess_id, token=token, action="submit", expected_status=201)
    assert c1_summary["step"] == "done"
    ref1 = c1_summary["complaint"]["reference"]
    assert ref1.startswith("DSVV-GRV-")

    # Complaint 2: Raise another complaint in the same session
    s2 = _chat_step(client, "Raise another complaint", session_id=sess_id, token=token, action="new")
    assert s2["sessionId"] != sess_id
    sess_id_2 = s2["sessionId"]
    assert s2["step"] == "category"

    s2_lab = _chat_step(client, "Computer/Lab", session_id=sess_id_2, token=token)
    assert s2_lab["step"] == "lab"

    s2_sys = _chat_step(client, "MCA Lab", session_id=sess_id_2, token=token)
    assert s2_sys["step"] == "systemNumber"

    s2_desc = _chat_step(client, "L425", session_id=sess_id_2, token=token)
    assert s2_desc["step"] == "description"

    s2_conf_id = _chat_step(
        client,
        "Monitor screen is completely blank and power led blinks amber.",
        session_id=sess_id_2,
        token=token,
    )
    # Expected: only the confirmation "Wahi details use karein?"
    assert s2_conf_id["step"] == "confirm_stored_identity"
    assert "Wahi details use karein?" in s2_conf_id["reply"]
    # Mobile number is masked (only last 4 digits visible)
    assert "******3210" in s2_conf_id["reply"]
    assert "9876543210" not in s2_conf_id["reply"]
    assert "MCA/2024/018" in s2_conf_id["reply"]
    assert "Haan" in s2_conf_id["quickReplies"]
    assert "Badlein" in s2_conf_id["quickReplies"]

    # Tap "Haan" -> goes straight to summary
    s2_summary = _chat_step(client, "Haan", session_id=sess_id_2, token=token, action="yes")
    assert s2_summary["step"] == "confirm"
    assert "MCA Lab" in s2_summary["reply"]
    assert "L425" in s2_summary["reply"]
    assert "MCA/2024/018" in s2_summary["reply"]

    # Submit complaint 2 with token
    c2_done = _chat_step(client, "Submit", session_id=sess_id_2, token=token, action="submit", expected_status=201)
    assert c2_done["step"] == "done"
    ref2 = c2_done["complaint"]["reference"]
    assert ref2.startswith("DSVV-GRV-")
    assert ref1 != ref2

    doc1 = complaints().find_one({"id": ref1})
    doc2 = complaints().find_one({"id": ref2})
    assert doc1 is not None and doc2 is not None
    assert doc1["submittedBy"]["id"] == "USR-1001"
    assert doc2["submittedBy"]["id"] == "USR-1001"
    assert doc2["lab"] == "MCA Lab"
    assert doc2["systemNumber"] == "L425"


def test_guest_badlein_at_stored_identity_confirmation_changes_field(client, student_token):
    """'Badlein' at the stored identity confirmation lets user correct one field for complaint 2."""
    token = student_token
    s1 = _chat_step(client, "Raise a complaint", token=token)
    sess_id = s1["sessionId"]
    _chat_step(client, "Water", session_id=sess_id, token=token)
    _chat_step(client, "Academic Block B", session_id=sess_id, token=token)
    _chat_step(client, "Water cooler is dispensing muddy water since yesterday afternoon.", session_id=sess_id, token=token)
    _chat_step(client, "MCA/2024/018", session_id=sess_id, token=token)
    _chat_step(client, "9876543210", session_id=sess_id, token=token)
    _chat_step(client, "Yes, details are correct", session_id=sess_id, token=token)
    _chat_step(client, "Submit", session_id=sess_id, token=token, action="submit", expected_status=201)

    # Complaint 2
    s2 = _chat_step(client, "Raise another complaint", session_id=sess_id, token=token, action="new")
    sess_id_2 = s2["sessionId"]
    _chat_step(client, "Electricity", session_id=sess_id_2, token=token)
    _chat_step(client, "Room 301", session_id=sess_id_2, token=token)
    conf = _chat_step(client, "Ceiling fan is sparking and making a loud grinding screech.", session_id=sess_id_2, token=token)
    assert conf["step"] == "confirm_stored_identity"

    # Tap "Badlein"
    choose = _chat_step(client, "Badlein", session_id=sess_id_2, token=token, action="edit")
    assert choose["step"] == "choose_identity_field"
    assert "Mobile" in choose["quickReplies"]

    # Change Mobile
    ask_mob = _chat_step(client, "Mobile", session_id=sess_id_2, token=token)
    assert ask_mob["step"] == "mobile"

    # Provide new mobile
    summary = _chat_step(client, "9111222333", session_id=sess_id_2, token=token)
    assert summary["step"] == "confirm"
    assert "******2333" in summary["reply"]
    assert "9111222333" not in summary["reply"]

    # Submit complaint 2 with new mobile and token
    done = _chat_step(client, "Submit", session_id=sess_id_2, token=token, action="submit", expected_status=201)
    assert done["step"] == "done"
    ref = done["complaint"]["reference"]

    from database import complaints
    doc = complaints().find_one({"id": ref})
    assert doc["submittedBy"]["mobile"] == "9111222333"


def test_new_session_same_scholar_id_asks_all_details_without_prefill(client, student_token):
    """In a new chat, never prefill personal details from earlier complaints. Always ask again."""
    token = student_token
    # Session 1
    s1 = _chat_step(client, "Raise a complaint", token=token)
    _chat_step(client, "Water", session_id=s1["sessionId"], token=token)
    _chat_step(client, "Hostel 1", session_id=s1["sessionId"], token=token)
    _chat_step(client, "Pipeline leakage outside room 101 has flooded the corridor.", session_id=s1["sessionId"], token=token)
    _chat_step(client, "MCA/2024/018", session_id=s1["sessionId"], token=token)
    _chat_step(client, "9876543210", session_id=s1["sessionId"], token=token)
    _chat_step(client, "Yes, details are correct", session_id=s1["sessionId"], token=token)
    _chat_step(client, "Submit", session_id=s1["sessionId"], token=token, action="submit", expected_status=201)

    # Completely NEW session (no sessionId passed)
    new_s = _chat_step(client, "Raise a complaint", token=token)
    assert new_s["sessionId"] != s1["sessionId"]

    _chat_step(client, "Electricity", session_id=new_s["sessionId"], token=token)
    _chat_step(client, "Hostel 2", session_id=new_s["sessionId"], token=token)
    _chat_step(client, "Main switch board is completely dead with burning smell.", session_id=new_s["sessionId"], token=token)

    # Provide same Scholar ID in new session
    ask_id = _chat_step(client, "MCA/2024/018", session_id=new_s["sessionId"], token=token)
    # MUST ask contact details from scratch!
    assert ask_id["step"] == "mobile"
    assert "Wahi details use karein?" not in ask_id["reply"]


def test_done_clears_stored_identity(client, student_token):
    """Tapping 'Done' clears the stored identity from the session."""
    from database import chatbot_sessions

    token = student_token
    s1 = _chat_step(client, "Raise a complaint", token=token)
    sess_id = s1["sessionId"]
    _chat_step(client, "Water", session_id=sess_id, token=token)
    _chat_step(client, "Hostel 1", session_id=sess_id, token=token)
    _chat_step(client, "Pipeline leakage outside room 101 has flooded the corridor.", session_id=sess_id, token=token)
    _chat_step(client, "MCA/2024/018", session_id=sess_id, token=token)
    _chat_step(client, "9876543210", session_id=sess_id, token=token)
    _chat_step(client, "Yes, details are correct", session_id=sess_id, token=token)
    _chat_step(client, "Submit", session_id=sess_id, token=token, action="submit", expected_status=201)

    # Verify stored_identity is present before Done
    session_doc = chatbot_sessions().find_one({"sessionId": sess_id})
    assert session_doc.get("stored_identity") is not None

    # Tap "Done"
    done_res = _chat_step(client, "Done", session_id=sess_id, token=token, action="done")
    assert done_res["step"] == "idle"

    # Verify stored_identity is cleared
    session_doc_after = chatbot_sessions().find_one({"sessionId": sess_id})
    assert session_doc_after.get("stored_identity") is None


def test_fresh_chat_raise_complaint_on_completed_session_does_not_prefill(client, student_token):
    """Clicking 'Raise a complaint' on a finished session starts fresh without stored identity."""
    token = student_token
    s1 = _chat_step(client, "Raise a complaint", token=token)
    sess_id = s1["sessionId"]
    _chat_step(client, "Water", session_id=sess_id, token=token)
    _chat_step(client, "Hostel 1", session_id=sess_id, token=token)
    _chat_step(client, "Pipeline leakage outside room 101 has flooded the corridor.", session_id=sess_id, token=token)
    _chat_step(client, "MCA/2024/018", session_id=sess_id, token=token)
    _chat_step(client, "9876543210", session_id=sess_id, token=token)
    _chat_step(client, "Yes, details are correct", session_id=sess_id, token=token)
    c1 = _chat_step(client, "Submit", session_id=sess_id, token=token, action="submit", expected_status=201)
    assert c1["step"] == "done"

    # User starts a fresh complaint using 'Raise a complaint' starter
    fresh = _chat_step(client, "Raise a complaint", session_id=sess_id, token=token, action="raise_complaint")
    assert fresh["sessionId"] != sess_id
    fresh_sess = fresh["sessionId"]
    assert fresh["step"] == "category"

    _chat_step(client, "Electricity", session_id=fresh_sess, token=token)
    _chat_step(client, "Academic Block A, Floor 2", session_id=fresh_sess, token=token)
    step4 = _chat_step(
        client,
        "Switchboard is burnt and producing smoke continuously.",
        session_id=fresh_sess,
        token=token,
    )
    # MUST ask for Scholar ID, NOT 'Wahi details use karein?'
    assert step4["step"] == "scholarId"
    assert "Wahi details use karein?" not in step4["reply"]


def test_step_progress_counter_never_changes_after_category_selection(client, student_token):
    """Total steps in [Step X of Y] never changes after category selection, and confirm is [Step Y of Y]."""
    import re

    pattern = re.compile(r"\[(?:Step|चरण)\s*(\d+)(?:\s*of\s*|/)(\d+)\]")
    token = student_token

    # Flow 1: Water (General campus category)
    s1 = _chat_step(client, "Raise a complaint", token=token)
    m1 = pattern.search(s1["reply"])
    assert m1 is not None

    s2 = _chat_step(client, "Water", session_id=s1["sessionId"], token=token)
    m2 = pattern.search(s2["reply"])
    assert m2 is not None
    total_expected = int(m2.group(2))

    s3 = _chat_step(client, "Academic Block A", session_id=s1["sessionId"], token=token)
    m3 = pattern.search(s3["reply"])
    assert m3 is not None
    assert int(m3.group(2)) == total_expected
    assert int(m3.group(1)) == 3

    s4 = _chat_step(
        client,
        "Water cooler pipe is broken and water is overflowing continuously.",
        session_id=s1["sessionId"],
        token=token,
    )
    m4 = pattern.search(s4["reply"])
    assert m4 is not None
    assert int(m4.group(2)) == total_expected
    assert int(m4.group(1)) == 4

    s5 = _chat_step(client, "MCA/2024/018", session_id=s1["sessionId"], token=token)
    m5 = pattern.search(s5["reply"])
    assert m5 is not None
    assert int(m5.group(2)) == total_expected
    assert int(m5.group(1)) == 5

    s6 = _chat_step(client, "9876543210", session_id=s1["sessionId"], token=token)
    m6 = pattern.search(s6["reply"])
    assert m6 is not None
    assert int(m6.group(2)) == total_expected
    assert int(m6.group(1)) == 6

    s7 = _chat_step(client, "Yes, details are correct", session_id=s1["sessionId"], token=token)
    m7 = pattern.search(s7["reply"])
    assert m7 is not None
    assert int(m7.group(2)) == total_expected
    # Confirm step is ALWAYS [Step Y of Y]
    assert int(m7.group(1)) == total_expected
    assert s7["step"] == "confirm"

    # Flow 2: Computer/Lab (expands to lab and systemNumber)
    c1 = _chat_step(client, "Raise a complaint", token=token)
    c2 = _chat_step(client, "Computer/Lab", session_id=c1["sessionId"], token=token)
    mc2 = pattern.search(c2["reply"])
    assert mc2 is not None
    lab_total = int(mc2.group(2))

    c3 = _chat_step(client, "MCA Lab", session_id=c1["sessionId"], token=token)
    mc3 = pattern.search(c3["reply"])
    assert mc3 is not None
    assert int(mc3.group(2)) == lab_total
    assert int(mc3.group(1)) == 3

    c4 = _chat_step(client, "Workstation 12", session_id=c1["sessionId"], token=token)
    mc4 = pattern.search(c4["reply"])
    assert mc4 is not None
    assert int(mc4.group(2)) == lab_total
    assert int(mc4.group(1)) == 4

    c5 = _chat_step(
        client,
        "System boots to recovery screen and keyboard is completely unresponsive.",
        session_id=c1["sessionId"],
        token=token,
    )
    mc5 = pattern.search(c5["reply"])
    assert mc5 is not None
    assert int(mc5.group(2)) == lab_total
    assert int(mc5.group(1)) == 5

    c6 = _chat_step(client, "MCA/2024/018", session_id=c1["sessionId"], token=token)
    mc6 = pattern.search(c6["reply"])
    assert mc6 is not None
    assert int(mc6.group(2)) == lab_total
    assert int(mc6.group(1)) == 6

    c7 = _chat_step(client, "9876543210", session_id=c1["sessionId"], token=token)
    mc7 = pattern.search(c7["reply"])
    assert mc7 is not None
    assert int(mc7.group(2)) == lab_total
    assert int(mc7.group(1)) == 7

    c8 = _chat_step(client, "Yes, details are correct", session_id=c1["sessionId"], token=token)
    mc8 = pattern.search(c8["reply"])
    assert mc8 is not None
    assert int(mc8.group(2)) == lab_total
    # Confirm step is ALWAYS [Step Y of Y]
    assert int(mc8.group(1)) == lab_total
    assert c8["step"] == "confirm"
