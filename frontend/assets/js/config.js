/**
 * Runtime configuration for the frontend.
 *
 * Loaded as a plain (non-module) script before the page modules, so anything
 * set here is already on `window` when `services/mockApi.js` reads it.
 *
 * Leave the value empty for the normal setup: Flask serves this folder itself
 * on http://127.0.0.1:5000, and the standalone static server on port 5500 is
 * detected automatically, so mockApi.js works out the right API URL on its own.
 *
 * Set it only if the API ever lives on a different origin from these pages:
 *
 *     window.__API_BASE_URL__ = 'https://api.example.com'
 */
window.__API_BASE_URL__ = ''
