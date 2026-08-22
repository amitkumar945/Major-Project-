# DSVV Grievance Management System — Frontend

A complete frontend for the **Dev Sanskriti Vishwavidyalaya Grievance Management System**, built
as an MCA major project using **plain HTML, CSS and JavaScript**.

Students and staff register campus complaints (water, electricity, building, computer lab); the
system classifies them, assigns a department officer, tracks them against a deadline, escalates
them when the deadline is missed, and collects feedback once the work is done.

> **No build step. No framework. No dependencies.**
> There is no React, no Node.js, no npm, no bundler. Every file in this folder is served exactly
> as it is written.

> **This build is connected to a real backend.** Authentication (bcrypt + JWT), the complaint
> lifecycle, notifications, analytics and the AI classification all run on the Flask + MongoDB
> API in `../backend`, and the data lives in MongoDB. The services in `assets/js/services/` are
> thin HTTP clients — the mock data files in `assets/js/data/` are no longer used at runtime and
> are kept only as reference for the original prototype.

---

## 1. Running the project

The backend serves this folder, so one server runs everything:

```bash
cd backend
python app.py
```

Then open **http://127.0.0.1:5000**

See `../backend/README.md` for first-time setup (it takes two commands: install the requirements
and generate a `JWT_SECRET_KEY`).

### Running the frontend separately

The pages use ES modules (`<script type="module">`), which browsers refuse to load from a `file://`
path — **do not double-click `index.html`.** To serve this folder on its own:

```bash
cd frontend
python -m http.server 5500
```

Open **http://localhost:5500**. The backend must still be running on port 5000; CORS is already
configured for this origin, and `services/mockApi.js` detects the port and calls
`http://localhost:5000/api` automatically.

| Command | What it does |
|---|---|
| `python ../backend/app.py` | Run the API **and** serve this folder on port 5000 |
| `python -m http.server 5500` | Serve only the frontend (backend must run separately) |
| `Ctrl + C` | Stop the server |

---

## 2. Demo login credentials

Real accounts, created in MongoDB the first time the backend starts. Each lands on a different
dashboard.

| Role | Email | Password |
|---|---|---|
| Student / Staff | `student@dsvv.ac.in` | `student123` |
| Department Officer | `officer@dsvv.ac.in` | `officer123` |
| Administrator | `admin@dsvv.ac.in` | `admin123` |

The login page has a one-click button for each account, so nothing has to be typed during a demo.
Passwords are bcrypt-hashed in the database and verified by the API — the browser never sees a
password list.

Registering creates a real account and returns a signed JWT. The sign-up form itself is
email-only, with no OTP step; the backend does implement OTP
(`/api/auth/send-otp`, `/verify-otp`, `/resend-otp`) and it can be made mandatory for registration
by setting `OTP_REQUIRED_FOR_REGISTER=true`.

You can also sign in as any other officer in the directory using that officer's email with the
password `officer123` — useful for showing a second officer's queue.

---

## 3. Technology used

| Layer | Choice |
|---|---|
| Markup | HTML5, one file per screen (multi-page application) |
| Styling | Hand-written CSS with custom properties — no framework, no preprocessor |
| Behaviour | JavaScript ES modules (ES2022) — no library |
| Charts | Hand-drawn inline SVG (`assets/js/components/charts.js`) |
| Icons | One SVG sprite (`assets/icons.svg`), referenced with `<use>` |
| Routing | Ordinary links between HTML pages |
| State | Browser `localStorage` |
| Dependencies | **none** |

### Why no framework

- The whole project runs from a plain folder — nothing to install, nothing to build.
- Flask can serve this folder directly, so the finished system needs one server, not two.
- Every line that runs in the browser is a line in this repository, which makes the project
  straightforward to explain during the viva.

---

## 4. Folder structure

```text
frontend/
├── index.html                  landing page
├── track.html                  public complaint tracking
├── login.html  register.html  forgot-password.html
├── 404.html
│
├── student/                    dashboard, new-complaint, complaints,
│                               complaint-details, notifications, feedback,
│                               profile, help
├── officer/                    dashboard, complaints, complaint-details,
│                               department, notifications, profile
├── admin/                      dashboard, complaints, complaint-details,
│                               departments, officers, users, escalations,
│                               analytics, notifications, settings
│
└── assets/
    ├── favicon.svg
    ├── icons.svg               SVG sprite — every icon in the application
    │
    ├── css/
    │   ├── tokens.css          colours, spacing, type scale, shadows
    │   ├── base.css            reset, element defaults, utilities, animations
    │   ├── components.css      buttons, cards, badges, forms, tables, modals…
    │   ├── layout.css          navbar, sidebar, topbar, page shells
    │   └── pages.css           landing, stepper, timeline, charts, map…
    │
    └── js/
        ├── utils/              constants, helpers, validators,
        │                       complaintTimeline, chartTheme
        ├── data/               departments, users, complaints, notifications,
        │                       analytics, feedback   (mock data)
        ├── services/           mockApi, authService, complaintService,
        │                       userService, officerService, departmentService,
        │                       notificationService, analyticsService
        ├── components/         dom, ui, toast, modal, shell, session,
        │                       navigation, publicChrome, authAside, charts,
        │                       complaintTable, complaintListView, filters,
        │                       timeline, notificationItem, complaintParts,
        │                       fileUpload, locationPicker, aiCard
        └── pages/              one script per screen
```

### How a page is put together

Every page follows the same three steps:

```js
ready(() => {
  const user = requireRole(ROLES.STUDENT)   // 1. guard the page
  if (!user) return
  renderShell(user, { title: 'Dashboard' }) // 2. draw sidebar + top bar
  load(user)                                // 3. fetch data and render
})
```

`components/dom.js` is what replaces the framework. Components are plain functions that return an
HTML string, and pages put that string into the page:

```js
mount('#root', complaints.map(complaintCard).join(''))
```

Any value that came from a user goes through `esc()` first, so a quotation mark inside a complaint
description can never break the markup.

---

## 5. Pages

| Page | Access | What it does |
|---|---|---|
| `index.html` | public | Hero, how-it-works, departments, features, workflow, FAQ |
| `track.html` | public | Track any complaint by reference number |
| `login.html` | public | Sign in, with one-click demo accounts |
| `register.html` | public | Create an account and sign in immediately |
| `forgot-password.html` | public | Password reset request |
| `student/dashboard.html` | student | Counters, quick actions, three charts, recent complaints |
| `student/new-complaint.html` | student | Five-step submission form |
| `student/complaints.html` | student | Search, filters, sorting, pagination |
| `student/complaint-details.html` | student | Tracking, timeline, feedback, reopen |
| `student/notifications.html` | student | Notification centre |
| `student/feedback.html` | student | Ratings given and pending |
| `student/profile.html` | student | Profile and password |
| `student/help.html` | student | FAQs and support form |
| `officer/dashboard.html` | officer | Workload counters and performance |
| `officer/complaints.html` | officer | Personal work queue |
| `officer/complaint-details.html` | officer | Accept, change status, remarks, resolution |
| `officer/department.html` | officer | Department queue and team workload |
| `admin/dashboard.html` | admin | Campus-wide metrics and four charts |
| `admin/complaints.html` | admin | Master table with inline actions |
| `admin/complaint-details.html` | admin | Assign, re-prioritise, escalate, close |
| `admin/departments.html` | admin | Add, edit and delete departments |
| `admin/officers.html` | admin | Directory, workload, activate/deactivate |
| `admin/users.html` | admin | Students and staff directory |
| `admin/escalations.html` | admin | Overdue complaints and the escalation ladder |
| `admin/analytics.html` | admin | Eight analytics charts |
| `admin/settings.html` | admin | Targets, notifications, automation, demo reset |

Access is enforced by `requireRole()` at the top of every page script: a student who opens an admin
page is redirected to their own dashboard, and a signed-out visitor is sent to the login page and
returned afterwards.

---

## 6. The complaint lifecycle

```text
Submitted → AI Classified → Assigned to Department → Officer Assigned
         → Work Started → Resolution Submitted → Resolved → Feedback
```

Each stage is recorded with a timestamp and the responsible person, and is shown to the
complainant as a visual timeline.

**Deadlines** come from the priority: 1 day (Urgent), 3 (High), 7 (Medium), 14 (Low).
**Escalation** has three levels: Department Officer → Department Head → Administration.

---

## 7. The AI module

Classification now runs **on the server** (`backend/ai/`), called from
`complaintService.analyseComplaint()` via `POST /api/ai/classify`.

| Prediction | How it works today |
|---|---|
| Department | Weighted keyword dictionary over stemmed tokens; strong terms outweigh shared ones |
| Priority | Urgency rules, plus a reason string and a scale-of-impact adjustment |
| Duplicate probability | Jaccard similarity of stemmed token sets against existing complaints |
| Confidence | Grows with the winning score and its margin over second place |
| Suggested officer | The active officer in that department with the lightest **live** workload |
| Text processing | Cleaning, tokenising, stopword removal, stemming, regex entity extraction |

**No model has been trained.** Every AI response includes `"modelTrained": false`, and
`GET /api/ai/status` reports exactly what is and is not available. Each module is isolated so a
trained model can replace it without changing this frontend.

---

## 8. Charts

The charts are drawn by hand as SVG in `components/charts.js` — donut, horizontal bars, columns,
grouped bars and lines. There is no charting library.

The palette in `utils/chartTheme.js` was checked for colour-vision-deficiency separation rather
than picked by eye, and every chart carries a legend plus a **"view as table"** switch, so no
information depends on colour alone.

---

## 9. How the frontend talks to Flask

`services/mockApi.js` holds the transport. It picks the API origin automatically, so the same
files work whether Flask serves them or a separate static server does:

```js
// /api when Flask serves this folder, http://<host>:5000/api otherwise
export const API_BASE_URL = SAME_ORIGIN ? '/api' : `${location.protocol}//${location.hostname}:5000/api`
```

`request()` and `upload()` use the browser's built-in `fetch`, attach the JWT from localStorage,
unwrap the `{ success, message, data }` envelope so services receive `data` directly, and raise
`ApiError` (carrying `.status` and, for a 422, `.fields`) on failure. A 401 on a protected page
clears the dead session and returns the visitor to the login screen.

Pages never changed during the backend migration, because they only ever await a service function.

### Endpoint map

| Service function | Flask endpoint |
|---|---|
| `authService.login` | `POST /api/auth/login` |
| `authService.register` | `POST /api/auth/register` |
| `authService.logout` | `POST /api/auth/logout` |
| `authService.updateProfile` | `PUT /api/auth/profile` |
| `authService.changePassword` | `PUT /api/auth/password` |
| `authService.requestPasswordReset` | `POST /api/auth/forgot-password` |
| `authService.sendOtp` / `verifyOtp` / `resendOtp` | `POST /api/auth/send-otp` · `/verify-otp` · `/resend-otp` |
| `complaintService.getComplaints` | `GET /api/complaints` |
| `complaintService.getComplaintById` | `GET /api/complaints/:id` |
| `complaintService.trackComplaint` | `GET /api/complaints/track/:ref` |
| `complaintService.getStatistics` | `GET /api/complaints/statistics` |
| `complaintService.getEscalations` | `GET /api/complaints/escalations` |
| `complaintService.createComplaint` | `POST /api/complaints` |
| `complaintService.updateStatus` | `PUT /api/complaints/:id/status` |
| `complaintService.addRemark` | `POST /api/complaints/:id/remarks` |
| `complaintService.submitResolution` | `POST /api/complaints/:id/resolve` |
| `complaintService.assignOfficer` | `POST /api/complaints/:id/assign` |
| `complaintService.changePriority` | `PUT /api/complaints/:id/priority` |
| `complaintService.escalateComplaint` | `POST /api/complaints/:id/escalate` |
| `complaintService.closeComplaint` | `POST /api/complaints/:id/close` |
| `complaintService.reopenComplaint` | `POST /api/complaints/:id/reopen` |
| `complaintService.submitFeedback` | `POST /api/complaints/:id/feedback` |
| `complaintService.analyseComplaint` | `POST /api/ai/classify` |
| `complaintService.findDuplicates` | `POST /api/ai/duplicates` |
| `officerService.getOfficers` | `GET /api/officers` |
| `officerService.suggestOfficer` | `GET /api/officers/suggest` |
| `departmentService.getDepartments` | `GET /api/departments` |
| `userService.getUsers` | `GET /api/users` |
| `notificationService.getNotifications` | `GET /api/notifications` |
| `notificationService.markAllAsRead` | `PUT /api/notifications/read-all` |
| `analyticsService.getDashboardCharts` | `GET /api/analytics/charts` |
| `analyticsService.getAnalyticsOverview` | `GET /api/analytics/overview` |

### Serving this folder from Flask

Already done — `backend/app.py` serves this folder, including extension-less URLs like `/login`
and `/student/dashboard`, with `404.html` as the fallback. Set `SERVE_FRONTEND=false` to turn it
off and host the frontend elsewhere.

One server, no Node, no build step.

---

## 10. Responsive design

| Breakpoint | Behaviour |
|---|---|
| ≥ 1280px | Full desktop layout, wider page padding |
| ≥ 1024px | Sidebar becomes a fixed column; tables replace card lists |
| 640–1023px | Sidebar becomes a slide-in drawer; complaint tables become cards |
| < 640px | Everything single column; forms stack; dashboard cards stack |

---

## 11. Accessibility

- Every form control has a `<label>`, and validation messages use `role="alert"`.
- Dialogs trap focus, close on Escape, and return focus where it came from.
- Keyboard focus is always visible (`:focus-visible`), and every page has a skip link.
- Charts ship a legend and a table view, so colour never carries meaning alone.
- Icons are `aria-hidden`; the text beside them carries the meaning.
- `prefers-reduced-motion` disables all animation.

---

## 12. What is real, and what is not

| Feature | Status |
|---|---|
| Login, registration, roles | **Real** — bcrypt hashing and signed JWTs, verified by Flask |
| Complaints, officers, departments, users | **Real** — stored in MongoDB |
| File uploads | **Real** — validated by magic number, stored on the server, downloads are access-controlled |
| Notifications | **Real** — generated by the server and stored in MongoDB |
| Analytics | **Real** — every chart is computed from actual complaint data |
| SLA and escalation | **Real** — deadline monitoring with a three-level ladder |
| Audit log | **Real** — every consequential action is recorded |
| AI classification, priority, duplicates | **Rule-based, not a trained model** — see §7 |
| OCR | Implemented but **off by default**; needs OpenCV + Tesseract installed |
| Geo-location | Real Geolocation API, with a simulated campus fallback |
| Email / SMS delivery | **Not sent** — no provider is configured. OTP codes are returned in the API response while `OTP_DEV_MODE=true` |
| Admin → Settings → Reset demo data | Now **permanently deletes** all complaint data from MongoDB |

---

## 13. Academic note

All names, IDs and email addresses are invented for this prototype and do not belong to any real
person. This is an academic project and not an official university portal.
