# Mobile API notes

What a Flutter client needs that a browser does not. Everything here is
**additive**: the website's requests and responses are byte-identical to what
they were before, so both clients share one backend.

---

## 1. Sign in as a mobile client

Send `"client": "mobile"` in the login body (or the header
`X-Client-Type: mobile`). Without it you get the web session shape.

```http
POST /api/auth/login
Content-Type: application/json

{ "identifier": "student@dsvv.ac.in", "password": "…", "client": "mobile" }
```

```jsonc
{
  "success": true,
  "message": "Signed in successfully.",
  "data": {
    "user":  { "id": "USR-1001", "role": "student", … },
    "token": "<short-lived access JWT>",
    "issuedAt": "2026-08-29T…Z",
    "expiresIn": 3600,              // seconds  (MOBILE_ACCESS_TOKEN_MINUTES)
    "refreshToken": "<opaque>",     // store in secure storage, never in prefs
    "refreshExpiresIn": 2592000     // seconds  (REFRESH_TOKEN_DAYS)
  }
}
```

`register` accepts `"client": "mobile"` the same way.

Send the access token on every other call as `Authorization: Bearer <token>`.

---

## 2. `POST /api/auth/refresh`

Exchange a refresh token for a new access token. Call it when a request comes
back `401`, then retry the original request once.

**Authentication:** none. This is deliberate — the endpoint has to work *after*
the access token has expired. The refresh token is itself the credential.

**Request**

```jsonc
{ "refreshToken": "<opaque token>" }
```

**Response `200`**

```jsonc
{
  "success": true,
  "message": "Session refreshed.",
  "data": {
    "user": { … },
    "token": "<new access JWT>",
    "issuedAt": "…",
    "expiresIn": 3600,
    "refreshToken": "<NEW opaque token>",   // rotated - replace what you stored
    "refreshExpiresIn": 2592000
  }
}
```

**Errors**

| Status | When |
|--------|------|
| `422`  | `refreshToken` missing from the body |
| `401`  | unknown, expired, revoked, or already-used token |
| `403`  | the account has been deactivated |

**Rotation and reuse detection.** Every successful refresh consumes the old
token and returns a new one. If a consumed token is ever presented again, that
is either theft or a broken client, so **every session for that user is
revoked** and they must sign in again. Always overwrite your stored refresh
token with the new one, and never run two refreshes concurrently — serialise
them behind a single mutex/completer in the app.

---

## 3. `POST /api/auth/logout`

```jsonc
{ "refreshToken": "<opaque token>" }   // revokes just this device
{ "allDevices": true }                 // revokes every session for this user
```

Requires the access token in the `Authorization` header. Without a body it
behaves exactly as before (stateless sign-out) — which is what the website does.

---

## 4. Push notifications

### `POST /api/devices/register`

**Auth:** Bearer access token (required).

```jsonc
{ "token": "<FCM registration token>",
  "platform": "android",      // android | ios | web
  "deviceName": "Pixel 8" }   // optional, shown in the device list
```

`201` returns the stored device with the **token masked** (`"…a1b2c3"`). Safe to
call on every app launch: re-registering the same token updates the row rather
than creating a duplicate.

If a different account registers a token already on file, the token moves to
that account — so a shared handset never receives the previous user's alerts.

### `DELETE /api/devices/register`

```jsonc
{ "token": "<FCM registration token>" }
```

Or `?token=…` in the query string. Scoped to the owner: one user cannot delete
another's device. Call it on logout.

### `GET /api/devices`

The caller's own devices, tokens masked. Raw tokens are never returned by any
endpoint.

### Server configuration

| Variable | Meaning |
|---|---|
| `PUSH_ENABLED` | master switch, `false` by default |
| `FCM_PROJECT_ID` | Firebase project id |
| `FCM_CREDENTIALS_FILE` | absolute path to the service-account JSON |

The service-account JSON **must live outside the repository** and is covered by
`.gitignore`. Sending also needs `pip install firebase-admin`, which is
optional — the backend runs fine without it, and simply does not push.

When push is unconfigured, notifications still appear in the in-app feed, which
remains the source of truth.

---

## 5. Response shapes

Every endpoint uses the same envelope:

```jsonc
{ "success": true, "message": "…", "data": … }
```

Errors:

```jsonc
{ "success": false, "message": "…", "error": { "fields": { "email": "…" } } }
```

**List endpoints.** `/api/complaints`, `/api/complaints/my` and
`/api/complaints/assigned` are always paginated:

```jsonc
{ "items": [ … ], "total": 100, "page": 1, "pageSize": 20, "totalPages": 5 }
```

`/api/officers`, `/api/notifications`, `/api/departments`, `/api/users` and
`/api/feedback` return a **bare array by default**, because live pages in the
website consume them that way (`[...officers].sort(…)`). Add `?page=` or
`?pageSize=` and you get the paginated envelope above instead.

**Mobile clients should always send `?page=`**, so every list parses through one
model.

### Page size limits

| Limit | Value |
|---|---|
| default | 10 (complaints), 20 (other lists) |
| maximum over HTTP | **100** |

Anything larger is clamped to 100 rather than rejected, so no request fails
because of it. The website's dashboard/chart helper asks for the whole set with
`pageSize=10000`, and the CSV export reads server-side; both are explicitly
allowed and remain scoped by role.

---

## 6. OTP behaviour

In production a verification code is **never** returned in an API response —
it is only delivered by the configured mail provider. `forgot-password` returns
an identical body whether or not the address is registered, so it cannot be
used to discover accounts.

Codes are only echoed back in a development or test environment. That requires
`OTP_DEV_MODE=true` **and** a non-production environment; setting the flag on a
deployed server does nothing.
