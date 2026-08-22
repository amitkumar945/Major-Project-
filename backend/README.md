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

137 tests covering registration, login, JWT verification, role authorisation,
OTP, complaint creation, tracking, status flow, remarks, resolution, feedback,
reopen, file upload, department prediction, priority prediction, duplicate
detection, officer assignment, SLA escalation, analytics and audit logging —
plus invalid input and unauthorised access for each.

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