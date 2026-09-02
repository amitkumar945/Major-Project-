/**
 * Runtime configuration for the frontend.
 *
 * This static app is designed to run either:
 *   1) behind Flask on the same origin, or
 *   2) on a separate host with a real backend API.
 *
 * Leave this null for the normal setup. The frontend and the Flask API are
 * deployed together as one Vercel project (see the root `vercel.json`, which
 * routes `/api/*` to `api/index.py`), so the API is always on the same origin
 * as these pages. With no override, `services/mockApi.js` resolves the base to
 * a relative `/api`, which works in production and when Flask serves the app
 * locally on :5000. When a separate static server hosts these files (e.g. Live
 * Server on :5500), it falls back to the Flask dev origin on port 5000.
 *
 * Only set this if the API ever moves to a genuinely different origin, e.g.
 * 'https://api.example.com' or 'https://api.example.com/api'. Values ending
 * with /api are normalised automatically. Do not leave a placeholder hostname
 * here: it overrides the working same-origin default and every request fails
 * with net::ERR_NAME_NOT_RESOLVED.
 */
window.__API_BASE_URL__ = null
