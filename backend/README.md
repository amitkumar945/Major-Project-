# Grievance Management System — Flask + MongoDB Backend

The real backend for the DSVV Grievance Management System, serving the existing
HTML/CSS/JavaScript frontend in `../frontend`.

Authentication is genuine (bcrypt + JWT), all data lives in MongoDB, and the
frontend now talks to this API instead of its in-browser mock services.

---

## 1. Requirements

| Need | Version |
|---|---|
| Python | 3.10 or newer |
| MongoDB | 5.0 or newer, running locally |

---

## 2. Setup

```bash
cd backend
pip install -r requirements.txt
```

Create the environment file and put a real signing key in it:

```bash
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux

python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste that value after `JWT_SECRET_KEY=` in `.env`.

**The server refuses to start without it** — that is deliberate, so a
deployment can never run on a default, publicly-known key.

---

## 3. Running

```bash
python app.py
```

| URL | What it is |
|---|---|
| http://127.0.0.1:5000/ | The frontend, served by Flask |
| http://127.0.0.1:5000/api | The API |
| http://127.0.0.1:5000/api/health | Health check (also pings MongoDB) |

One server runs everything — no separate static server is needed. To run the
frontend separately instead (e.g. `python -m http.server 5500` inside
`frontend/`), set `SERVE_FRONTEND=false`; CORS is already configured for
`localhost:5500`.

On first start the four departments and the demo accounts are created
automatically. Seeding is idempotent — nothing is duplicated on restart.

### AI grievance assistant and complaint chat

The floating assistant is available on the public, sign-in, and role-based
portal pages. It answers grounded FAQs and can guide a registered student/staff
member or a guest through complaint creation. Complaint chat is not a parallel
creation path: `POST /api/chatbot/message` calls
`services.chatbot_service.handle_chat_message()`, which submits through
`services.complaint_service.create_complaint()` and therefore uses the same
classification, priority, department routing, officer assignment, assignment
history, notifications, audit logging, and validation as the complaint form.
Notification failure after creation does not discard the complaint or its
reference.

#### Endpoint contract

The endpoint accepts an optional JWT. A signed-in user is identified from the
verified token; guests do not need an account.

```json
{
  "message": "Water",
  "sessionId": "optional-session-id",
  "action": "optional-action"
}
```

`message` is required and limited to 1,200 characters. `sessionId` and `action`
are returned/used by the client across turns; supported actions include
`raise_complaint`, `submit`, `edit`, `cancel`, and `new`. The standard success
envelope contains `data.reply`, `data.sessionId`, `data.step`, optional
`data.quickReplies`, and, after creation, `data.complaint` with the reference
and routed department. A newly created complaint returns HTTP 201 with
`data.created: true` and a reference; an idempotent retry returns HTTP 200
with the same reference and `data.created: false`.

The state machine collects category, then lab and system number for
Computer/Lab or a campus location for other categories, a problem description,
and (for guests) Scholar ID and contact details. Registered Scholar IDs reuse
the account snapshot. Unregistered IDs create a complaint with a submitter
snapshot marked `userType: "Guest"` and `isVerified: false`; the account is not
created. Guest complaints appear in normal department and officer queues and
are labelled **Unverified guest** in admin/officer details. Public tracking
masks guest identity as `Guest` and excludes contact details and Scholar ID;
registered tracking keeps its existing display-name behavior.

Supported chatbot categories are Building, Water, Electricity, Computer/Lab,
Hostel, Classroom, and Other. Computer/Lab choices are BCA Lab, BIT Lab, and
MCA Lab. The location suggestions are examples only; any campus landmark or
room label of 3–200 characters is accepted. Update `constants.py` for complaint
categories/departments and `services/chatbot_service.py` for slot suggestions
and fast-path classification mappings/keywords. Urgent keywords belong in
`ai/priority.py` so the chatbot and normal complaint form share priority rules.

Sessions are stored in MongoDB with unguessable IDs and expire after 30 minutes
using both application checks and a TTL index. The web widget keeps the active
ID in tab-scoped `sessionStorage` so a page reload can resume the conversation.
Submitted sessions are immutable; retries return the existing complaint
reference and cannot create a second complaint. The complaint collection uses a
unique sparse `_chatbotSessionId` index for persistence-level idempotency.

#### Limits and OpenAI assistant

The endpoint allows 30 messages per client per 60 seconds by default. Configure
`RATE_LIMIT_CHATBOT` and `CHATBOT_RATE_WINDOW` to tune that limit. Requests are
limited to 8 KiB by default (`CHATBOT_MAX_REQUEST_BYTES`), and message text is
limited to 1,200 characters.
Guest complaint submissions additionally use the following environment
settings (defaults shown):

| Setting | Default | Meaning |
|---|---:|---|
| `CHATBOT_GUEST_RATE_WINDOW` | 300 | Guest submission window in seconds |
| `CHATBOT_GUEST_IP_LIMIT` | 15 | Guest submissions per client IP per window |
| `CHATBOT_GUEST_MOBILE_LIMIT` | 5 | Guest submissions per normalized mobile per window |

The limits use an in-process fixed-window counter, so they are per process and
reset on restart. Multi-worker or multi-instance deployments need a shared
rate-limit store (for example Redis) to enforce a global quota; Redis is not
currently part of this deployment. Client identity uses the WSGI peer address.
Forwarded headers are ignored unless `TRUSTED_PROXY_COUNT` is set to the number
of trusted proxies and the final trusted proxy overwrites `X-Forwarded-For`.
The Vercel adapter trusts one Vercel hop by default; Vercel documents that it
overwrites this header with the public requester IP. On other hosts, only
configure trusted proxies when the app cannot be reached directly around them.

The assistant uses the official OpenAI Python SDK and the Chat Completions API.
It defaults to `gpt-4o-mini`; conversation history is limited to recent FAQ
turns and redacted before storage and transmission. Complaint filing and
authenticated status lookup remain backend-controlled and are not delegated to
the model. API failures use a clearly labelled local FAQ response.

```dotenv
OPENAI_API_KEY=your-provider-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT=12
```

Set the key in `backend/.env` locally (never commit that file) or in the
deployment platform's encrypted environment/secret settings. Do not put it in
frontend files. `CHATBOT_AI_API_KEY`, `CHATBOT_AI_MODEL`,
`CHATBOT_AI_BASE_URL`, and `CHATBOT_AI_TIMEOUT` remain supported as legacy
aliases. If no key is configured or OpenAI returns an error (including invalid
key, exhausted quota, provider rate limit, or timeout), the endpoint returns
the existing local FAQ with a `source: "local_faq"` marker and an explanatory
notice; successful model answers are marked `source: "ai"`. The API key and
provider exception details are never included in responses.

### Demo accounts

| Role | Email | Password |
|---|---|---|
| Student | `student@dsvv.ac.in` | `student123` |
| Officer | `officer@dsvv.ac.in` | `officer123` |
| Admin | `admin@dsvv.ac.in` | `admin123` |

Other officers (`pankaj.semwal@`, `naveen.painuli@`, `anupam.kaushik@`) share
the officer password. Change these via `SEED_*_PASSWORD` before exposing the
system to a network.

---

## 4. Tests

```bash
python -m pytest tests/ -q
```

301 tests covering registration, login, JWT verification, role authorisation,
OTP, complaint creation, tracking, status flow, remarks, resolution, feedback,
reopen, file upload, department prediction, priority prediction, duplicate
detection, officer assignment, SLA escalation, analytics and audit logging —
plus invalid input and unauthorised access for each.

`tests/test_resilience.py` additionally proves the submission path survives a
failure in any supporting subsystem: a crash in the classifier, an unreachable
notifications collection or a failing audit write must never cost a user their
complaint.

Tests use a **separate database** (`grievance_management_test`), dropped at the
end of the run, so development data is never touched.

---

## 5. Project structure

```text
backend/
├── app.py                 application factory, CORS, error handlers
├── config.py              environment-driven configuration
├── constants.py           statuses, departments, priorities (mirrors the frontend)
├── database.py            MongoDB connection, collections, indexes
├── seed.py                departments + demo accounts (idempotent)
│
├── routes/                HTTP layer — one blueprint per resource
│   ├── auth_routes.py         register, login, OTP, profile, password
│   ├── complaint_routes.py    the complaint lifecycle
│   ├── ai_routes.py           classification, priority, duplicates, NLP, OCR
│   ├── officer_routes.py      directory, workload, assignment
│   ├── department_routes.py   master data + admin CRUD
│   ├── user_routes.py         student/staff directory
│   ├── notification_routes.py notification centre
│   ├── feedback_routes.py     ratings
│   ├── analytics_routes.py    every dashboard chart
│   ├── admin_routes.py        SLA control, audit log, settings
│   └── file_routes.py         authenticated file downloads
│
├── services/              business logic — no HTTP knowledge
│   ├── auth_service.py        bcrypt hashing, account creation
│   ├── otp_service.py         hashed, expiring codes
│   ├── complaint_service.py   lifecycle, timeline, permissions
│   ├── ai_service.py          orchestrates the ai/ modules
│   ├── assignment_service.py  workload-based officer selection
│   ├── notification_service.py
│   ├── escalation_service.py  SLA monitoring
│   ├── analytics_service.py   chart datasets
│   ├── department_service.py
│   ├── user_service.py
│   └── audit_service.py
│
├── ai/                    prediction modules (rule-based — see §7)
│   ├── nlp_processor.py       cleaning, tokenising, stemming, entities
│   ├── classifier.py          department prediction
│   ├── priority.py            urgency prediction
│   ├── duplicate_detection.py similarity matching
│   └── ocr_processor.py       optional OpenCV + Tesseract pipeline
│
├── utils/
│   ├── jwt_utils.py           @jwt_required, @role_required
│   ├── validators.py          mirrors the frontend validators
│   ├── file_utils.py          magic-number upload validation
│   ├── rate_limit.py          throttling for auth/OTP
│   ├── responses.py           the success/error envelope
│   └── helpers.py             dates, ids, deadlines
│
├── tests/                 pytest suite
└── uploads/               stored files (git-ignored)
```

---

## 6. Response format

Every endpoint returns the same envelope.

```jsonc
// success
{ "success": true, "message": "Complaint created successfully", "data": { } }

// error
{ "success": false, "message": "Invalid complaint data", "error": { } }
```

Validation failures return **422** with field-level messages in the same
`{field: message}` shape the frontend validators already produce:

```json
{ "success": false, "message": "Please correct the highlighted fields.",
  "error": { "fields": { "title": "Title should be at least 8 characters" } } }
```

---

## 7. What the "AI" actually is

**No machine-learning model has been trained.** Every prediction is rule-based,
and each response says so with `"modelTrained": false`. `GET /api/ai/status`
reports this in full.

| Feature | How it works today |
|---|---|
| Department | Weighted keyword dictionary over stemmed tokens |
| Priority | Urgency keyword rules + a scale-of-impact adjustment |
| Duplicates | Jaccard similarity over stemmed token sets |
| NLP | Cleaning, tokenising, stopword removal, suffix stemming, regex entities |
| OCR | OpenCV pre-processing + Tesseract — **optional, off by default** |

Each module is isolated behind a single function, so a trained model can
replace one without touching the routes or the frontend:

- `ai/classifier.py` → `classify(title, description, category)`
- `ai/priority.py` → `predict(title, description)`
- `ai/duplicate_detection.py` → `find_duplicates(...)`

### Enabling OCR

OCR is off by default and complaint submission works fully without it.

```bash
pip install opencv-python pytesseract
```

Tesseract itself must also be installed
([Windows builds](https://github.com/UB-Mannheim/tesseract/wiki)). Then set
`OCR_ENABLED=true`, and `TESSERACT_CMD` if the binary is not on `PATH`.

If the dependencies are missing, `POST /api/ai/ocr` reports that clearly
instead of failing — the pipeline can never break complaint submission.

---

## 8. Security

| Measure | Implementation |
|---|---|
| Passwords | bcrypt, 12 rounds; never stored, logged or returned |
| Tokens | Signed JWT with expiry and issuer; verified on every protected route |
| Authorisation | `@role_required("admin")` plus per-record ownership checks |
| Deactivated accounts | Existing tokens stop working immediately |
| Uploads | Extension + declared MIME + **magic-number** validation, size limits, randomised stored names |
| File access | Downloads are authenticated and scoped to the related complaint |
| Path traversal | Upload paths resolved and confined to the upload root |
| Rate limiting | Login, registration and OTP endpoints |
| CORS | Explicit origin list — never `*` |
| Secrets | Environment only; `.env` is git-ignored |
| Errors | Stack traces are logged server-side, never returned |
| Enumeration | Login and password-reset give identical answers for known and unknown emails |

### Before deploying anywhere real

1. Set a fresh `JWT_SECRET_KEY`.
2. Set `OTP_DEV_MODE=false` (otherwise codes are returned in API responses).
3. Change the `SEED_*_PASSWORD` values.
4. Set `FLASK_DEBUG=false` and `CORS_ORIGINS` to the real origin.
5. Run behind a production WSGI server (`waitress`, `gunicorn`) — not `app.py`.

### Automatic SLA escalation

Complaints that pass their deadline escalate up a three-level ladder. That
sweep has always been available on the admin screen
(`POST /api/admin/sla-check`); it can now also run on a timer:

```bash
SLA_AUTO_CHECK=true
SLA_CHECK_INTERVAL_MINUTES=60
```

**Off by default** - with it false the server behaves exactly as before. The
alternative is to leave it off and point cron / Windows Task Scheduler at the
admin endpoint instead. With several gunicorn workers each worker would start
its own timer; the sweep is idempotent so that is safe, just wasteful, so
prefer one worker or the external-cron approach.

---

## 9. API reference

### Auth — `/api/auth`
| Method | Path | Access |
|---|---|---|
| POST | `/register` | public |
| POST | `/login` | public |
| POST | `/logout` | authenticated |
| GET | `/me` | authenticated |
| PUT | `/profile` | authenticated |
| PUT | `/password` | authenticated |
| POST | `/send-otp` `/verify-otp` `/resend-otp` | public |
| POST | `/forgot-password` `/reset-password` | public |

### Complaints — `/api/complaints`
| Method | Path | Access |
|---|---|---|
| POST | `` | authenticated (JSON or multipart) |
| GET | `` | authenticated (auto-scoped by role) |
| GET | `/my` `/assigned` `/statistics` | authenticated |
| GET | `/escalations` | admin |
| GET | `/track/<ref>` | **public** |
| GET | `/<id>` `/<id>/history` | authenticated + permitted |
| PUT | `/<id>/status` | officer, admin |
| POST | `/<id>/remarks` | authenticated |
| POST | `/<id>/resolve` | officer, admin |
| POST | `/<id>/assign` · PUT `/<id>/reassign` | admin |
| PUT | `/<id>/priority` `/<id>/deadline` | admin / officer |
| POST | `/<id>/escalate` `/<id>/close` | admin |
| POST | `/<id>/reopen` `/<id>/feedback` | complainant |
| POST | `/<id>/evidence` | authenticated |

### AI — `/api/ai`
`POST /classify` · `/department` · `/priority` · `/duplicates` · `/nlp` · `/ocr` · `GET /status`

### Others
`/api/officers` · `/api/departments` · `/api/users` · `/api/notifications` ·
`/api/feedback` · `/api/analytics` · `/api/admin` · `/api/files/<path>`

---

## 10. MongoDB collections

`users` · `complaints` · `departments` · `officers` · `assignments` ·
`notifications` · `feedback` · `audit_logs` · `otps` · `counters`

Indexes are created automatically on start, including a TTL index that expires
OTP documents and a text index for complaint search.

---

## 11. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `JWT_SECRET_KEY is not set` | Copy `.env.example` to `.env` and generate a key (§2) |
| `Is MongoDB running?` | Start the MongoDB service; check `MONGO_URI` |
| Port 5000 already in use | `set PORT=5050 && python app.py` |
| Login fails with the demo password | The account was created with a different `SEED_*_PASSWORD` |
| Frontend shows "Cannot reach the server" | The backend is not running, or the origin is missing from `CORS_ORIGINS` |
| OTP not received | Expected — no mail provider is configured. In dev mode the code is in the API response |
#   M a j o r - P r o j e c t -  
 
