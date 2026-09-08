# PWA + Android packaging

The existing HTML/CSS/JS frontend, made installable on Android and packaged
for the Play Store. **One codebase, one backend, one database** — nothing was
rewritten, and every existing page, API and role still works exactly as before.

```
frontend/ (existing HTML/CSS/JS)
      ↓  + manifest + service worker
Installable PWA  ──────────────►  Android home screen
      ↓  + TWA wrapper (Bubblewrap)
APK / AAB  ────────────────────►  Google Play Store
      ↓
Same Flask backend + MongoDB (unchanged)
```

---

## 1. Files created

| File | Purpose |
|---|---|
| `frontend/manifest.webmanifest` | App name, icons, colours, standalone display, shortcuts |
| `frontend/sw.js` | Service worker — app-shell cache, **never caches API data** |
| `frontend/offline.html` | Fallback page shown when a navigation fails offline |
| `frontend/assets/js/pwa.js` | Registers the worker, provides the "Install app" button |
| `frontend/assets/css/mobile.css` | Mobile/PWA polish, loaded last so it layers on top |
| `frontend/assets/icons/*.png` | 192/512 standard + 192/512 maskable + apple-touch |
| `frontend/.well-known/assetlinks.json` | Digital Asset Links for the TWA (needs your fingerprint) |

## 2. Files modified

| File | Change |
|---|---|
| 30 × `*.html` | **+9 lines each, purely additive**: manifest link, theme-color, apple meta tags, `mobile.css`, `pwa.js` |
| `frontend/assets/js/components/session.js` | Sign-out now also clears cached pages (one optional-chained call) |
| `frontend/assets/js/pages/adminEscalations.js` | Added mobile cards beside the 11-column table |

**No backend file was changed.** Flask already served the frontend folder, so
`manifest.webmanifest`, `sw.js` and `.well-known/assetlinks.json` are picked up
automatically.

---

## 3. Caching policy (important)

The service worker is deliberately conservative:

| Request | Behaviour |
|---|---|
| `/api/**` | **Network only. Never cached.** Offline → JSON error the UI already handles |
| `/uploads/**` | **Network only. Never cached.** (Complaint evidence is private) |
| Non-GET (POST/PUT/DELETE) | Never intercepted |
| Cross-origin (fonts, map tiles) | Not intercepted; browser HTTP cache handles it |
| `/assets/**` | Cache-first, refreshed in background (public, identical for everyone) |
| HTML pages | Network-first, cache only as an offline fallback |

Complaints, profiles, notifications and analytics are private and role-scoped.
Caching them would leave one user's grievances readable by the next person on a
shared handset, and would survive logout. So they are never stored.

On sign-out the app posts `CLEAR_PRIVATE_CACHE`, which deletes the runtime
page cache.

---

## 4. Installing the PWA on Android

**Requirement: HTTPS.** Service workers only run in a secure context.
`localhost` counts as secure, so local development works, but a plain-HTTP LAN
IP does **not** — on `http://10.x.x.x:5000` the site still works as a normal
website, just without install or offline support.

### On the phone
1. Open the site in **Chrome** on Android.
2. Either tap the **Install app** button that appears bottom-right, or use
   Chrome's ⋮ menu → **Add to Home screen / Install app**.
3. The DSVV shield icon appears on the home screen.
4. Opening it launches standalone — no browser address bar.

### Verifying it worked
Chrome DevTools (`chrome://inspect` with the phone connected, or desktop
Chrome) → **Application** tab:
- **Manifest** — no errors, icons listed
- **Service workers** — `sw.js` "activated and running"
- **Cache storage** — `dsvv-shell-v1` present; confirm no `/api/` entries

---

## 5. Building the Android package (TWA)

A Trusted Web Activity wraps the PWA in a native shell. The UI is still the
same HTML/CSS/JS — nothing is rebuilt.

### Prerequisites (already installed on this machine)
- JDK 17 — `C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot`
- Android SDK — `%LOCALAPPDATA%\Android\Sdk`
- Node 24 / npm 11
- `npm install -g @bubblewrap/cli`

### Build

```bash
# 1. Initialise from the deployed manifest (must be a public HTTPS URL)
cd android-twa
bubblewrap init --manifest https://YOUR-DOMAIN/manifest.webmanifest

# 2. Debug APK, for testing on a phone
bubblewrap build --skipPwaValidation
#    → ./app-release-unsigned-aligned.apk and ./app-release-bundle.aab

# 3. Install the debug build
adb install -r app-release-signed.apk
```

Bubblewrap asks for a signing key on first run; it can generate one. **Keep
that keystore safe** — Play Store updates must be signed with the same key.

### Digital Asset Links (required, or the app shows a browser bar)

1. Get your release key's SHA-256 fingerprint:
   ```bash
   keytool -list -v -keystore android.keystore -alias android
   ```
2. Paste it into `frontend/.well-known/assetlinks.json`, replacing
   `REPLACE_WITH_YOUR_RELEASE_SIGNING_KEY_SHA256_FINGERPRINT`.
3. Redeploy the frontend so `https://YOUR-DOMAIN/.well-known/assetlinks.json`
   serves it.
4. Verify: https://developers.google.com/digital-asset-links/tools/generator

If Play App Signing is enabled (recommended), use the fingerprint Play Console
shows you **after** the first upload, not your local one.

---

## 6. Google Play Console steps

1. Create the app in Play Console (name, default language, app/game, free/paid).
2. Upload the `.aab` to a testing track first (internal testing is fastest).
3. Complete the required declarations:
   - Privacy policy URL (mandatory — the app handles personal data)
   - Data safety form: declare location, photos, email, name
   - Content rating questionnaire
   - Target audience and ads declaration
4. Add store listing: short/full description, 512×512 icon, feature graphic
   (1024×500), and at least 2 phone screenshots.
5. Enable Play App Signing, then copy the SHA-256 it gives you into
   `assetlinks.json` and redeploy the site.
6. Roll out to internal testing, install from the Play link, confirm the app
   opens **without** a browser address bar (that proves asset links verified).
7. Promote to production.

---

## 7. Mobile responsiveness

The frontend was already mobile-first (viewport tags on all 30 pages, drawer
sidebar, bottom tab bar, 32 media queries, card fallbacks for the complaint
tables). `mobile.css` adds what was missing:

- Horizontal-overflow guard, so no page scrolls sideways
- 48dp minimum touch targets on coarse pointers
- 16px form inputs (stops iOS zoom-on-focus)
- Safe-area insets for notch and gesture bar in standalone mode
- Modals become bottom sheets under 720px
- Chart and filter-bar wrapping
- Tap-highlight removal on custom controls
- Install button styling; hidden once installed

Plus mobile cards for the admin escalations table (previously an 11-column,
1100px-wide table — the last remaining horizontal-scroll offender).
