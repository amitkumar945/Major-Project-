"""Public FAQ and conversational complaint filing assistant."""

import json

from flask import Blueprint, current_app, request

from services import chatbot_service
from utils.jwt_utils import current_user, optional_jwt
from utils.rate_limit import rate_limit
from utils.responses import error, success, validation_error

bp = Blueprint("chatbot", __name__, url_prefix="/api/chatbot")


@bp.post("/message")
@optional_jwt
@rate_limit("chatbot")
def message():
    max_request_bytes = current_app.config.get("CHATBOT_MAX_REQUEST_BYTES", 8192)
    if request.content_length is not None and request.content_length > max_request_bytes:
        return error("The chat request is too large.", 413)

    raw_body = request.stream.read(max_request_bytes + 1)
    if len(raw_body) > max_request_bytes:
        return error("The chat request is too large.", 413)

    try:
        values = json.loads(raw_body) if request.is_json else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        values = {}
    values = values or {}
    if not isinstance(values, dict):
        return validation_error({"message": "Send a JSON object containing your question."})
    text = values.get("message")
    if not isinstance(text, str) or not text.strip():
        return validation_error({"message": "Enter a question for the assistant."})
    if len(text) > 1200:
        return validation_error({"message": "Keep your question under 1,200 characters."})

    session_id = values.get("sessionId")
    if session_id is not None and (
        not isinstance(session_id, str) or len(session_id) > 64
    ):
        return validation_error({"sessionId": "Invalid chat session."})
    action = values.get("action")
    if action is not None and (not isinstance(action, str) or len(action) > 40):
        return validation_error({"action": "Invalid chat action."})

    client_ip = (request.remote_addr or "unknown")[:64]

    result = chatbot_service.handle_chat_message(
        text=text.strip(),
        session_id=session_id,
        user=current_user(),
        action=action,
        config=current_app.config,
        client_ip=client_ip,
    )
    return success(result, status=201 if result.get("created") else 200)
