"""Grounded help, conversational state machine, and complaint submission assistant."""

import hashlib
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from ai import priority as priority_module
from constants import (
    CATEGORIES,
    CATEGORY_DEPARTMENT_MAP,
    DEPARTMENTS,
    ROLE_OFFICER,
    ROLE_STUDENT,
)
from database import chatbot_sessions, complaints, users
from openai import APIError, OpenAI
from pymongo.errors import DuplicateKeyError
from services import ai_service, complaint_service, notification_service
from utils import rate_limit
from utils.helpers import iso, parse_iso, utcnow
from utils.responses import ApiException
from utils.validators import is_email, is_mobile

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\s().-]*){8,15}(?!\w)")
_SECRET = re.compile(
    r"(?i)\b(?:password|passcode|otp|one.time.password|token|jwt)"
    r"(?:\s+(?:is|equals)\s*|\s*[:=]\s*|\s+)[^\s,;.!?]+"
)
_REFERENCE = re.compile(r"\b[A-Z]{2,6}-GRV-\d{4}-\d{4,6}\b", re.I)
_SCHOLAR_ID = re.compile(
    r"\b(?:GUEST/)?\d{4}/\d{2,}(?:/\d{2,})?\b|\bUSR-\d{3,}\b",
    re.I,
)
_DEVANAGARI = re.compile(r"[\u0900-\u097f]")
_WORD = re.compile(r"[a-z]+", re.I)
_HINGLISH_MARKERS = {
    "ab", "apni", "batao", "btao", "bataiye", "chahiye", "ka", "kar",
    "kaise", "karo", "karu", "karun", "kya", "ki", "maine", "meri",
    "mujhe", "pani", "paani", "panee", "bijli", "bijlee", "shikayat", "shikaayat",
    "shikayt", "stithi", "sthiti", "hai", "hain", "iska", "uska",
    "haan", "han", "ha", "theek", "sahi", "badlein", "badal", "jaari", "naya",
}
_SUBMISSION_CONFIRMATIONS = {
    "submit", "submit complaint", "yes", "yes submit", "haan", "han", "ha",
    "haan submit", "ji haan", "ji haan submit", "darj kare", "darj karo",
    "दर्ज करें", "दर्ज कर दें", "हाँ", "हां", "जी हाँ", "जी हां", "हाँ जमा करें",
}

SESSION_TTL_MINUTES = 30
ALLOWED_CATEGORIES = list(CATEGORIES)
ALLOWED_LABS = ["BCA Lab", "BIT Lab", "MCA Lab"]
CANONICAL_LOCATIONS = [
    "Gayatri Bhavan, Hostel Zone A",
    "Academic Block C, Second Floor",
    "Shantikunj Bhavan, Computer Lab Wing",
    "Central Library, Ground Floor",
    "Annapurna Bhavan, Dining Hall",
]

STATE_IDLE = "idle"
STATE_CONFIRMING_FAST_PATH = "confirming_fast_path"
STATE_COLLECTING = "collecting"
STATE_CONFIRMING_SUBMISSION = "confirming_submission"
STATE_SUBMITTING = "submitting"
STATE_EDITING = "editing"
STATE_COMPLETED = "completed"
STATE_CONFIRMING_RESTART = "confirming_restart"

DEPT_TO_CATEGORY = {
    "MCA Lab / Computer Lab": "Computer/Lab",
    "Jal Kal Vibhag": "Water",
    "Vidyut Vibhag": "Electricity",
    "Nirman Vibhag": "Building",
}
CATEGORY_ALIASES = {
    "Water": ("pani", "paani", "panee", "जल", "पानी", "water"),
    "Electricity": ("bijli", "bijlee", "bijalee", "बिजली", "विद्युत", "electricity", "power", "light"),
    "Building": ("nirman", "भवन", "निर्माण", "building"),
    "Computer/Lab": ("computer lab", "कंप्यूटर लैब", "कंप्यूटर", "computer/lab", "computer", "lab"),
    "Hostel": ("hostel", "छात्रावास", "hostel zone"),
    "Classroom": ("classroom", "कक्षा", "class room"),
    "Other": ("other", "अन्य"),
}

COMMAND_AND_CHIP_LABELS = {
    "raise a complaint", "raise complaint", "new complaint", "file a complaint",
    "lodge complaint", "शिकायत दर्ज करें", "नई शिकायत दर्ज", "shikayat darj karein",
    "shikayat darj karo", "complaint darj karo", "mujhe complaint register karni hai",
    "i want to register a complaint",
    "how do i register a grievance?", "how do i register a grievance",
    "which department handles water leakage?", "which department handles water leakage",
    "how do i upload a photo?", "how do i upload a photo",
    "how can i track my complaint?", "how can i track my complaint",
    "track a complaint", "help & faqs", "help", "cancel", "back", "पीछे", "रद्द करें",
    "continue", "start new", "जारी रखें", "नई शुरू करें",
    "haan, sahi hai", "yes, details are correct", "badlein", "change details",
}


def is_chip_or_command(text: str) -> bool:
    return (text or "").strip().lower() in COMMAND_AND_CHIP_LABELS


def complaint_reference(text: str) -> str:
    match = _REFERENCE.search(text or "")
    return match.group(0).upper() if match else ""


def _ai_safe_text(text: str) -> str:
    """Strip common identifiers and secrets before sending text to a provider."""
    cleaned = _SECRET.sub("[redacted]", text or "")
    cleaned = _EMAIL.sub("[email redacted]", cleaned)
    cleaned = _PHONE.sub("[number redacted]", cleaned)
    cleaned = _REFERENCE.sub("[complaint reference redacted]", cleaned)
    cleaned = _SCHOLAR_ID.sub("[student ID redacted]", cleaned)
    return cleaned[:1200]


def _language_style(text: str, preferred: str = "en") -> str:
    """Choose a response style from the current message, retaining context for short follow-ups."""
    if _DEVANAGARI.search(text or ""):
        return "hi"
    words = {word.lower() for word in _WORD.findall(text or "")}
    if words & _HINGLISH_MARKERS:
        return "hinglish"
    if len(words) <= 4 and preferred in {"hi", "hinglish"}:
        return preferred
    return "en"


def _status_intent(text: str) -> bool:
    q = (text or "").lower()
    words = {word.lower() for word in _WORD.findall(q)}
    return bool(
        words & {"status", "stetus", "statas", "track", "timeline", "stithi", "sthiti"}
        or _DEVANAGARI.search(q)
        and any(term in q for term in ("स्थिति", "स्थित", "ट्रैक", "स्टेटस"))
        or "where is" in q
        or "how do i track" in q
    )


def _how_to_question(text: str) -> bool:
    q = (text or "").strip().lower()
    return (
        "?" in q
        or q.startswith(("how ", "what ", "which ", "where ", "can i ", "could i ", "kya ", "kaise "))
        or " kaise " in q
        or "कैसे" in q
        or any(m in q for m in ("upload", "photo", "register a grievance", "water leakage", "track my"))
    )


def _fallback(text: str, language: str = None) -> str:
    q = (text or "").lower()
    style = language or _language_style(text)
    words = {word.lower() for word in _WORD.findall(q)}
    if style == "hi":
        if any(word in q for word in ("पानी", "जल", "नल", "leak", "water")):
            return "पानी की सप्लाई, पाइपलाइन, RO या लीकेज की शिकायत के लिए Jal Kal Vibhag चुनें। /student/new-complaint.html पर शिकायत दर्ज करें और Water category चुनें।"
        if any(word in q for word in ("बिजली", "विद्युत", "electric", "light", "fan", "power")):
            return "बिजली, वायरिंग, पंखे या लाइट की शिकायत के लिए Vidyut Vibhag चुनें। /student/new-complaint.html पर शिकायत दर्ज करें और Electricity category चुनें।"
        if any(word in q for word in ("निर्माण", "भवन", "रखरखाव", "building", "maintenance", "repair")):
            return "भवन, फर्नीचर या कैंपस मरम्मत की शिकायत के लिए Nirman Vibhag चुनें। /student/new-complaint.html पर शिकायत दर्ज करें और सही category चुनें।"
        if any(word in q for word in ("कंप्यूटर", "लैब", "computer", "lab", "system", "printer")):
            return "कंप्यूटर या लैब की शिकायत MCA Lab / Computer Lab को भेजी जाती है। फॉर्म में Computer/Lab चुनें, फिर BCA Lab, BIT Lab या MCA Lab और system number भरें।"
        if any(word in q for word in ("दर्ज", "पंजीकरण")) or "complaint" in words and any(word in words for word in ("register", "file", "submit")):
            return "शिकायत दर्ज करने के लिए /student/new-complaint.html खोलें। अपनी समस्या, category और स्थान भरें, जानकारी जाँचें और Submit करें। शिकायत दर्ज होने पर reference number मिलेगा।"
        if _status_intent(q):
            return "अपनी शिकायत की स्थिति देखने के लिए उसका reference number भेजें। निजी जानकारी दिखाने से पहले आपको लॉग इन करना होगा। आप /track.html पर भी reference number से status देख सकते हैं।"
        if any(word in q for word in ("फोटो", "दस्तावेज", "upload", "photo", "attachment")):
            return "शिकायत फॉर्म के Photo step पर सबूत के तौर पर फोटो या दस्तावेज जोड़ सकते हैं। यह वैकल्पिक है; एक अनुरोध में अधिकतम 5 फाइलें (हर एक 5 MB तक) जोड़ें।"
        if any(word in q for word in ("प्राथमिकता", "urgent", "priority")):
            return "शिकायत की priority Low, Medium, High या Urgent हो सकती है। इसे सिस्टम निर्धारित करता है; assistant इसे बदल नहीं सकता।"
        if any(word in q for word in ("लॉगिन", "पासवर्ड", "otp", "password", "login")):
            return "लॉगिन या OTP में समस्या हो तो पेज पर दिए निर्देश देखें। पासवर्ड बदलने के लिए /forgot-password.html खोलें। अपना password या OTP chat में साझा न करें।"
        return "मैं शिकायत दर्ज करने, विभाग चुनने, status देखने, फाइल जोड़ने और escalation के बारे में मदद कर सकता हूँ। निजी शिकायत की जानकारी के लिए लॉग इन करें और reference number दें।"

    if style == "hinglish":
        if any(word in q for word in ("pani", "paani", "panee", "nal", "water", "leak", "जल", "पानी")):
            return "Water supply, plumbing ya leakage ki complaint Jal Kal Vibhag ko jaati hai. /student/new-complaint.html par form kholkar Water category choose karein."
        if any(word in q for word in ("bijli", "bijlee", "bijalee", "electric", "light", "fan", "power", "बिजली")):
            return "Electricity, wiring, fan ya light ki complaint Vidyut Vibhag ko jaati hai. Form mein Electricity category choose karein."
        if any(word in q for word in ("building", "maintenance", "repair", "nirman", "भवन")):
            return "Building ya campus maintenance ki complaint Nirman Vibhag ko jaati hai. Form mein Building category choose karke details submit karein."
        if any(word in q for word in ("computer", "lab", "system", "printer", "कंप्यूटर")):
            return "Computer aur lab issues MCA Lab / Computer Lab ko route hote hain. Form mein Computer/Lab choose karein, phir lab aur system number bharein."
        if any(word in q for word in ("photo", "upload", "attachment", "file")):
            return "Complaint form ke Photo step par aap optional evidence upload kar sakte hain: maximum 5 files, har file 5 MB tak."
        if _status_intent(q):
            return "Apni complaint ka status check karne ke liye reference number bhejiye. Private details dekhne se pehle sign in zaroori hai. Aap /track.html par bhi reference number se check kar sakte hain."
        if "maine" in words and "register" in words:
            return "Agar aap complaint register kar chuke hain, uska reference number bhejiye. Main status sirf verified record se check kar sakta hoon."
        if any(word in q for word in ("register", "file", "submit", "darj", "shikayat", "शिकायत")):
            return "Complaint register karne ke liye /student/new-complaint.html kholiye. Problem, category aur location bhariye, details review karke Submit karein. Register hone par reference number milega."
        if any(word in q for word in ("password", "login", "otp")):
            return "Login ya OTP issue ke liye page par diye steps follow karein. Password reset ke liye /forgot-password.html use karein. Password ya OTP chat mein share na karein."
        return "Main complaint register karne, department choose karne, status check karne aur escalation mein help kar sakta hoon. Private status ke liye sign in karke reference number bhejiye."

    if any(word in q for word in ("water", "leak", "tap", "pani", "paani", "nal", "पानी", "जल", "leakage")):
        return "Water supply, plumbing, RO, drainage, or sanitation complaints go to Jal Kal Vibhag. Register at /student/new-complaint.html and choose Water; the portal routes the department."
    if any(word in q for word in ("electric", "power", "light", "fan", "bijli", "current", "बिजली", "विद्युत")):
        return "Power, wiring, fan, or lighting issues go to Vidyut Vibhag. Register at /student/new-complaint.html and choose Electricity."
    if any(word in q for word in ("building", "maintenance", "furniture", "repair", "marammat", "deewar", "diwar", "nirman", "निर्माण", "भवन")):
        return "Building, furniture, and campus maintenance issues go to Nirman Vibhag. Register at /student/new-complaint.html and choose Building (or the matching category)."
    if any(word in q for word in ("computer", "lab", "system number", "printer", "wifi", "computer/lab")):
        return "Computer and lab issues route to MCA Lab / Computer Lab. In the form, choose Computer/Lab, select BCA Lab, BIT Lab, or MCA Lab, and enter the affected computer's label in System Number (for example, System 01)."
    if any(word in q for word in ("upload", "photo", "attachment", "document", "file", "चित्र", "दस्तावेज")):
        return "In the grievance form, add supporting evidence at the Photo step. Images and documents are optional; each file may be up to 5 MB, with up to 5 files per request. Review your details before submitting."
    if _status_intent(q):
        return "Please send the complaint reference number to check its status. Sign in is required before I can show private details. You can also track it at /track.html."
    if "complaint" in words and any(word in words for word in ("register", "file", "submit")):
        return "Open /student/new-complaint.html, enter the problem, category, and location, then review and submit. The portal shows a reference number when the complaint is registered."
    if any(word in q for word in ("priority", "urgent", "high", "medium", "low")):
        return "Priority indicates the urgency assigned to a grievance. The portal supports Low, Medium, High, and Urgent; the department/officer workflow manages it. The assistant cannot change a complaint's priority."
    if any(word in q for word in ("register", "account", "signup", "sign up", "registration", "darj", "panjeekaran", "पंजीकरण")):
        return "Create an account at /register.html with your details and complete the verification steps shown. Registration is for student/staff accounts; use /login.html if you already have an account."
    if any(word in q for word in ("login", "password", "otp", "email", "mobile", "forgot", "लॉगिन", "पासवर्ड")):
        return "For sign-in, email, mobile, or OTP trouble, check the selected role and use the message shown on the existing page. Use /forgot-password.html for a secure password reset. Never share your password or OTP in chat."
    if any(word in q for word in ("escalat", "contact", "department", "विभाग")):
        depts = "; ".join(f"{d['name']} ({d['email']})" for d in DEPARTMENTS)
        return f"The grievance is routed to its department. If it remains unresolved past its deadline, use the escalation process shown on the complaint page or contact the department: {depts}."
    return "I can help with grievance registration, department selection, status meanings, evidence uploads, tracking, escalation, and account access. You can ask in Hindi, English, or Hinglish. For private status details, sign in and share your complaint reference."


def _provider_answer(text: str, config, history: list = None) -> str | None:
    api_key = config.get("OPENAI_API_KEY") or config.get("CHATBOT_AI_API_KEY", "")
    if not api_key:
        return None
    base_url = (
        config.get("OPENAI_BASE_URL")
        or config.get("CHATBOT_AI_BASE_URL")
        or "https://api.openai.com/v1"
    )
    departments = "\n".join(
        f"- {d['name']}: {d['description']} Contact: {d['email']}" for d in DEPARTMENTS
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are the DSVV Grievance Management System assistant. Help students "
                "and staff in clear, concise Hindi, English, or Hinglish. Reply in the "
                "language and script of the user's latest message: use Devanagari for "
                "Hindi and Roman script for Hinglish. For a short ambiguous follow-up, "
                "continue the user's recent language style unless they switch. Do not "
                "translate the user's message to English before understanding it. Use only the "
                "verified portal facts below. If policy or process details are missing, "
                "say they are unavailable and direct the user to the portal; never invent "
                "university policy, complaint status, assignment, deadline, or user records. "
                "You cannot access databases or perform actions. Never claim a complaint "
                "was filed, changed, escalated, or resolved; only the backend complaint "
                "flow can confirm those actions. Never request passwords, OTPs, tokens, or "
                "unnecessary personal data. A complaint can be filed using the existing "
                "grievance form or the chat's guided complaint flow. The form collects "
                "title, description, category, optional evidence (up to 5 files, 5 MB each), "
                "location, then asks the user to review and submit. Tracking is available "
                "at /track.html; private complaint details are shown only after backend "
                "authorization. Supported priorities are Low, Medium, High, and Urgent; "
                "priority is determined by the backend and is not changed by the assistant. "
                "Water routes to Jal Kal Vibhag, electricity to Vidyut Vibhag, building "
                "and maintenance to Nirman Vibhag, and Computer/Lab to MCA Lab / Computer "
                "Lab. Computer/Lab choices are BCA Lab, BIT Lab, and MCA Lab. For an "
                "unresolved complaint, use the portal's escalation action and follow the "
                "deadline and escalation level shown there; do not invent timelines. "
                "Officers provide resolution reports; after a complaint is closed, the "
                "complainant can provide feedback from the complaint/feedback page. "
                "Feedback is restricted to the authenticated owner. Password reset: "
                "/forgot-password.html. Registration: /register.html; login: /login.html."
                "\nVerified department directory:\n" + departments
            ),
        }
    ]
    history = history if isinstance(history, list) else []
    for entry in history[-8:]:
        if (
            isinstance(entry, dict)
            and entry.get("role") in {"user", "assistant"}
            and isinstance(entry.get("content"), str)
        ):
            messages.append(
                {"role": entry["role"], "content": _ai_safe_text(entry["content"])}
            )
    messages.append({"role": "user", "content": _ai_safe_text(text)})

    try:
        timeout = max(
            2,
            min(int(config.get("OPENAI_TIMEOUT") or config.get("CHATBOT_AI_TIMEOUT", 12)), 20),
        )
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
        )
        with client:
            response = client.chat.completions.create(
                model=(
                    config.get("OPENAI_MODEL")
                    or config.get("CHATBOT_AI_MODEL")
                    or "gpt-4o-mini"
                ),
                temperature=0.2,
                max_tokens=350,
                messages=messages,
            )
        answer_text = response.choices[0].message.content
        if isinstance(answer_text, str) and answer_text.strip():
            return _ai_safe_text(answer_text.strip())[:2000]
    except APIError as exc:
        logger.warning("OpenAI chatbot request failed (%s)", type(exc).__name__)
        return None
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        logger.warning("OpenAI chatbot response could not be used (%s)", type(exc).__name__)
        return None
    return None


def answer(text: str, config, history: list = None, language: str = None) -> tuple[str, str]:
    """Return (answer, method); provider errors safely fall back to local FAQ."""
    generated = _provider_answer(text, config, history)
    if generated:
        return generated, "ai"
    return _fallback(text, language), "faq"


def suggested_action(text: str) -> dict | None:
    """Offer a direct link to an existing portal workflow when it fits."""
    q = (text or "").lower()
    if any(word in q for word in ("register", "submit", "file a", "new complaint", "new grievance", "water", "leak", "pani", "paani", "nal", "electric", "bijli", "building", "maintenance", "computer", "lab", "darj", "पानी", "बिजली", "शिकायत दर्ज")):
        return {"label": "Open grievance form", "href": "/student/new-complaint.html"}
    if any(word in q for word in ("forgot", "reset password", "password reset", "पासवर्ड")):
        return {"label": "Reset password", "href": "/forgot-password.html"}
    if any(word in q for word in ("login", "sign in", "otp", "email", "mobile", "लॉगिन")):
        return {"label": "Open sign in", "href": "/login.html"}
    if any(word in q for word in ("status", "track", "timeline", "stithi", "shikayat", "स्थिति", "शिकायत संख्या")):
        return {"label": "Track a complaint", "href": "/track.html"}
    return None


# ------------------------------------------------------------- Session storage


def get_or_create_session(session_id: str = None, user: dict = None) -> tuple[dict, bool]:
    """Load existing unexpired session or initialize a fresh one."""
    now = utcnow()
    created = False
    session = None

    if session_id:
        session = chatbot_sessions().find_one({"sessionId": session_id})
        if session:
            expires_at = session.get("expiresAt")
            if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at < now:
                chatbot_sessions().delete_one({"sessionId": session_id})
                session = None
            elif session.get("userId") and (
                not user or session["userId"] != user.get("id")
            ):
                session = None

    if not session:
        created = True
        new_id = secrets.token_urlsafe(24)
        session = {
            "sessionId": new_id,
            "userId": user.get("id") if user else None,
            "state": STATE_IDLE,
            "step": "idle",
            "draft": {},
            "step_history": [],
            "invalid_attempts": 0,
            "createdAt": now,
            "updatedAt": now,
            "expiresAt": now + timedelta(minutes=SESSION_TTL_MINUTES),
            "reference": None,
            "complaintId": None,
        }
        chatbot_sessions().insert_one(session)
    else:
        if user and user.get("id") and not session.get("userId"):
            session["userId"] = user["id"]

    return session, created


def save_session(session: dict) -> None:
    now = utcnow()
    session["updatedAt"] = now
    session["expiresAt"] = now + timedelta(minutes=SESSION_TTL_MINUTES)
    chatbot_sessions().replace_one({"sessionId": session["sessionId"]}, session, upsert=True)


def _finish_session(session: dict, complaint: dict, language: str = "en") -> dict:
    now = utcnow()
    reference = complaint.get("id") or complaint.get("reference")
    chatbot_sessions().update_one(
        {"sessionId": session["sessionId"]},
        {"$set": {
            "reference": reference,
            "complaintId": reference,
            "department": complaint.get("department"),
            "priority": complaint.get("priority"),
            "complaintStatus": complaint.get("status"),
            "state": STATE_COMPLETED,
            "step": "done",
            "updatedAt": now,
            "expiresAt": now + timedelta(minutes=SESSION_TTL_MINUTES),
        }},
    )
    session.update({
        "reference": reference,
        "complaintId": reference,
        "department": complaint.get("department"),
        "priority": complaint.get("priority"),
        "complaintStatus": complaint.get("status"),
        "state": STATE_COMPLETED,
        "step": "done",
    })
    return _done_response(session, complaint, language=language)


def _done_response(
    session: dict,
    complaint: dict = None,
    newly_created: bool = False,
    language: str = "en",
) -> dict:
    reference = session.get("reference")
    department = (complaint or {}).get("department") or session.get("department")
    if language == "hi":
        reply = (
            f"शिकायत सफलतापूर्वक दर्ज हुई। Reference ID: {reference}. "
            f"विभाग: {department or 'जाँच जारी है'}."
            if newly_created
            else f"शिकायत {reference} पहले ही दर्ज हो चुकी है। "
            f"विभाग: {department or 'जाँच जारी है'}."
        )
        quick_replies = ["शिकायत ट्रैक करें", "दूसरी शिकायत दर्ज करें", "पूर्ण"]
    elif language == "hinglish":
        reply = (
            f"Complaint register ho gayi. Reference ID: {reference}. "
            f"Department: {department or 'review mein hai'}."
            if newly_created
            else f"Complaint {reference} pehle hi register ho chuki hai. "
            f"Department: {department or 'review mein hai'}."
        )
        quick_replies = ["Track this complaint", "Raise another complaint", "Done"]
    else:
        reply = (
            f"Complaint registered successfully. Reference ID: {reference}. "
            f"Assigned department: {department or 'being reviewed'}."
            if newly_created
            else f"Complaint {reference} has already been registered. "
            f"Assigned department: {department or 'being reviewed'}."
        )
        quick_replies = ["Track this complaint", "Raise another complaint", "Done"]

    return {
        "reply": reply,
        "sessionId": session["sessionId"],
        "step": "done",
        "method": "complaint_flow",
        "created": newly_created,
        "complaint": {
            "id": reference,
            "reference": reference,
            "department": department,
            "priority": (complaint or {}).get("priority") or session.get("priority"),
            "status": (complaint or {}).get("status") or session.get("complaintStatus"),
        },
        "quickReplies": quick_replies,
        "action": {"label": "Track complaint", "href": f"/track.html?id={reference}"},
    }


def _claim_submission(session: dict) -> bool:
    result = chatbot_sessions().update_one(
        {
            "sessionId": session["sessionId"],
            "state": STATE_CONFIRMING_SUBMISSION,
            "$or": [{"reference": None}, {"reference": {"$exists": False}}],
        },
        {"$set": {"state": STATE_SUBMITTING, "updatedAt": utcnow()}},
    )
    return result.modified_count == 1


def _release_submission(session: dict) -> None:
    now = utcnow()
    chatbot_sessions().update_one(
        {"sessionId": session["sessionId"], "state": STATE_SUBMITTING},
        {"$set": {
            "state": STATE_CONFIRMING_SUBMISSION,
            "step": "confirm",
            "updatedAt": now,
            "expiresAt": now + timedelta(minutes=SESSION_TTL_MINUTES),
        }},
    )


def _problem_report_intent(text: str) -> bool:
    """Separate an unsolicited problem report from the existing help FAQ."""
    lower = (text or "").strip().lower()
    if "?" in lower or _how_to_question(lower) or lower.startswith(("there is ", "there's ")):
        return False
    if _DEVANAGARI.search(lower):
        return any(
            marker in lower
            for marker in (
                "नहीं आ रहा", "नहीं आ रही", "काम नहीं कर", "नहीं चल",
                "चली गई", "खराब", "लीक", "टूट", "बंद हो", "आग", "धुआँ",
                "चिंगारी", "करंट",
            )
        )
    if lower.startswith(("mera ", "meri ", "mere ", "my ", "hamara ", "hamari ")):
        return True
    markers = (
        "not working", "kaam nahi", "chal nahi", "broken", "stopped working",
        "short circuit", "shortcircuit", "fire", "spark", "sparking",
        "leak", "leaking", "nahi aa", "chali gayi", "chala gaya",
        "kharab", "toot", "tut gaya", "crack", "damaged",
        "aag", "dhua", "chingaari", "karant", "current lag",
    )
    return any(marker in lower for marker in markers)


# ---------------------------------------------------------- Slot determination (Single source of truth)


def get_flow_steps(draft: dict, user: dict = None, config: dict = None) -> list[str]:
    """Single source of truth for the complete sequence of complaint flow steps."""
    steps = ["category"]
    cat = draft.get("category")
    if cat == "Computer/Lab":
        steps.extend(["lab", "systemNumber"])
    else:
        steps.append("location")
    steps.append("description")

    ask_identity = config.get("CHATBOT_ASK_IDENTITY", True) if config else True
    if ask_identity:
        steps.append("scholarId")
        if user and user.get("id"):
            acc_mob = (user.get("mobile") or "").strip()
            if not is_mobile(acc_mob):
                steps.append("mobile")
            steps.append("confirm_identity")
        else:
            steps.extend(["name", "mobile", "email"])
    else:
        if not user:
            steps.append("scholarId")
            if draft.get("isRegistered") is False:
                steps.extend(["name", "mobile", "email"])

    steps.append("confirm")
    return steps


def get_first_missing_slot(draft: dict, user: dict = None, config: dict = None) -> str:
    """Find the first unfilled slot in canonical order. SINGLE SOURCE OF TRUTH."""
    steps = get_flow_steps(draft, user, config)
    for step in steps:
        if step == "category" and not draft.get("category"):
            return "category"
        if step == "lab" and not draft.get("lab"):
            return "lab"
        if step == "systemNumber" and not draft.get("systemNumber"):
            return "systemNumber"
        if step == "location" and not draft.get("location"):
            return "location"
        if step == "description" and len((draft.get("description") or "").strip()) < 25:
            return "description"
        if step == "scholarId" and not draft.get("scholarId"):
            return "scholarId"
        if step == "name" and len((draft.get("name") or "").strip()) < 3:
            return "name"
        if step == "mobile" and not is_mobile((draft.get("mobile") or "").strip()):
            return "mobile"
        if step == "email" and not is_email((draft.get("email") or "").strip()):
            return "email"
        if step == "confirm_identity" and not draft.get("identityConfirmed"):
            return "confirm_identity"
        if step == "confirm":
            return "confirm"
    return "confirm"


def get_step_progress(step: str, draft: dict, user: dict = None, config: dict = None) -> tuple[int, int]:
    steps = get_flow_steps(draft, user, config)
    total = len(steps)
    try:
        idx = steps.index(step) + 1
    except ValueError:
        idx = total
    return idx, total


def prompt_for_slot(
    slot: str,
    draft: dict,
    language: str = "en",
    user: dict = None,
    config: dict = None,
) -> tuple[str, list | None]:
    """Generate prompt text (with progress hint) and quick reply buttons for a given slot."""
    step_num, total_steps = get_step_progress(slot, draft, user, config)

    # Progress header
    if language == "hi":
        p_hdr = f"[चरण {step_num}/{total_steps}]\n"
        back_btn = "पीछे"
        cancel_btn = "रद्द करें"
    elif language == "hinglish":
        p_hdr = f"[Step {step_num} of {total_steps}]\n"
        back_btn = "Back"
        cancel_btn = "Cancel"
    else:
        p_hdr = f"[Step {step_num} of {total_steps}]\n"
        back_btn = "Back"
        cancel_btn = "Cancel"

    if slot == "category":
        if language == "hi":
            reply = f"{p_hdr}कृपया अपनी शिकायत की श्रेणी (Category) चुनें:"
            buttons = ["भवन", "जल", "विद्युत", "कंप्यूटर लैब", "छात्रावास", "कक्षा", "अन्य", cancel_btn]
        elif language == "hinglish":
            reply = f"{p_hdr}Apni complaint ki category choose karein:"
            buttons = ALLOWED_CATEGORIES + [cancel_btn]
        else:
            reply = f"{p_hdr}Please select the category of your complaint:"
            buttons = ALLOWED_CATEGORIES + [cancel_btn]
        return reply, buttons

    if slot == "lab":
        if language == "hi":
            reply = f"{p_hdr}समस्या किस कंप्यूटर लैब में है?"
            buttons = ["BCA Lab", "BIT Lab", "MCA Lab", back_btn, cancel_btn]
        elif language == "hinglish":
            reply = f"{p_hdr}Issue kis computer lab mein hai?"
            buttons = ALLOWED_LABS + [back_btn, cancel_btn]
        else:
            reply = f"{p_hdr}Which computer lab is the issue in?"
            buttons = ALLOWED_LABS + [back_btn, cancel_btn]
        return reply, buttons

    if slot == "systemNumber":
        if language == "hi":
            reply = f"{p_hdr}कृपया सिस्टम नंबर या वर्कस्टेशन का लेबल लिखें (उदाहरण: System 01)।"
        elif language == "hinglish":
            reply = f"{p_hdr}System number ya workstation label batayein (jaise: System 01):"
        else:
            reply = f"{p_hdr}What is the system number or workstation label (e.g. System 01)?"
        return reply, [back_btn, cancel_btn]

    if slot == "location":
        if language == "hi":
            reply = f"{p_hdr}कैंपस में समस्या कहाँ है? नीचे दिए गए विकल्पों में से चुनें या भवन और कमरा लिखें:"
            buttons = CANONICAL_LOCATIONS + [back_btn, cancel_btn]
        elif language == "hinglish":
            reply = f"{p_hdr}Campus mein issue kahan hai? Landmark choose karein ya building aur room batayein:"
            buttons = CANONICAL_LOCATIONS + [back_btn, cancel_btn]
        else:
            reply = f"{p_hdr}Where on campus is the issue located? Choose a landmark or enter the building and room:"
            buttons = CANONICAL_LOCATIONS + [back_btn, cancel_btn]
        return reply, buttons

    if slot == "description":
        if language == "hi":
            reply = f"{p_hdr}कृपया समस्या का पूरा विवरण दें (कम से कम 25 अक्षर):"
        elif language == "hinglish":
            reply = f"{p_hdr}Problem ka detail batayein (kam se kam 25 characters):"
        else:
            reply = f"{p_hdr}Please describe the problem in detail (minimum 25 characters):"
        return reply, [back_btn, cancel_btn]

    if slot == "scholarId":
        if language == "hi":
            reply = f"{p_hdr}कृपया अपना स्कॉलर आईडी / छात्र आईडी दर्ज करें (उदाहरण: MCA/2024/018):"
        elif language == "hinglish":
            reply = f"{p_hdr}Apna Scholar ID / Student ID batayein (jaise: MCA/2024/018):"
        else:
            reply = f"{p_hdr}Please enter your Scholar ID / Student ID (e.g. MCA/2024/018):"
        return reply, [back_btn, cancel_btn]

    if slot == "confirm_identity":
        name = draft.get("name", "")
        mobile = draft.get("mobile", "")
        email = draft.get("email", "")
        if language == "hi":
            reply = f"{p_hdr}ये विवरण सही हैं?\n• नाम: {name}\n• मोबाइल: {mobile}\n• ईमेल: {email}"
            buttons = ["हाँ, विवरण सही है", "विवरण बदलें", cancel_btn]
        elif language == "hinglish":
            reply = f"{p_hdr}Ye details sahi hain?\n• Name: {name}\n• Mobile: {mobile}\n• Email: {email}"
            buttons = ["Haan, sahi hai", "Badlein", cancel_btn]
        else:
            reply = f"{p_hdr}Are these details correct?\n• Name: {name}\n• Mobile: {mobile}\n• Email: {email}"
            buttons = ["Yes, details are correct", "Change details", cancel_btn]
        return reply, buttons

    if slot == "name":
        if language == "hi":
            reply = f"{p_hdr}कृपया अपना पूरा नाम लिखें (कम से कम 3 अक्षर):"
        elif language == "hinglish":
            reply = f"{p_hdr}Apna poora naam batayein (kam se kam 3 characters):"
        else:
            reply = f"{p_hdr}Please enter your full name (minimum 3 characters):"
        return reply, [back_btn, cancel_btn]

    if slot == "mobile":
        if language == "hi":
            reply = f"{p_hdr}अपडेट प्राप्त करने के लिए अपना 10 अंकों का मोबाइल नंबर लिखें (उदाहरण: 9876543210):"
        elif language == "hinglish":
            reply = f"{p_hdr}Updates ke liye apna 10-digit mobile number batayein (jaise: 9876543210):"
        else:
            reply = f"{p_hdr}Please enter your 10-digit mobile number for updates (e.g. 9876543210):"
        return reply, [back_btn, cancel_btn]

    if slot == "email":
        if language == "hi":
            reply = f"{p_hdr}समाधान की सूचना के लिए अपना ईमेल पता लिखें (उदाहरण: student@dsvv.ac.in):"
        elif language == "hinglish":
            reply = f"{p_hdr}Resolution updates ke liye apna email address batayein (jaise: student@example.com):"
        else:
            reply = f"{p_hdr}Please enter your email address for notifications (e.g. student@example.com):"
        return reply, [back_btn, cancel_btn]

    if slot == "confirm":
        category = draft.get("category", "")
        location = (
            f"{draft.get('lab', '')} (Workstation: {draft.get('systemNumber', '')})"
            if category == "Computer/Lab"
            else draft.get("location", "Campus")
        )
        scholar_id = draft.get("scholarId", "")
        name = draft.get("name", "")
        mobile = draft.get("mobile", "")
        email = draft.get("email", "")

        if language == "hi":
            summary = (
                f"{p_hdr}कृपया अपनी शिकायत का सारांश जाँचें:\n"
                f"• श्रेणी: {category}\n"
                f"• स्थान / लैब: {location}\n"
                f"• समस्या: {draft.get('description', '')}\n"
                f"• स्कॉलर आईडी: {scholar_id}\n"
                f"• नाम: {name}\n"
                f"• मोबाइल: {mobile}\n"
                f"• ईमेल: {email}\n\n"
                "क्या आप इस शिकायत को अभी दर्ज करना चाहते हैं?"
            )
            buttons = ["दर्ज करें", "बदलें", "रद्द करें"]
        elif language == "hinglish":
            summary = (
                f"{p_hdr}Complaint summary review karein:\n"
                f"• Category: {category}\n"
                f"• Location / Lab: {location}\n"
                f"• Problem: {draft.get('description', '')}\n"
                f"• Scholar ID: {scholar_id}\n"
                f"• Name: {name}\n"
                f"• Mobile: {mobile}\n"
                f"• Email: {email}\n\n"
                "Kya aap complaint abhi submit karna chahenge?"
            )
            buttons = ["Submit", "Edit", "Cancel"]
        else:
            summary = (
                f"{p_hdr}Please review your complaint summary:\n"
                f"• Category: {category}\n"
                f"• Location / Lab: {location}\n"
                f"• Problem: {draft.get('description', '')}\n"
                f"• Scholar ID: {scholar_id}\n"
                f"• Name: {name}\n"
                f"• Mobile: {mobile}\n"
                f"• Email: {email}\n\n"
                "Would you like to submit this complaint now?"
            )
            buttons = ["Submit", "Edit", "Cancel"]
        return summary, buttons

    return ("How can I help you?", ["Raise a complaint", "Track a complaint"])


# ----------------------------------------------------------------- Fast path


def detect_fast_path(text: str) -> dict | None:
    """Classify problem text upfront and check for high-confidence category."""
    cleaned = (text or "").strip()
    if len(cleaned) < 8:
        return None

    try:
        dept_result = ai_service.classify_department(title="", description=cleaned)
    except Exception:
        return None

    department = dept_result.get("department")
    confidence = dept_result.get("confidence", 0.0)

    if confidence >= 0.5 and department in DEPT_TO_CATEGORY:
        proposed_cat = DEPT_TO_CATEGORY[department]
        return {
            "department": department,
            "category": proposed_cat,
            "confidence": confidence,
        }
    return None


# ----------------------------------------------------------- Master dispatch


def handle_chat_message(
    text: str,
    session_id: str = None,
    user: dict = None,
    action: str = None,
    config: dict = None,
    client_ip: str = "",
) -> dict:
    """Master conversational entrypoint: handles FAQ, tracking and complaint flow."""
    config = config or {}
    message_text = (text or "").strip()
    action_val = (action or "").strip().lower()

    session, created_new = get_or_create_session(session_id, user)
    if not isinstance(session.get("draft"), dict):
        session["draft"] = {}
    if not isinstance(session.get("step_history"), list):
        session["step_history"] = []

    language = _language_style(message_text, session.get("preferredLanguage", "en"))
    session["preferredLanguage"] = language
    draft = session["draft"]
    state = session.get("state", STATE_IDLE)

    # 1. Immutable submitted session check
    if state == STATE_COMPLETED and not _status_intent(message_text):
        starts_another = (
            action_val in ("new", "raise_complaint")
            or "raise another" in message_text.lower()
            or "another complaint" in message_text.lower()
            or "raise a complaint" in message_text.lower()
            or "शिकायत दर्ज करें" in message_text.lower()
        )
        if starts_another:
            session, _ = get_or_create_session(None, user)
            session["preferredLanguage"] = language
            session["draft"] = {}
            session["step_history"] = []
            session["invalid_attempts"] = 0
            session["state"] = STATE_COLLECTING
            session["step"] = "category"
            save_session(session)
            prompt, quick_replies = prompt_for_slot("category", session["draft"], language, user, config)
            return {
                "reply": prompt,
                "sessionId": session["sessionId"],
                "step": "category",
                "method": "complaint_flow",
                "quickReplies": quick_replies,
                "draft": session["draft"],
            }
        return _done_response(session, language=language)

    # 2. Lock release if stuck submitting
    if state == STATE_SUBMITTING:
        committed = complaints().find_one(
            {"_chatbotSessionId": session["sessionId"]}, {"_id": 0}
        )
        if committed:
            return _finish_session(session, committed, language)
        _release_submission(session)
        session["state"] = STATE_CONFIRMING_SUBMISSION
        state = STATE_CONFIRMING_SUBMISSION

    # 3. Global Cancel Intent
    if action_val == "cancel" or message_text.lower() in ("cancel", "रद्द करें", "radd", "stop", "abort", "reset"):
        session["draft"] = {}
        session["step_history"] = []
        session["invalid_attempts"] = 0
        session["state"] = STATE_IDLE
        session["step"] = "idle"
        save_session(session)
        cancel_replies = {
            "hi": "आपकी शिकायत का ड्राफ्ट रद्द कर दिया गया है। मैं आपकी और क्या मदद कर सकता हूँ?",
            "hinglish": "Aapki complaint draft cancel ho gayi. Main aapki aur kya help kar sakta hoon?",
            "en": "Your complaint draft has been cancelled. How else can I help you?",
        }
        starter_replies = {
            "hi": ["शिकायत दर्ज करें", "शिकायत ट्रैक करें", "सहायता और FAQ"],
            "hinglish": ["Raise a complaint", "Track a complaint", "Help & FAQs"],
            "en": ["Raise a complaint", "Track a complaint", "Help & FAQs"],
        }[language]
        return {
            "reply": cancel_replies[language],
            "sessionId": session["sessionId"],
            "step": "idle",
            "method": "complaint_flow",
            "quickReplies": starter_replies,
        }

    # 4. Global Back Intent during active flow (Requirement C)
    if action_val == "back" or message_text.lower() in ("back", "पीछे", "go back", "wapas", "peeche"):
        if state in (STATE_COLLECTING, STATE_CONFIRMING_SUBMISSION, STATE_EDITING, STATE_CONFIRMING_FAST_PATH):
            if session.get("step_history"):
                prev_step = session["step_history"].pop()
                draft.pop(prev_step, None)
                if prev_step == "scholarId":
                    draft.pop("identityConfirmed", None)
                if prev_step == "category":
                    draft.pop("lab", None)
                    draft.pop("systemNumber", None)
                    draft.pop("location", None)
                session["step"] = prev_step
                session["state"] = STATE_COLLECTING
                session["invalid_attempts"] = 0
                save_session(session)
                prompt, qr = prompt_for_slot(prev_step, draft, language, user, config)
                return {
                    "reply": prompt,
                    "sessionId": session["sessionId"],
                    "step": prev_step,
                    "method": "complaint_flow",
                    "quickReplies": qr,
                    "draft": draft,
                }
            else:
                session["draft"] = {}
                session["state"] = STATE_IDLE
                session["step"] = "idle"
                save_session(session)
                starter_replies = {
                    "hi": ["शिकायत दर्ज करें", "शिकायत ट्रैक करें", "सहायता और FAQ"],
                    "hinglish": ["Raise a complaint", "Track a complaint", "Help & FAQs"],
                    "en": ["Raise a complaint", "Track a complaint", "Help & FAQs"],
                }[language]
                return {
                    "reply": "Cancelled. How else can I help?",
                    "sessionId": session["sessionId"],
                    "step": "idle",
                    "method": "complaint_flow",
                    "quickReplies": starter_replies,
                }

    # 5. Active flow interrupted by "Raise a complaint" (Requirement B)
    is_raise_intent = (
        action_val in ("raise_complaint", "new_complaint", "create")
        or (
            not _how_to_question(message_text.lower())
            and any(phrase in message_text.lower() for phrase in (
                "raise a complaint", "raise complaint", "new complaint",
                "file a complaint", "lodge complaint", "शिकायत दर्ज करें", "नई शिकायत दर्ज",
                "shikayat darj karein", "shikayat darj karo", "complaint darj karo",
                "mujhe complaint register karni hai", "i want to register a complaint",
            ))
        )
    )

    if is_raise_intent and state in (STATE_COLLECTING, STATE_CONFIRMING_FAST_PATH, STATE_CONFIRMING_SUBMISSION, STATE_EDITING):
        session["previous_state"] = state
        session["previous_step"] = session.get("step")
        session["state"] = STATE_CONFIRMING_RESTART
        session["step"] = "confirm_restart"
        save_session(session)
        msg = {
            "hi": "चल रही शिकायत जारी रखें या नई शुरू करें?",
            "hinglish": "Chal rahi complaint jaari rakhein ya naya shuru karein?",
            "en": "Do you want to continue your current complaint or start a new one?",
        }[language]
        btns = {
            "hi": ["जारी रखें", "नई शुरू करें"],
            "hinglish": ["Continue", "Start new"],
            "en": ["Continue", "Start new"],
        }[language]
        return {
            "reply": msg,
            "sessionId": session["sessionId"],
            "step": "confirm_restart",
            "method": "complaint_flow",
            "quickReplies": btns,
            "draft": draft,
        }

    # Handling response in STATE_CONFIRMING_RESTART
    if state == STATE_CONFIRMING_RESTART:
        low = message_text.strip().lower()
        if any(w in low for w in ("new", "naya", "नई", "start new", "शुरू")):
            session["draft"] = {}
            session["step_history"] = []
            session["invalid_attempts"] = 0
            session["state"] = STATE_COLLECTING
            session["step"] = "category"
            save_session(session)
            prompt, qr = prompt_for_slot("category", session["draft"], language, user, config)
            return {
                "reply": prompt,
                "sessionId": session["sessionId"],
                "step": "category",
                "method": "complaint_flow",
                "quickReplies": qr,
                "draft": session["draft"],
            }
        else:
            # Continue current complaint
            session["state"] = session.get("previous_state", STATE_COLLECTING)
            cur = session.get("previous_step") or get_first_missing_slot(draft, user, config)
            session["step"] = cur
            save_session(session)
            prompt, qr = prompt_for_slot(cur, draft, language, user, config)
            resume_msg = {
                "hi": f"ठीक है, जारी रखते हैं:\n\n{prompt}",
                "hinglish": f"Theek hai, continue karte hain:\n\n{prompt}",
                "en": f"Resuming your complaint:\n\n{prompt}",
            }[language]
            return {
                "reply": resume_msg,
                "sessionId": session["sessionId"],
                "step": cur,
                "method": "complaint_flow",
                "quickReplies": qr,
                "draft": draft,
            }

    # 6. Status tracking for verified records
    ref_match = complaint_reference(message_text)
    is_status_q = _status_intent(message_text)
    tracking_reference = ref_match or (
        (session.get("lastComplaintReference") or session.get("reference"))
        if is_status_q else None
    )
    if is_status_q and state in {STATE_IDLE, STATE_COMPLETED}:
        if not tracking_reference:
            save_session(session)
            replies = {
                "hi": "अपनी शिकायत की स्थिति देखने के लिए उसका reference number भेजें। निजी जानकारी दिखाने से पहले आपको लॉग इन करना होगा।",
                "hinglish": "Complaint ka status check karne ke liye uska reference number bhejiye. Private details dekhne se pehle sign in zaroori hai.",
                "en": "Please send the complaint reference number to check its status. Sign in is required before I can show private details.",
            }
            return {
                "reply": replies[language],
                "sessionId": session["sessionId"],
                "step": "idle",
                "method": "faq",
                "source": "local_faq",
                "sourceNotice": {
                    "hi": "यह built-in FAQ की जानकारी है, शिकायत रिकॉर्ड का status नहीं।",
                    "hinglish": "Yeh built-in FAQ ki guidance hai, complaint record ka status nahi.",
                    "en": "This guidance is from the built-in FAQ, not a complaint lookup.",
                }[language],
                "action": {"label": "Sign in", "href": "/login.html"} if not user else None,
            }
        if not user:
            save_session(session)
            replies = {
                "hi": "शिकायत की निजी जानकारी दिखाने से पहले कृपया लॉग इन करें।",
                "hinglish": "Complaint ki private details dikhane se pehle please sign in karein.",
                "en": "Please sign in first. I can show complaint details only after the server verifies your access.",
            }
            return {
                "reply": replies[language],
                "sessionId": session["sessionId"],
                "method": "faq",
                "action": {"label": "Sign in", "href": "/login.html"},
            }
        try:
            complaint = complaint_service.get_complaint(tracking_reference, user)
        except ApiException as exc:
            if exc.status not in (403, 404):
                raise
            save_session(session)
            replies = {
                "hi": "यह शिकायत आपके खाते में नहीं मिली या आपको इसकी जानकारी देखने की अनुमति नहीं है। reference number जाँचें और सही खाते से लॉग इन करें।",
                "hinglish": "Yeh complaint aapke account mein nahi mili ya aapko ise dekhne ki permission nahi hai. Reference number check karke sahi account se sign in karein.",
                "en": "I couldn't find that complaint for your account, or you don't have access to it. Check the reference and sign in with the account that submitted it.",
            }
            return {
                "reply": replies[language],
                "sessionId": session["sessionId"],
                "method": "faq",
            }
        session["lastComplaintReference"] = complaint.get("id")
        save_session(session)
        timeline = [
            {"label": ev.get("label"), "at": ev.get("at"), "state": ev.get("state")}
            for ev in (complaint.get("timeline") or [])
            if ev.get("at")
        ]
        replies = {
            "hi": f"शिकायत {complaint.get('id')}: स्थिति {complaint.get('status', 'उपलब्ध नहीं')}. विभाग: {complaint.get('department') or 'अभी तय नहीं'}. प्राथमिकता: {complaint.get('priority') or 'तय नहीं'}.",
            "hinglish": f"Complaint {complaint.get('id')}: status {complaint.get('status', 'unavailable')}. Department: {complaint.get('department') or 'abhi assign nahi hua'}. Priority: {complaint.get('priority') or 'set nahi hai'}.",
            "en": f"Complaint {complaint.get('id')}: {complaint.get('status', 'Status unavailable')}. Department: {complaint.get('department') or 'Not assigned'}. Priority: {complaint.get('priority') or 'Not set'}.",
        }
        return {
            "reply": replies[language],
            "sessionId": session["sessionId"],
            "method": "verified_record",
            "sourceNotice": {
                "hi": "शिकायत पोर्टल से सत्यापित रिकॉर्ड।",
                "hinglish": "Complaint portal se verified record.",
                "en": "Verified complaint record.",
            }[language],
            "complaint": {
                "id": complaint.get("id"),
                "status": complaint.get("status"),
                "department": complaint.get("department"),
                "priority": complaint.get("priority"),
                "submittedAt": complaint.get("submittedAt"),
                "updatedAt": complaint.get("updatedAt"),
                "timeline": timeline,
            },
        }

    # 7. FAQ Interrupt during active flow (Requirement D)
    if state == STATE_COLLECTING and _how_to_question(message_text):
        faq_ans, _ = answer(message_text, config, language=language)
        cur_slot = get_first_missing_slot(draft, user, config)
        pending_prompt, qr = prompt_for_slot(cur_slot, draft, language, user, config)
        interjection = {
            "hi": f"{faq_ans}\n\nचल रही शिकायत पर वापस आते हैं:\n\n{pending_prompt}",
            "hinglish": f"{faq_ans}\n\nChal rahi complaint par wapas aate hain:\n\n{pending_prompt}",
            "en": f"{faq_ans}\n\nReturning to your complaint in progress:\n\n{pending_prompt}",
        }[language]
        save_session(session)
        return {
            "reply": interjection,
            "sessionId": session["sessionId"],
            "step": cur_slot,
            "method": "complaint_flow",
            "quickReplies": qr,
            "draft": draft,
        }

    # 8. Fast-path Confirmation State
    if state == STATE_CONFIRMING_FAST_PATH:
        proposed = draft.get("proposedCategory")
        if (
            action_val == "yes"
            or message_text.lower().startswith("yes")
            or (proposed and proposed.lower() in message_text.lower())
            or message_text.lower() in ("confirm", "haan", "ha", "हाँ", "sahi", "theek")
        ):
            draft["category"] = proposed
            session["step_history"] = ["category"]
            session["state"] = STATE_COLLECTING
            session["invalid_attempts"] = 0
            next_slot = get_first_missing_slot(draft, user, config)
            session["step"] = next_slot
            save_session(session)
            prompt, qr = prompt_for_slot(next_slot, draft, language, user, config)
            confirmation = {
                "hi": f"ठीक है, category {proposed} चुनी गई।\n\n{prompt}",
                "hinglish": f"Theek hai, {proposed} category select ki hai.\n\n{prompt}",
                "en": f"Great, setting category to {proposed}.\n\n{prompt}",
            }[language]
            return {
                "reply": confirmation,
                "sessionId": session["sessionId"],
                "step": next_slot,
                "method": "complaint_flow",
                "quickReplies": qr,
                "draft": draft,
            }
        elif "other" in message_text.lower() or "choose" in message_text.lower() or "दूसरी" in message_text:
            session["state"] = STATE_COLLECTING
            session["step"] = "category"
            session["invalid_attempts"] = 0
            save_session(session)
            prompt, qr = prompt_for_slot("category", draft, language, user, config)
            return {
                "reply": prompt,
                "sessionId": session["sessionId"],
                "step": "category",
                "method": "complaint_flow",
                "quickReplies": qr,
                "draft": draft,
            }
        else:
            session["state"] = STATE_COLLECTING
            session["step"] = "category"
            session["invalid_attempts"] = 0
            save_session(session)
            prompt, qr = prompt_for_slot("category", draft, language, user, config)
            return {
                "reply": prompt,
                "sessionId": session["sessionId"],
                "step": "category",
                "method": "complaint_flow",
                "quickReplies": qr,
                "draft": draft,
            }

    # 9. Editing Choice State
    if state == STATE_EDITING:
        target = message_text.strip().lower()
        if "category" in target or "श्रेणी" in target:
            draft.pop("category", None)
            draft.pop("lab", None)
            draft.pop("systemNumber", None)
            draft.pop("location", None)
            session["state"] = STATE_COLLECTING
            session["step"] = "category"
            session["invalid_attempts"] = 0
            save_session(session)
            prompt, qr = prompt_for_slot("category", draft, language, user, config)
            return {"reply": prompt, "sessionId": session["sessionId"], "step": "category", "method": "complaint_flow", "quickReplies": qr, "draft": draft}
        elif "lab" in target or "location" in target or "लैब" in target or "स्थान" in target:
            draft.pop("lab", None)
            draft.pop("systemNumber", None)
            draft.pop("location", None)
            session["state"] = STATE_COLLECTING
            slot = "lab" if draft.get("category") == "Computer/Lab" else "location"
            session["step"] = slot
            session["invalid_attempts"] = 0
            save_session(session)
            prompt, qr = prompt_for_slot(slot, draft, language, user, config)
            return {"reply": prompt, "sessionId": session["sessionId"], "step": slot, "method": "complaint_flow", "quickReplies": qr, "draft": draft}
        elif "desc" in target or "problem" in target or "विवरण" in target or "समस्या" in target:
            draft.pop("description", None)
            session["state"] = STATE_COLLECTING
            session["step"] = "description"
            session["invalid_attempts"] = 0
            save_session(session)
            prompt, qr = prompt_for_slot("description", draft, language, user, config)
            return {"reply": prompt, "sessionId": session["sessionId"], "step": "description", "method": "complaint_flow", "quickReplies": qr, "draft": draft}
        elif "scholar" in target or "student id" in target or "स्कॉलर" in target:
            draft.pop("scholarId", None)
            draft.pop("identityConfirmed", None)
            session["state"] = STATE_COLLECTING
            session["step"] = "scholarId"
            session["invalid_attempts"] = 0
            save_session(session)
            prompt, qr = prompt_for_slot("scholarId", draft, language, user, config)
            return {"reply": prompt, "sessionId": session["sessionId"], "step": "scholarId", "method": "complaint_flow", "quickReplies": qr, "draft": draft}
        elif "name" in target or "नाम" in target:
            draft.pop("name", None)
            draft.pop("identityConfirmed", None)
            session["state"] = STATE_COLLECTING
            session["step"] = "name"
            session["invalid_attempts"] = 0
            save_session(session)
            prompt, qr = prompt_for_slot("name", draft, language, user, config)
            return {"reply": prompt, "sessionId": session["sessionId"], "step": "name", "method": "complaint_flow", "quickReplies": qr, "draft": draft}
        elif "mobile" in target or "phone" in target or "मोबाइल" in target:
            draft.pop("mobile", None)
            draft.pop("identityConfirmed", None)
            session["state"] = STATE_COLLECTING
            session["step"] = "mobile"
            session["invalid_attempts"] = 0
            save_session(session)
            prompt, qr = prompt_for_slot("mobile", draft, language, user, config)
            return {"reply": prompt, "sessionId": session["sessionId"], "step": "mobile", "method": "complaint_flow", "quickReplies": qr, "draft": draft}
        elif "email" in target or "ईमेल" in target:
            draft.pop("email", None)
            draft.pop("identityConfirmed", None)
            session["state"] = STATE_COLLECTING
            session["step"] = "email"
            session["invalid_attempts"] = 0
            save_session(session)
            prompt, qr = prompt_for_slot("email", draft, language, user, config)
            return {"reply": prompt, "sessionId": session["sessionId"], "step": "email", "method": "complaint_flow", "quickReplies": qr, "draft": draft}
        else:
            session["state"] = STATE_CONFIRMING_SUBMISSION
            session["step"] = "confirm"
            save_session(session)
            prompt, qr = prompt_for_slot("confirm", draft, language, user, config)
            return {"reply": prompt, "sessionId": session["sessionId"], "step": "confirm", "method": "complaint_flow", "quickReplies": qr, "draft": draft}

    # 10. Summary Confirmation State
    if state == STATE_CONFIRMING_SUBMISSION:
        missing_slot = get_first_missing_slot(draft, user, config)
        if missing_slot != "confirm":
            session["state"] = STATE_COLLECTING
            session["step"] = missing_slot
            save_session(session)
            prompt, quick_replies = prompt_for_slot(missing_slot, draft, language, user, config)
            return {
                "reply": prompt,
                "sessionId": session["sessionId"],
                "step": missing_slot,
                "method": "complaint_flow",
                "quickReplies": quick_replies,
                "draft": draft,
            }

        confirmation = re.sub(r"[\s.,!?।]+", " ", message_text.strip().lower()).strip()
        if action_val == "submit" or confirmation in _SUBMISSION_CONFIRMATIONS:
            if session.get("reference"):
                return _done_response(session, language=language)

            if not _claim_submission(session):
                latest = chatbot_sessions().find_one({"sessionId": session["sessionId"]}) or session
                if latest.get("reference"):
                    return _done_response(latest, language=language)
                return {
                    "reply": "Your complaint is still being registered. Please retry shortly if no reference appears.",
                    "sessionId": session["sessionId"],
                    "step": "submitting",
                    "method": "complaint_flow",
                }
            session["state"] = STATE_SUBMITTING

            is_guest = not user
            if is_guest:
                if client_ip:
                    ip_allowed, _ = rate_limit.check(
                        "chatbot_guest_ip",
                        limit=config.get("CHATBOT_GUEST_IP_LIMIT", 15),
                        window=config.get("CHATBOT_GUEST_RATE_WINDOW", 300),
                        client_key=f"ip:{client_ip}",
                    )
                    if not ip_allowed:
                        _release_submission(session)
                        return {
                            "reply": "Too many complaints submitted from this connection. Please wait 5 minutes before submitting again.",
                            "sessionId": session["sessionId"],
                            "step": "confirm",
                            "method": "complaint_flow",
                            "quickReplies": ["Submit", "Cancel"],
                        }
                guest_mobile = draft.get("mobile", "")
                if guest_mobile:
                    mobile_hash = hashlib.sha256(guest_mobile.encode("utf-8")).hexdigest()
                    mob_allowed, _ = rate_limit.check(
                        "chatbot_guest_mobile",
                        limit=config.get("CHATBOT_GUEST_MOBILE_LIMIT", 5),
                        window=config.get("CHATBOT_GUEST_RATE_WINDOW", 300),
                        client_key=f"mobile:{mobile_hash}",
                    )
                    if not mob_allowed:
                        _release_submission(session)
                        return {
                            "reply": "Too many submissions associated with this mobile number. Please wait a few minutes.",
                            "sessionId": session["sessionId"],
                            "step": "confirm",
                            "method": "complaint_flow",
                            "quickReplies": ["Submit", "Cancel"],
                        }

            existing = complaints().find_one(
                {"_chatbotSessionId": session["sessionId"]}, {"_id": 0}
            )
            if existing:
                return _finish_session(session, existing, language)

            category = draft.get("category", "Other")
            location_label = (
                f"{draft.get('lab', '')} - {draft.get('systemNumber', '')}"
                if category == "Computer/Lab"
                else draft.get("location", "")
            )
            payload = {
                "title": f"{category} issue at {location_label}"[:200],
                "description": draft.get("description", ""),
                "category": category,
                "lab": draft.get("lab", ""),
                "systemNumber": draft.get("systemNumber", ""),
                "location": {
                    "address": draft.get("location") or location_label,
                    "latitude": 29.99965,
                    "longitude": 78.1946,
                },
                "submitter": {
                    "name": draft.get("name") or (user.get("name") if user else "Guest"),
                    "scholarId": draft.get("scholarId") or (user.get("userId") if user else ""),
                    "email": draft.get("email") or (user.get("email") if user else ""),
                    "mobile": draft.get("mobile") or (user.get("mobile") if user else ""),
                },
            }

            try:
                created = complaint_service.create_complaint(
                    payload,
                    user=user,
                    idempotency_key=session["sessionId"],
                )
                if not created or not created.get("id"):
                    raise RuntimeError("Complaint creation returned no reference.")
            except DuplicateKeyError:
                created = complaints().find_one(
                    {"_chatbotSessionId": session["sessionId"]}, {"_id": 0}
                )
                if not created:
                    _release_submission(session)
                    raise
                return _finish_session(session, created, language)
            except Exception:
                _release_submission(session)
                raise

            try:
                notification_service.notify_admins(
                    f"New complaint {created['id']}",
                    f"New {created['category']} complaint assigned to {created['department']}.",
                    created["id"],
                )
            except Exception:
                logger.exception("Failed to notify administrators for complaint %s", created["id"])
            _finish_session(session, created, language)
            return _done_response(session, created, newly_created=True, language=language)

        elif action_val == "edit" or message_text.lower() in ("edit", "change", "modify", "बदलें"):
            session["state"] = STATE_EDITING
            session["step"] = "edit"
            save_session(session)
            if language == "hi":
                edit_buttons = ["श्रेणी", "स्थान / लैब", "विवरण", "स्कॉलर आईडी", "नाम", "मोबाइल", "ईमेल", "रद्द करें"]
                edit_prompt = "आप कौन सा विवरण बदलना चाहते हैं?"
            elif language == "hinglish":
                edit_buttons = ["Category", "Location / Lab", "Description", "Scholar ID", "Name", "Mobile", "Email", "Cancel"]
                edit_prompt = "Kaunsi detail badalna chahte hain?"
            else:
                edit_buttons = ["Category", "Location / Lab", "Description", "Scholar ID", "Name", "Mobile", "Email", "Cancel"]
                edit_prompt = "Which detail would you like to edit?"

            return {
                "reply": edit_prompt,
                "sessionId": session["sessionId"],
                "step": "edit",
                "method": "complaint_flow",
                "quickReplies": edit_buttons,
                "draft": draft,
            }
        else:
            save_session(session)
            confirmation_replies = {
                "hi": "शिकायत अभी जमा नहीं हुई है। जमा करने के लिए 'हाँ' कहें, जानकारी बदलने के लिए 'बदलें' कहें या ड्राफ्ट रद्द करने के लिए 'रद्द करें' कहें।",
                "hinglish": "Complaint abhi submit nahi hui hai. Submit karne ke liye 'Submit' boliye, details badalne ke liye 'Edit' ya draft cancel karne ke liye 'Cancel' boliye.",
                "en": "Your complaint has not been submitted. Say 'Submit' to submit, 'Edit' to change details, or 'Cancel' to discard the draft.",
            }
            buttons = {
                "hi": ["दर्ज करें", "बदलें", "रद्द करें"],
                "hinglish": ["Submit", "Edit", "Cancel"],
                "en": ["Submit", "Edit", "Cancel"],
            }[language]
            return {
                "reply": confirmation_replies[language],
                "sessionId": session["sessionId"],
                "step": "confirm",
                "method": "complaint_flow",
                "quickReplies": buttons,
                "draft": draft,
            }

    # 11. Active Slot Collection State
    if state == STATE_COLLECTING:
        if session.get("step") == "choose_identity_field":
            current_step = "choose_identity_field"
        else:
            current_step = get_first_missing_slot(draft, user, config)
        if current_step == "confirm":
            session["step"] = current_step
            session["state"] = STATE_CONFIRMING_SUBMISSION
            save_session(session)
            prompt, quick_replies = prompt_for_slot(current_step, draft, language, user, config)
            return {
                "reply": prompt,
                "sessionId": session["sessionId"],
                "step": current_step,
                "method": "complaint_flow",
                "quickReplies": quick_replies,
                "draft": draft,
            }
        session["step"] = current_step

        # Help request handling (Requirement C)
        if message_text.lower() in ("help", "सहायता", "madad"):
            session["invalid_attempts"] = 0
            prompt, qr = prompt_for_slot(current_step, draft, language, user, config)
            help_hints = {
                "category": {
                    "hi": "कैंपस में समस्या किस तरह की है? जैसे पानी, बिजली, कंप्यूटर आदि। कृपया नीचे दिए गए विकल्पों में से चुनें।",
                    "hinglish": "Campus mein problem kis type ki hai? Jaise water, electricity, computer lab etc. Neeche diye options mein se choose karein.",
                    "en": "Please choose the area of your problem, such as Water, Electricity, Computer/Lab, or Building.",
                },
                "lab": {
                    "hi": "कृपया BCA Lab, BIT Lab या MCA Lab में से चुनें।",
                    "hinglish": "Please BCA Lab, BIT Lab ya MCA Lab mein se select karein.",
                    "en": "Please choose between BCA Lab, BIT Lab, or MCA Lab.",
                },
                "systemNumber": {
                    "hi": "कंप्यूटर पर लगा लेबल या नंबर लिखें, जैसे 'System 04' या 'PC-12'।",
                    "hinglish": "Workstation ya computer ka label batayein, jaise 'System 04' ya 'PC-12'.",
                    "en": "Enter the workstation label or number on the machine, e.g. 'System 04'.",
                },
                "location": {
                    "hi": "समस्या किस भवन या कमरे में है, जैसे 'Gayatri Bhavan, Room 204'।",
                    "hinglish": "Problem kis building ya room mein hai, jaise 'Gayatri Bhavan, Room 204'.",
                    "en": "Enter the building, room, or landmark where the issue is located.",
                },
                "description": {
                    "hi": "समस्या के बारे में कम से कम 25 अक्षर लिखें, जैसे 'पंखा बहुत आवाज कर रहा है और घूम नहीं रहा'।",
                    "hinglish": "Problem ka poora detail kam se kam 25 characters mein likhein.",
                    "en": "Please describe what is broken or malfunctioning in at least 25 characters.",
                },
                "scholarId": {
                    "hi": "अपना छात्र/स्कॉलर आईडी दर्ज करें, जैसे 'MCA/2024/018'।",
                    "hinglish": "Apna Scholar ID enter karein, jaise 'MCA/2024/018'.",
                    "en": "Enter your student Scholar ID, such as 'MCA/2024/018'.",
                },
                "name": {
                    "hi": "अपना पूरा नाम लिखें, जैसे 'रोहन वर्मा'।",
                    "hinglish": "Apna poora naam likhein, jaise 'Rohan Verma'.",
                    "en": "Enter your full name (at least 3 characters).",
                },
                "mobile": {
                    "hi": "अपना 10 अंकों का मोबाइल नंबर लिखें, जैसे '9876543210'।",
                    "hinglish": "Apna 10-digit mobile number enter karein, jaise '9876543210'.",
                    "en": "Enter your 10-digit Indian mobile number, e.g. '9876543210'.",
                },
                "email": {
                    "hi": "अपना ईमेल पता दर्ज करें, जैसे 'student@dsvv.ac.in'।",
                    "hinglish": "Apna email address enter karein, jaise 'student@example.com'.",
                    "en": "Enter a valid email address for notifications, e.g. 'student@example.com'.",
                },
            }
            hint = help_hints.get(current_step, {}).get(language, "Please answer the question below:")
            return {
                "reply": f"{hint}\n\n{prompt}",
                "sessionId": session["sessionId"],
                "step": current_step,
                "method": "complaint_flow",
                "quickReplies": qr,
                "draft": draft,
            }

        # Guard: Free-text inputs must never validate chip labels or command words as answers (Requirement B)
        if current_step in ("systemNumber", "description", "scholarId", "name", "mobile", "email"):
            if is_chip_or_command(message_text):
                prompt, qr = prompt_for_slot(current_step, draft, language, user, config)
                err_msg = {
                    "hi": "कृपया इस चरण के लिए माँगी गई जानकारी दर्ज करें।",
                    "hinglish": "Kripya is step ke liye required information enter karein.",
                    "en": "Please enter the requested information for this step.",
                }[language]
                return {
                    "reply": f"{err_msg}\n\n{prompt}",
                    "sessionId": session["sessionId"],
                    "step": current_step,
                    "method": "complaint_flow",
                    "quickReplies": qr,
                    "draft": draft,
                }

        # Validate and store incoming answer for the current slot
        if current_step == "category":
            matched = next((c for c in ALLOWED_CATEGORIES if c.lower() == message_text.lower()), None)
            if not matched:
                lower_category = message_text.strip().lower()
                matched = next(
                    (
                        cat for cat, aliases in CATEGORY_ALIASES.items()
                        if lower_category in aliases or lower_category == cat.lower()
                    ),
                    None,
                )
            if not matched:
                attempts = session.get("invalid_attempts", 0) + 1
                session["invalid_attempts"] = attempts
                save_session(session)
                if attempts >= 3:
                    help_text = {
                        "hi": "ऐसा लगता है कि आपको इस चरण में समस्या आ रही है। क्या आपको सहायता (Help) चाहिए या शिकायत रद्द (Cancel) करनी है?",
                        "hinglish": "Lagta hai is step mein dikkat aa rahi hai. Kya aapko Help chahiye ya Cancel karna chahte hain?",
                        "en": "It looks like you're having trouble with this step. Would you like Help or do you want to Cancel?",
                    }[language]
                    btns = {
                        "hi": ["Help", "रद्द करें", "पीछे"],
                        "hinglish": ["Help", "Cancel", "Back"],
                        "en": ["Help", "Cancel", "Back"],
                    }[language]
                    return {
                        "reply": help_text,
                        "sessionId": session["sessionId"],
                        "step": "category",
                        "method": "complaint_flow",
                        "quickReplies": btns,
                        "draft": draft,
                    }
                invalid_replies = {
                    "hi": f"'{message_text}' समझ नहीं आया। कृपया नीचे दिए विकल्पों में से चुनें (उदाहरण: Water, Electricity):",
                    "hinglish": f"'{message_text}' samajh nahi aayi. Neeche diye options mein se choose karein (jaise: Water, Electricity):",
                    "en": f"'{message_text}' is not a recognised category. Please select from (e.g. Water, Electricity):",
                }
                return {
                    "reply": invalid_replies[language],
                    "sessionId": session["sessionId"],
                    "step": "category",
                    "method": "complaint_flow",
                    "quickReplies": ALLOWED_CATEGORIES + ["Cancel"],
                    "draft": draft,
                }
            draft["category"] = matched
            session["step_history"].append("category")
            session["invalid_attempts"] = 0

        elif current_step == "lab":
            matched = next((lab for lab in ALLOWED_LABS if lab.lower() == message_text.lower()), None)
            if not matched:
                attempts = session.get("invalid_attempts", 0) + 1
                session["invalid_attempts"] = attempts
                save_session(session)
                if attempts >= 3:
                    help_text = {
                        "hi": "क्या आपको सहायता (Help) चाहिए या शिकायत रद्द (Cancel) करनी है?",
                        "hinglish": "Kya aapko Help chahiye ya Cancel karna chahte hain?",
                        "en": "Would you like Help or do you want to Cancel?",
                    }[language]
                    btns = ["Help", "Cancel", "Back"]
                    return {"reply": help_text, "sessionId": session["sessionId"], "step": "lab", "method": "complaint_flow", "quickReplies": btns, "draft": draft}
                return {
                    "reply": "Please select a valid computer lab (BCA Lab, BIT Lab, or MCA Lab):",
                    "sessionId": session["sessionId"],
                    "step": "lab",
                    "method": "complaint_flow",
                    "quickReplies": ALLOWED_LABS + ["Back", "Cancel"],
                    "draft": draft,
                }
            draft["lab"] = matched
            session["step_history"].append("lab")
            session["invalid_attempts"] = 0

        elif current_step == "systemNumber":
            val = message_text.strip()
            if not val or len(val) > 50:
                attempts = session.get("invalid_attempts", 0) + 1
                session["invalid_attempts"] = attempts
                save_session(session)
                if attempts >= 3:
                    btns = ["Help", "Cancel", "Back"]
                    return {"reply": "Would you like Help or do you want to Cancel?", "sessionId": session["sessionId"], "step": "systemNumber", "method": "complaint_flow", "quickReplies": btns, "draft": draft}
                return {
                    "reply": "Please enter a valid workstation or system label (1 to 50 characters, e.g. System 04):",
                    "sessionId": session["sessionId"],
                    "step": "systemNumber",
                    "method": "complaint_flow",
                    "quickReplies": ["Back", "Cancel"],
                    "draft": draft,
                }
            draft["systemNumber"] = val
            session["step_history"].append("systemNumber")
            session["invalid_attempts"] = 0

        elif current_step == "location":
            val = message_text.strip()
            if len(val) < 3 or len(val) > 200:
                attempts = session.get("invalid_attempts", 0) + 1
                session["invalid_attempts"] = attempts
                save_session(session)
                if attempts >= 3:
                    btns = ["Help", "Cancel", "Back"]
                    return {"reply": "Would you like Help or do you want to Cancel?", "sessionId": session["sessionId"], "step": "location", "method": "complaint_flow", "quickReplies": btns, "draft": draft}
                return {
                    "reply": "Please enter a campus landmark, room, or building name (at least 3 characters, e.g. Gayatri Bhavan):",
                    "sessionId": session["sessionId"],
                    "step": "location",
                    "method": "complaint_flow",
                    "quickReplies": CANONICAL_LOCATIONS + ["Back", "Cancel"],
                    "draft": draft,
                }
            draft["location"] = val
            session["step_history"].append("location")
            session["invalid_attempts"] = 0

        elif current_step == "description":
            val = message_text.strip()
            if len(val) < 25:
                attempts = session.get("invalid_attempts", 0) + 1
                session["invalid_attempts"] = attempts
                save_session(session)
                if attempts >= 3:
                    btns = ["Help", "Cancel", "Back"]
                    return {"reply": "Would you like Help or do you want to Cancel?", "sessionId": session["sessionId"], "step": "description", "method": "complaint_flow", "quickReplies": btns, "draft": draft}
                return {
                    "reply": f"The description is too short ({len(val)} characters). Please provide at least 25 characters (e.g. 'Ceiling fan in room 204 is making loud noise and not spinning'):",
                    "sessionId": session["sessionId"],
                    "step": "description",
                    "method": "complaint_flow",
                    "quickReplies": ["Back", "Cancel"],
                    "draft": draft,
                }
            draft["description"] = val
            session["step_history"].append("description")
            session["invalid_attempts"] = 0

        elif current_step == "scholarId":
            val = message_text.strip()
            if len(val) < 3 or len(val) > 40:
                attempts = session.get("invalid_attempts", 0) + 1
                session["invalid_attempts"] = attempts
                save_session(session)
                if attempts >= 3:
                    btns = ["Help", "Cancel", "Back"]
                    return {"reply": "Would you like Help or do you want to Cancel?", "sessionId": session["sessionId"], "step": "scholarId", "method": "complaint_flow", "quickReplies": btns, "draft": draft}
                return {
                    "reply": "Please enter a valid Scholar ID / Student ID (at least 3 characters, e.g. MCA/2024/018):",
                    "sessionId": session["sessionId"],
                    "step": "scholarId",
                    "method": "complaint_flow",
                    "quickReplies": ["Back", "Cancel"],
                    "draft": draft,
                }

            # Check if user is logged in
            if user and user.get("id"):
                expected_ids = {
                    (user.get("userId") or "").strip().lower(),
                    (user.get("scholarId") or "").strip().lower(),
                    (user.get("id") or "").strip().lower(),
                } - {""}
                if val.lower() not in expected_ids:
                    attempts = session.get("invalid_attempts", 0) + 1
                    session["invalid_attempts"] = attempts
                    save_session(session)
                    if attempts >= 3:
                        btns = ["Help", "Cancel", "Back"]
                        return {"reply": "Would you like Help or do you want to Cancel?", "sessionId": session["sessionId"], "step": "scholarId", "method": "complaint_flow", "quickReplies": btns, "draft": draft}
                    acc_label = user.get("userId") or user.get("id")
                    mismatch_replies = {
                        "hi": f"स्कॉलर आईडी '{val}' आपके लॉग-इन खाते ({acc_label}) से मेल नहीं खाता। कृपया अपना स्कॉलर आईडी दर्ज करें:",
                        "hinglish": f"Scholar ID '{val}' aapke logged-in account ({acc_label}) se match nahi karta. Kripya apna Scholar ID enter karein:",
                        "en": f"The Scholar ID '{val}' does not match your signed-in account ({acc_label}). Please enter your own Scholar ID:",
                    }
                    return {
                        "reply": mismatch_replies[language],
                        "sessionId": session["sessionId"],
                        "step": "scholarId",
                        "method": "complaint_flow",
                        "quickReplies": ["Back", "Cancel"],
                        "draft": draft,
                    }
                # Matches logged-in account
                draft["scholarId"] = user.get("userId") or user.get("id") or val
                draft["isRegistered"] = True
                draft["name"] = user.get("name", "")
                draft["email"] = user.get("email", "")
                acc_mob = (user.get("mobile") or "").strip()
                if is_mobile(acc_mob):
                    draft["mobile"] = re.sub(r"\D", "", acc_mob)[-10:]
                else:
                    draft.pop("mobile", None)
            else:
                # Guest user
                draft["scholarId"] = val
                ask_id = config.get("CHATBOT_ASK_IDENTITY", True) if config else True
                reg_user = users().find_one({"$or": [{"userId": val}, {"id": val}]}) if not ask_id else None
                if reg_user and not ask_id:
                    draft["isRegistered"] = True
                    draft["name"] = reg_user.get("name", "")
                    draft["email"] = reg_user.get("email", "")
                    draft["mobile"] = reg_user.get("mobile", "") or "9876543210"
                else:
                    draft["isRegistered"] = False
                    draft["identityVerified"] = False
                    draft.pop("name", None)
                    draft.pop("mobile", None)
                    draft.pop("email", None)

            session["step_history"].append("scholarId")
            session["invalid_attempts"] = 0

        elif current_step == "confirm_identity":
            low = message_text.strip().lower()
            if (
                action_val in ("yes", "haan", "confirm")
                or any(w in low for w in ("haan", "yes", "sahi", "theek", "confirm", "ok", "correct", "हाँ", "विवरण सही"))
            ):
                draft["identityConfirmed"] = True
                session["step_history"].append("confirm_identity")
                session["invalid_attempts"] = 0
            elif any(w in low for w in ("badlein", "change", "edit", "badal", "modify", "बदलें")):
                session["step"] = "choose_identity_field"
                save_session(session)
                choose_text = {
                    "hi": "कौन सा विवरण बदलना चाहते हैं?",
                    "hinglish": "Kaunsi detail badalna chahte hain?",
                    "en": "Which detail would you like to change for this complaint?",
                }[language]
                choose_buttons = {
                    "hi": ["नाम", "मोबाइल", "ईमेल", "रद्द करें"],
                    "hinglish": ["Name", "Mobile", "Email", "Cancel"],
                    "en": ["Name", "Mobile", "Email", "Cancel"],
                }[language]
                return {
                    "reply": choose_text,
                    "sessionId": session["sessionId"],
                    "step": "choose_identity_field",
                    "method": "complaint_flow",
                    "quickReplies": choose_buttons,
                    "draft": draft,
                }
            else:
                prompt, qr = prompt_for_slot("confirm_identity", draft, language, user, config)
                return {
                    "reply": prompt,
                    "sessionId": session["sessionId"],
                    "step": "confirm_identity",
                    "method": "complaint_flow",
                    "quickReplies": qr,
                    "draft": draft,
                }

        elif current_step == "choose_identity_field":
            low = message_text.strip().lower()
            if "name" in low or "नाम" in low:
                draft.pop("name", None)
                draft.pop("identityConfirmed", None)
                session["step"] = "name"
                session["invalid_attempts"] = 0
                save_session(session)
                prompt, qr = prompt_for_slot("name", draft, language, user, config)
                return {"reply": prompt, "sessionId": session["sessionId"], "step": "name", "method": "complaint_flow", "quickReplies": qr, "draft": draft}
            elif "mobile" in low or "phone" in low or "मोबाइल" in low:
                draft.pop("mobile", None)
                draft.pop("identityConfirmed", None)
                session["step"] = "mobile"
                session["invalid_attempts"] = 0
                save_session(session)
                prompt, qr = prompt_for_slot("mobile", draft, language, user, config)
                return {"reply": prompt, "sessionId": session["sessionId"], "step": "mobile", "method": "complaint_flow", "quickReplies": qr, "draft": draft}
            elif "email" in low or "ईमेल" in low:
                draft.pop("email", None)
                draft.pop("identityConfirmed", None)
                session["step"] = "email"
                session["invalid_attempts"] = 0
                save_session(session)
                prompt, qr = prompt_for_slot("email", draft, language, user, config)
                return {"reply": prompt, "sessionId": session["sessionId"], "step": "email", "method": "complaint_flow", "quickReplies": qr, "draft": draft}
            else:
                prompt, qr = prompt_for_slot("confirm_identity", draft, language, user, config)
                return {"reply": prompt, "sessionId": session["sessionId"], "step": "confirm_identity", "method": "complaint_flow", "quickReplies": qr, "draft": draft}

        elif current_step == "name":
            val = message_text.strip()
            if len(val) < 3 or len(val) > 100:
                attempts = session.get("invalid_attempts", 0) + 1
                session["invalid_attempts"] = attempts
                save_session(session)
                if attempts >= 3:
                    btns = ["Help", "Cancel", "Back"]
                    return {"reply": "Would you like Help or do you want to Cancel?", "sessionId": session["sessionId"], "step": "name", "method": "complaint_flow", "quickReplies": btns, "draft": draft}
                return {
                    "reply": "Please enter your full name (at least 3 characters, e.g. Rohan Verma):",
                    "sessionId": session["sessionId"],
                    "step": "name",
                    "method": "complaint_flow",
                    "quickReplies": ["Back", "Cancel"],
                    "draft": draft,
                }
            draft["name"] = val
            session["step_history"].append("name")
            session["invalid_attempts"] = 0

        elif current_step == "mobile":
            val = message_text.strip()
            if not is_mobile(val):
                attempts = session.get("invalid_attempts", 0) + 1
                session["invalid_attempts"] = attempts
                save_session(session)
                if attempts >= 3:
                    help_text = {
                        "hi": "ऐसा लगता है कि आपको इस चरण में समस्या आ रही है। क्या आपको सहायता (Help) चाहिए या शिकायत रद्द (Cancel) करनी है?",
                        "hinglish": "Lagta hai is step mein dikkat aa rahi hai. Kya aapko Help chahiye ya Cancel karna chahte hain?",
                        "en": "It looks like you're having trouble with this step. Would you like Help or do you want to Cancel?",
                    }[language]
                    btns = {
                        "hi": ["Help", "रद्द करें", "पीछे"],
                        "hinglish": ["Help", "Cancel", "Back"],
                        "en": ["Help", "Cancel", "Back"],
                    }[language]
                    return {
                        "reply": help_text,
                        "sessionId": session["sessionId"],
                        "step": "mobile",
                        "method": "complaint_flow",
                        "quickReplies": btns,
                        "draft": draft,
                    }
                err_replies = {
                    "hi": "कृपया 10 अंकों का मान्य भारतीय मोबाइल नंबर दर्ज करें (उदाहरण: 9876543210)।",
                    "hinglish": "Kripya valid 10-digit Indian mobile number batayein (jaise: 9876543210).",
                    "en": "Please enter a valid 10-digit Indian mobile number (e.g. 9876543210):",
                }
                return {
                    "reply": err_replies[language],
                    "sessionId": session["sessionId"],
                    "step": "mobile",
                    "method": "complaint_flow",
                    "quickReplies": ["Back", "Cancel"],
                    "draft": draft,
                }
            clean_digits = re.sub(r"\D", "", val)[-10:]
            draft["mobile"] = clean_digits
            session["step_history"].append("mobile")
            session["invalid_attempts"] = 0

        elif current_step == "email":
            val = message_text.strip().lower()
            if not is_email(val):
                attempts = session.get("invalid_attempts", 0) + 1
                session["invalid_attempts"] = attempts
                save_session(session)
                if attempts >= 3:
                    btns = ["Help", "Cancel", "Back"]
                    return {"reply": "Would you like Help or do you want to Cancel?", "sessionId": session["sessionId"], "step": "email", "method": "complaint_flow", "quickReplies": btns, "draft": draft}
                return {
                    "reply": "Please enter a valid email address (e.g. name@example.com):",
                    "sessionId": session["sessionId"],
                    "step": "email",
                    "method": "complaint_flow",
                    "quickReplies": ["Back", "Cancel"],
                    "draft": draft,
                }
            draft["email"] = val
            session["step_history"].append("email")
            session["invalid_attempts"] = 0

        # Advance to the first unfilled slot
        next_slot = get_first_missing_slot(draft, user, config)
        session["step"] = next_slot
        if next_slot == "confirm":
            session["state"] = STATE_CONFIRMING_SUBMISSION
        save_session(session)

        prompt, qr = prompt_for_slot(next_slot, draft, language, user, config)
        return {
            "reply": prompt,
            "sessionId": session["sessionId"],
            "step": next_slot,
            "method": "complaint_flow",
            "quickReplies": qr,
            "draft": draft,
        }

    # 12. Idle State: Check for Fast Path or Explicit "Raise Complaint" intent
    lower_text = message_text.lower()
    is_complaint_intent = (
        action_val in ("raise_complaint", "new_complaint", "create")
        or not _how_to_question(lower_text)
        and any(phrase in lower_text for phrase in (
            "raise a complaint", "raise complaint", "new complaint",
            "file a complaint", "lodge complaint",
        ))
        or (
            not _how_to_question(lower_text)
            and any(phrase in lower_text for phrase in (
                "शिकायत दर्ज करें", "नई शिकायत दर्ज", "shikayat darj karein",
                "shikayat darj karo", "complaint darj karo",
                "मुझे शिकायत दर्ज करनी है",
                "mujhe complaint register karni hai",
                "i want to register a complaint",
            ))
        )
    )

    if is_complaint_intent:
        session["draft"] = {}
        session["step_history"] = []
        session["invalid_attempts"] = 0
        session["state"] = STATE_COLLECTING
        session["step"] = "category"
        save_session(session)
        prompt, qr = prompt_for_slot("category", session["draft"], language, user, config)
        introductions = {
            "hi": f"मैं कुछ आसान चरणों में शिकायत दर्ज करने में मदद करूँगा।\n\n{prompt}",
            "hinglish": f"Main kuch simple steps mein complaint file karne mein help karunga.\n\n{prompt}",
            "en": f"I can guide you to file your complaint in just a few quick steps.\n\n{prompt}",
        }
        return {
            "reply": introductions[language],
            "sessionId": session["sessionId"],
            "step": "category",
            "method": "complaint_flow",
            "quickReplies": qr,
            "draft": session["draft"],
        }

    # Fast path only for problem reports
    if _problem_report_intent(message_text):
        fast_path = detect_fast_path(message_text)
        session["draft"] = {}
        session["step_history"] = []
        session["invalid_attempts"] = 0
        if message_text:
            session["draft"]["description"] = message_text
        if fast_path:
            proposed_category = fast_path["category"]
            session["draft"]["proposedCategory"] = proposed_category
            session["state"] = STATE_CONFIRMING_FAST_PATH
            session["step"] = "confirm_fast_path"
            save_session(session)
            confirmation = {
                "hi": (
                    f"यह {proposed_category} ({fast_path['department']}) की समस्या लगती है। "
                    f"क्या आप इसकी शिकायत दर्ज करना चाहते हैं?"
                ),
                "hinglish": (
                    f"Yeh {proposed_category} ({fast_path['department']}) ka issue lagta hai. "
                    "Kya aap iski complaint register karna chahenge?"
                ),
                "en": (
                    f"It looks like you are describing an issue regarding "
                    f"{proposed_category} ({fast_path['department']}). "
                    f"Would you like to raise a complaint for {proposed_category}?"
                ),
            }[language]
            btns = {
                "hi": [f"हाँ, {proposed_category}", "दूसरी श्रेणी चुनें", "रद्द करें"],
                "hinglish": [f"Yes, {proposed_category}", "Choose other category", "Cancel"],
                "en": [f"Yes, {proposed_category}", "Choose other category", "Cancel"],
            }[language]
            return {
                "reply": confirmation,
                "sessionId": session["sessionId"],
                "step": "confirm_fast_path",
                "method": "complaint_flow",
                "quickReplies": btns,
                "draft": session["draft"],
            }
        session["state"] = STATE_COLLECTING
        session["step"] = "category"
        save_session(session)
        start_replies = {
            "hi": "मैं शिकायत दर्ज करने में मदद कर सकता हूँ। कृपया category चुनें:",
            "hinglish": "Main complaint file karne mein help karunga. Complaint category choose karein:",
            "en": "I can help file that. Please choose the complaint category:",
        }
        return {
            "reply": start_replies[language],
            "sessionId": session["sessionId"],
            "step": "category",
            "method": "complaint_flow",
            "quickReplies": ALLOWED_CATEGORIES + ["Cancel"],
            "draft": session["draft"],
        }

    # 13. Default: Fallback to grounded FAQ or provider
    history = session.get("aiHistory", [])
    if not isinstance(history, list):
        history = []
    faq_answer, method = answer(message_text, config, history, language)
    starter_replies = {
        "hi": ["शिकायत दर्ज करें", "शिकायत ट्रैक करें", "सहायता और FAQ"],
        "hinglish": ["Raise a complaint", "Track a complaint", "Help & FAQs"],
        "en": ["Raise a complaint", "Track a complaint", "Help & FAQs"],
    }[language]
    result = {
        "reply": faq_answer,
        "sessionId": session["sessionId"],
        "step": "idle",
        "method": method,
        "action": suggested_action(message_text),
        "quickReplies": starter_replies,
    }
    if method == "ai":
        safe_question = _ai_safe_text(message_text)
        history = [
            *history[-6:],
            {"role": "user", "content": safe_question},
            {"role": "assistant", "content": _ai_safe_text(faq_answer)},
        ]
        session["aiHistory"] = history
        result["source"] = "ai"
    else:
        has_api_key = bool(
            config.get("OPENAI_API_KEY") or config.get("CHATBOT_AI_API_KEY", "")
        )
        result["source"] = "local_faq"
        result["sourceNotice"] = (
            {
                "hi": "AI सेवा उपलब्ध नहीं है; यह जवाब built-in FAQ से है।",
                "hinglish": "AI service abhi available nahi hai; yeh built-in FAQ ka jawab hai.",
                "en": "The AI service is unavailable; this reply is from the built-in FAQ.",
            }[language]
            if has_api_key
            else {
                "hi": "AI सेवा configure नहीं है; यह जवाब built-in FAQ से है।",
                "hinglish": "AI service configure nahi hai; yeh built-in FAQ ka jawab hai.",
                "en": "The AI service is not configured; this reply is from the built-in FAQ.",
            }[language]
        )
    save_session(session)
    return result
