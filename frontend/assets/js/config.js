/**
 * Runtime configuration for the frontend.
 *
 * This static app is designed to run either:
 *   1) behind Flask on the same origin, or
 *   2) on a separate host such as Vercel with a real backend API.
 *
 * For production hosting on Vercel, set this to your deployed Flask API base,
 * e.g. https://api.example.com or https://api.example.com/api.
 *
 * The app normalises values ending with /api automatically.
 */
window.__API_BASE_URL__ = 'https://your-backend-url.example.com'
