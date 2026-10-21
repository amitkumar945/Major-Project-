# Text complaint assistant

The floating web assistant is a client for the same Flask API used by future
clients. It can answer local FAQs, guide an optional-authenticated user through
complaint entry, and look up status only when the server authorizes the signed-in
user. It does not create complaints in a separate collection or bypass the
normal complaint service.

## Architecture

- `frontend/assets/js/components/chatbot.js` mounts the shared floating widget
  on public, authentication, and portal pages. It sends text to the API using
  the frontend's existing `request()` client.
- `backend/routes/chatbot_routes.py` validates request shape and limits, applies
  optional JWT authentication, and returns the standard API response envelope.
- `backend/services/chatbot_service.py` owns the FAQ, fast path, server-side
  conversation state, slot validation, and guest submission limits.
- `backend/database.py` provides the MongoDB `chatbot_sessions` collection.
  Session ids have a unique index and `expiresAt` has a MongoDB TTL index.
- `backend/services/complaint_service.py` creates the complaint through the
  same classification, priority, assignment, audit, and notification path used
  by the normal form. `_chatbotSessionId` has a unique sparse index to make
  retries idempotent.
- `backend/services/notification_service.py` skips submitter notifications for
  guests and can send a best-effort in-app notice to active admins.

Complaint and chat data use the existing camelCase document/API fields. Guest
complaints have a `submittedBy` snapshot with `type: "guest"`, `id: null`,
`scholarId`, `name`, `mobile`, `email`, and `isVerified: false`. Registered
complaints retain their account id and receive a registered submitter snapshot.
Public tracking masks guest identity as `Guest` and excludes contact details
and Scholar ID; registered tracking names remain unchanged.

## Endpoint contract

`POST /api/chatbot/message` accepts JSON and an optional `Authorization:
Bearer <JWT>` header.

Request:

```json
{
  "message": "Water",
  "sessionId": "optional-session-id",
  "action": "optional-action"
}
```

| Field | Required | Validation |
|---|---|---|
| `message` | Yes | String with non-whitespace content; at most 1,200 characters |
| `sessionId` | No | String of at most 64 characters; returned by the API |
| `action` | No | String of at most 40 characters |

The request body is limited by `CHATBOT_MAX_REQUEST_BYTES` (8 KiB by default).
The response uses the normal `{ "success", "message", "data" }` envelope.
`data` normally contains:

| Field | Meaning |
|---|---|
| `reply` | Assistant prompt, answer, or server-confirmed result |
| `sessionId` | Opaque id for the current server-side session |
| `step` | Current step, such as `category`, `lab`, `description`, `confirm`, or `done` |
| `method` | `complaint_flow`, `faq`, `ai`, or `verified_record` |
| `quickReplies` | Optional list of buttons for constrained answers |
| `draft` | Optional active complaint fields; shown only in the active conversation |
| `created` | `true` only for a newly created complaint |
| `complaint` | On completion: `id`, `reference`, `department`, `priority`, and `status` |

Successful turns that do not create a complaint return HTTP 200. A newly
persisted complaint returns HTTP 201 with `created: true` and its reference.
An idempotent retry returns HTTP 200 with the same reference and
`created: false`. The widget displays a success result only when the response
contains a reference and the status/`created` pair agrees with that contract.
Validation errors use the standard error envelope; oversized requests return
HTTP 413. A failed create leaves the server-side draft available for retry.

## Conversation and session behavior

The complaint flow asks for the first missing field in this order:

1. Category.
2. Lab and system number for `Computer/Lab`; otherwise a campus location.
3. Problem description (at least 25 characters).
4. Scholar ID for a guest; logged-in users skip this question.
5. Name, Indian mobile number, and email when the Scholar ID is unregistered.
6. Summary with Submit, Edit, and Cancel.
7. Reference id and routed department after a successful create.

Every answer is validated on the server. Categories and labs must match the
backend's allowed choices. A free-form location must be 3–200 characters, a
system label 1–50 characters, a name 3–100 characters, a mobile must pass the
existing Indian mobile validator, and an email must pass the existing email
validator. Invalid answers do not advance the current step.

When an account is used, its verified JWT identity is authoritative. A guest
may enter a Scholar ID: if it matches an active student/staff account, contact
questions are skipped and the account's contact snapshot is used; otherwise
the user supplies their details and the record is marked unverified. This does
not create an account or allow the guest to access private complaint history.

Sessions are stored in MongoDB, use unguessable random ids, are bound to a
signed-in user when applicable, and expire after 30 minutes of inactivity. The
browser keeps the id in tab-scoped `sessionStorage`; the server remains the
source of truth. Submitted sessions cannot be edited or cancelled; choosing
“Raise another complaint” starts a new session. A unique complaint index and
an atomic submission claim ensure retries do not create duplicate complaints.

The fast path reuses `ai.classifier.classify_department()`. Clear problem
reports with sufficient classifier confidence are confirmed once, then continue
at the first missing slot. Ambiguous reports keep their description and show
the category choices. The normal priority classifier is used at creation, so
urgent terms apply equally to chat and form submissions.

## Adding categories or keywords

1. Add a new supported complaint category and its default department mapping
   in `backend/constants.py`. This is the shared source used by normal
   complaint validation and the chatbot's allowed category list.
2. Add its department/category mapping and conversational aliases in
   `DEPT_TO_CATEGORY` and `CATEGORY_ALIASES` in
   `backend/services/chatbot_service.py` if it needs fast-path recognition.
3. Add English/Hinglish terms to the appropriate department entry in
   `DEPARTMENT_KEYWORDS` in `backend/ai/classifier.py`. The shared classifier
   scores these terms for both the normal form and chat.
4. Add safety-critical terms to `URGENT_KEYWORDS` in `backend/ai/priority.py`
   only when they should raise priority for both entry paths.
5. Add tests for the category validation, classifier mapping, fast path, and
   complaint creation. Keep the resulting category and department names
   consistent with the existing constants and seed data.

## Configuration and limits

| Setting | Default | Purpose |
|---|---:|---|
| `CHATBOT_MAX_REQUEST_BYTES` | `8192` | Maximum encoded request body |
| `RATE_LIMIT_CHATBOT` | `30` | Chat requests per client per window |
| `CHATBOT_RATE_WINDOW` | `60` seconds | General chatbot rate-limit window |
| `CHATBOT_SHARED_RATE_LIMIT` | `true` | Store chatbot and guest quotas in MongoDB for all workers |
| `CHATBOT_GUEST_RATE_WINDOW` | `300` seconds | Guest submission rate-limit window |
| `CHATBOT_GUEST_IP_LIMIT` | `15` | Guest submissions per peer IP per window |
| `CHATBOT_GUEST_MOBILE_LIMIT` | `5` | Guest submissions per normalized mobile per window |
| `OPENAI_API_KEY` | blank | Optional FAQ answer provider key; never sent to the browser |
| `OPENAI_MODEL` | `gpt-4o-mini` | Optional FAQ model |
| `OPENAI_BASE_URL` | OpenAI API URL | Optional provider base URL |
| `OPENAI_TIMEOUT` | `12` seconds | Provider request timeout |

`CHATBOT_AI_*` names remain supported as legacy OpenAI configuration aliases.
The FAQ falls back to a built-in local answer when the provider is absent or
fails. Complaint filing and authenticated status lookup are backend-controlled
and do not depend on the provider. User messages and contact details are not
written to application logs; provider history is redacted before storage or
transmission.

Chatbot and guest-submission limits use atomic MongoDB fixed-window counters
by default and are shared across workers. MongoDB expires old windows. If the
counter store has a transient error, the service logs the error type and falls
back to the process-local soft limit; other endpoint limits remain in process
memory. Guest complaints do not
have an account for the private “my complaints” view or account notifications;
they can use the public reference tracker, which excludes guest contact data.
The web chat supports browser speech recognition and spoken replies when the
browser provides Web Speech APIs; recognized text is reviewed before sending.
The chat does not support attachments, OTP verification, or a Flutter chat
screen.

## Manual test script

Start MongoDB, then run the Flask app from `backend/` using the repository's
configured environment. The app serves the frontend and API on the same origin:

```powershell
cd backend
..\.venv\Scripts\python.exe app.py
```

In a second PowerShell window, check health and obtain a student token from the
local demo account:

```powershell
$base = 'http://127.0.0.1:5000'
Invoke-RestMethod "$base/api/health"
$login = Invoke-RestMethod "$base/api/auth/login" -Method Post `
  -ContentType 'application/json' `
  -Body (@{ identifier = 'student@dsvv.ac.in'; password = 'student123' } | ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.data.token)" }
```

The following helper sends a turn and retains the returned session id:

```powershell
$sessionId = $null
function Send-Chat($message, $tokenHeaders = @{}, $action = $null) {
  $body = @{ message = $message }
  if ($script:sessionId) { $body.sessionId = $script:sessionId }
  if ($action) { $body.action = $action }
  $response = Invoke-RestMethod "$base/api/chatbot/message" -Method Post `
    -Headers $tokenHeaders -ContentType 'application/json' -Body ($body | ConvertTo-Json)
  $script:sessionId = $response.data.sessionId
  $response.data
}
```

Try a registered computer complaint:

```powershell
Send-Chat 'Raise a complaint' $headers
Send-Chat 'Computer/Lab' $headers
Send-Chat 'MCA Lab' $headers
Send-Chat 'System 14' $headers
Send-Chat 'The monitor display is flickering and turns off during lab practicals.' $headers
Send-Chat 'Submit' $headers 'submit'
```

For a guest run, clear `$sessionId` and call the helper without `$headers`.
Use Water, a campus location, a 25-character description, an unregistered
Scholar ID, a name, a 10-digit mobile, and an email; finish with Submit. Check
that the reply includes a reference only after HTTP 201, then open
`/track.html?id=<reference>` and confirm only the guest display name is shown.
The student/Admin and department-officer details are available through their
normal authenticated complaint pages. To verify idempotency, repeat Submit
with the same session id and confirm the HTTP 200 reply has the original
reference.
