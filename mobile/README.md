# DSVV Grievance — Android app

A **separate** native-quality Android client for the existing Grievance
Management System. It talks to the same Flask backend over the same REST API
the website uses; it does not duplicate the backend, the database, or the
authentication system, and it does not modify the web frontend in any way.

```
Existing Flask backend  ──┬──►  Existing web app   (unchanged)
                          └──►  This Android app   (new)
```

---

## 1. Technology

**Flutter (Dart)**, chosen after inspecting the backend:

* `backend/MOBILE_API.md` was already written for a Flutter client — it
  documents the `client: "mobile"` login flag, refresh-token rotation, and FCM
  device registration. The server side of this app already existed.
* One language for all screens, and a real APK at the end.
* `flutter_map` renders the campus polygon directly from the coordinates the
  server validates against, with no Google Maps API key to provision.

| Concern | Package |
|---|---|
| State | `provider` |
| HTTP | `http` |
| Token storage | `flutter_secure_storage` (Keystore-backed) |
| Camera / gallery | `image_picker` |
| GPS | `geolocator` |
| Map | `flutter_map` + `latlong2` |
| Push | `firebase_messaging` + `flutter_local_notifications` (optional) |
| Charts | `fl_chart` |

---

## 2. Project structure

```
mobile/
├── lib/
│   ├── main.dart                  app entry, providers, push-tap routing
│   ├── core/
│   │   ├── config/
│   │   │   ├── app_config.dart    API base URL (--dart-define), limits
│   │   │   ├── constants.dart     mirror of backend/constants.py
│   │   │   └── campus.dart        DSVV polygon + bounds, copied from the server
│   │   ├── network/
│   │   │   ├── api_client.dart    envelope, 401→refresh→replay, multipart
│   │   │   └── api_exception.dart typed errors with per-field messages
│   │   ├── storage/secure_store.dart
│   │   ├── router/app_router.dart  role → shell
│   │   ├── theme/app_theme.dart    Material 3, brand palette from tokens.css
│   │   └── utils/formatters.dart
│   ├── models/                     user, complaint, notification, stats
│   ├── services/                   auth, complaint, admin, notification,
│   │                               location, push
│   ├── providers/                  auth, complaint, notification
│   ├── screens/
│   │   ├── auth/                   login, register, OTP, forgot password
│   │   ├── student/                dashboard, shell, new complaint
│   │   ├── officer/                dashboard, shell
│   │   ├── admin/                  dashboard, shell, complaints, users,
│   │   │                           officers, departments, escalations,
│   │   │                           analytics, settings
│   │   └── shared/                 complaint list, complaint details,
│   │                               map picker, notifications, profile
│   └── widgets/                    cards, badges, states, form fields,
│                                   image picker
└── android/                        manifest, Gradle, resources, icons
```

---

## 3. Screens implemented

**Auth (4)** — login, registration, OTP entry (6-box, resend cooldown),
forgot-password (email → OTP → new password).

**Student (7)** — dashboard, my complaints (search + filters + infinite
scroll), new complaint (camera/gallery/GPS/AI preview), complaint details,
feedback, notifications, profile.

**Officer (5)** — dashboard (overdue first), assigned queue, complaint
details, status update / remark / resolution with proof photos, profile.

**Admin (11)** — dashboard, all complaints, complaint details with
assign / reassign / priority / escalate / close, users, officers (with
create), departments, escalations, analytics (4 charts), settings, profile.

**Shared (5)** — complaint list, complaint details, campus map picker,
notifications feed, profile.

---

## 4. APIs integrated

All 59 calls were cross-checked against the Flask blueprints; every one maps
to a real route.

| Area | Endpoints |
|---|---|
| Auth | `login`, `register`, `refresh`, `logout`, `me`, `profile`, `password`, `send-otp`, `verify-otp`, `resend-otp`, `forgot-password`, `reset-password` |
| Complaints | list, `my`, `assigned`, `statistics`, `escalations`, `track/<id>`, `<id>`, create (JSON + multipart), `status`, `remarks`, `resolve`, `assign`, `reassign`, `priority`, `escalate`, `close`, `reopen`, `feedback`, `evidence` |
| AI | `classify` |
| Notifications | list, `unread-count`, `read-all`, `<id>/read`, `<id>/unread`, delete |
| Devices | `register` (POST/DELETE) |
| Users | list, `summary`, `<id>/status` |
| Officers | list, `suggest`, create, update, `<id>/status` |
| Departments | list, update, `<code>/status` |
| Analytics | `summary`, `overview`, `status`, `departments`, `priority`, `trend`, `sla` |
| Admin | `dashboard`, `settings`, `sla`, `sla-check` |

### Contract details that matter

* **Mobile session** — login/register send `"client": "mobile"` and the header
  `X-Client-Type: mobile`, so the server returns `refreshToken` /
  `expiresIn` alongside the short-lived access token.
* **Refresh** — serialised behind a single `Completer`. `MOBILE_API.md` warns
  that concurrent refreshes trip reuse detection and revoke every session, so
  parallel 401s queue behind one call. The rotated token is always stored.
* **Pagination** — every list request sends `?page=`, so all responses parse
  through the one paginated envelope.
* **Toggles** — `/users/<id>/status`, `/officers/<id>/status` and
  `/departments/<code>/status` are toggles that ignore the request body. The
  app sends no body and re-fetches afterwards.
* **Files** — `/api/files/...` is behind `@jwt_required`, so image thumbnails
  attach the bearer token rather than using a plain `Image.network`.

---

## 5. Campus map

`lib/core/config/campus.dart` holds the DSVV outline copied **verbatim** from
`backend/constants.py` (OpenStreetMap way/1152422760) — all 28 vertices, the
padded bounding box, and the centre. This was verified programmatically to be
byte-identical to the server's copy. No coordinates were invented.

The picker shades the true polygon, constrains panning to the padded bounds,
turns the pin red outside them, and gates "Confirm" on the same
`in_campus_bounds` rule the API enforces — so a pin the app accepts is a pin
the server accepts.

GPS failure is always recoverable: denied, blocked, disabled and timeout each
get their own message and the user can still drag the pin.

---

## 6. Building the APK

### Prerequisites (not installed on this machine)

| Tool | Version | Get it |
|---|---|---|
| Flutter SDK | 3.19+ | https://docs.flutter.dev/get-started/install/windows |
| JDK | 17 | bundled with Android Studio, or Temurin 17 |
| Android SDK | API 34 | Android Studio → SDK Manager |

Confirm with `flutter doctor` — it must show no red crosses for
"Flutter", "Android toolchain" and "Android Studio".

### Build

```bash
cd "e:\Major Project UI\mobile"

flutter pub get

# Debug on an emulator (host machine = 10.0.2.2)
flutter run

# Debug on a real phone over wifi — use YOUR laptop's LAN IP
flutter run --dart-define=API_BASE_URL=http://192.168.1.7:5000

# Release APK against the deployed backend
flutter build apk --release \
  --dart-define=API_BASE_URL=https://your-backend.vercel.app
```

The APK lands at:

```
mobile/build/app/outputs/flutter-apk/app-release.apk
```

Install it with `flutter install`, or copy the file to the phone and open it
(enable "Install unknown apps" for the file manager).

Smaller downloads, if you want them:

```bash
flutter build apk --split-per-abi --release --dart-define=API_BASE_URL=...
```

### Backend must be reachable

`flutter run` with no `--dart-define` targets `http://10.0.2.2:5000`, which is
the emulator's route to the host. Start the backend first:

```bash
cd "e:\Major Project UI"
python backend/app.py
```

For a real phone, the laptop and phone must be on the same wifi, the backend
must listen on `0.0.0.0`, and Windows Firewall must allow port 5000.

### Cleartext HTTP

Release builds refuse plain HTTP (`usesCleartextTraffic="false"` +
`network_security_config.xml`). Debug builds allow it via
`android/app/src/debug/`, so local development works while a shipped APK can
never send tokens in the clear. Point release builds at an HTTPS URL.

### Signing

Unsigned release builds fall back to the debug key, which installs fine for
testing. For a distributable APK:

```bash
keytool -genkey -v -keystore dsvv-release.jks -keyalg RSA \
  -keysize 2048 -validity 10000 -alias dsvv
```

Then create `mobile/android/key.properties` (gitignored):

```properties
storePassword=...
keyPassword=...
keyAlias=dsvv
storeFile=../../dsvv-release.jks
```

### Push notifications (optional)

The app runs fine without Firebase — `PushService` catches its own
initialisation failure and the in-app feed remains the source of truth, which
matches the backend's `PUSH_ENABLED=false` default.

To enable it: create a Firebase project, add an Android app with package
`in.ac.dsvv.grievance`, drop `google-services.json` into `android/app/`, then
uncomment the `com.google.gms.google-services` plugin line in
`android/app/build.gradle`. Configure `PUSH_ENABLED`, `FCM_PROJECT_ID` and
`FCM_CREDENTIALS_FILE` on the server per `MOBILE_API.md`.

---

## 7. Design notes

Built for Android, not as a shrunken website:

* Bottom navigation, 52dp minimum touch targets, cards instead of the web
  app's 860px-wide tables.
* Android back button handled with `PopScope` — sub-tabs return to Home, and
  the details screen carries its "something changed" result back so the list
  behind refreshes.
* Every list has explicit loading / empty / error states, and an empty result
  caused by a filter offers "Clear filters" rather than the generic message.
* Pull-to-refresh on every list and dashboard.
* Confirmation dialogs before anything destructive or irreversible.
* Optimistic updates on notification read/delete, reverted if the call fails.
* Client-side validation mirrors the server's rules, so users see problems
  before spending a round trip; server field errors map back onto the inputs.
* `POST /admin/reset-data` is deliberately **not** exposed — an irreversible
  wipe of all complaint data should not be one tap away on a phone. It remains
  on the web admin.
