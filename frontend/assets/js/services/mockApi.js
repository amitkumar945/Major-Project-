/**
 * Mock API transport.
 *
 * Every service in this folder talks to the pages through the same
 * promise-based contract that a real HTTP call would use. Today the data comes
 * from the files in `assets/js/data`; tomorrow only the body of each service
 * function changes.
 *
 * ---------------------------------------------------------------------------
 * FUTURE FLASK INTEGRATION
 * ---------------------------------------------------------------------------
 * The browser's built-in `fetch` is all that is needed - no library, no build
 * step. Set `USE_API` to true below once the Flask server is running.
 *
 * 1. A service body changes from this:
 *
 *      export function getComplaints(filters) {
 *        return respond(applyFilters(filters))
 *      }
 *
 *    to this:
 *
 *      export function getComplaints(filters) {
 *        return request('/complaints', { query: filters })
 *      }
 *
 * 2. No page needs to change, because pages only ever await the service
 *    function and never know where the data came from.
 * ---------------------------------------------------------------------------
 */

/**
 * Base URL of the Flask API.
 *
 * Relative by default, so the same build works whether Flask serves this
 * folder itself (http://127.0.0.1:5000) or a separate static server does
 * (http://localhost:5500). In the second case the browser still needs an
 * absolute URL, so fall back to the Flask origin when the page is not being
 * served by Flask itself.
 */
const SAME_ORIGIN = ['5000', '80', '443', ''].includes(location.port)

export const API_BASE_URL = SAME_ORIGIN
  ? '/api'
  : `${location.protocol}//${location.hostname}:5000/api`

/**
 * The real Flask backend is now connected; every service calls it over HTTP.
 * The mock helpers below (`respond`, `fail`, `delay`) are kept only because a
 * few components still use `delay` for their loading animations.
 */
export const USE_API = true

/** Error shape the pages can rely on for both mock and real failures. */
export class ApiError extends Error {
  constructor(message, status = 400, fields = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    // Field-level messages from a 422, in the same `{field: message}` shape
    // the client-side validators produce, so `showErrors()` can render them.
    this.fields = fields
  }
}

export function delay(ms = 400) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Resolve with `data` after a short, realistic network pause.
 * The pause is what makes the loading skeletons visible in the prototype.
 */
export async function respond(data, ms = 380) {
  await delay(ms)
  // Return a deep copy so callers cannot mutate the in-memory store by accident.
  return structuredClone(data)
}

/** Reject with an ApiError after a pause - used for simulated failures. */
export async function fail(message, status = 400, ms = 300) {
  await delay(ms)
  throw new ApiError(message, status)
}

/* ------------------------------------------------------------ real HTTP */

/** The signed-in user's token, attached to every authenticated request. */
function authToken() {
  try {
    return JSON.parse(localStorage.getItem('dsvv_auth_session') ?? 'null')?.token ?? null
  } catch {
    return null
  }
}

/**
 * The session has expired or the token was rejected. Clear it and send the
 * visitor to the login page, remembering where they were.
 */
function handleExpiredSession() {
  try {
    localStorage.removeItem('dsvv_auth_session')
  } catch {
    /* ignore */
  }
  // Public pages (landing, tracking, login) must not bounce.
  const publicPages = ['/index.html', '/login.html', '/register.html', '/track.html', '/forgot-password.html', '/']
  if (!publicPages.includes(location.pathname)) {
    const next = encodeURIComponent(location.pathname + location.search)
    location.replace(`/login.html?next=${next}&expired=1`)
  }
}

/**
 * Unwrap the API envelope: `{ success, message, data }`.
 * Services receive `data` directly, which is the shape the pages already use.
 */
function unwrap(payload) {
  if (payload && typeof payload === 'object' && 'success' in payload && 'data' in payload) {
    return payload.data
  }
  return payload
}

/**
 * Call the Flask API.
 *
 * @param {string} path            e.g. '/complaints'
 * @param {object} [options]
 * @param {string} [options.method]  GET | POST | PUT | PATCH | DELETE
 * @param {object} [options.body]    JSON body
 * @param {object} [options.query]   query-string parameters
 */
export async function request(path, { method = 'GET', body, query } = {}) {
  const url = new URL(API_BASE_URL + path, location.origin)
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== '' && value != null && value !== false) {
        url.searchParams.set(key, value)
      }
    })
  }

  const headers = { Accept: 'application/json' }
  if (body) headers['Content-Type'] = 'application/json'

  const token = authToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError('Cannot reach the server. Please check that the backend is running.', 0)
  }

  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    // 401 on a protected page means the token died - don't leave the user
    // staring at an error they cannot act on.
    if (response.status === 401 && token) handleExpiredSession()

    throw new ApiError(
      payload?.message ?? 'The request could not be completed.',
      response.status,
      payload?.error?.fields ?? null,
    )
  }

  return unwrap(payload)
}

/**
 * Send files to Flask as multipart/form-data (evidence, resolution proof).
 * `fields` values that are objects are JSON-encoded, which is what the
 * complaint endpoint expects for `location` and `ai`.
 */
export async function upload(path, files, fields = {}, method = 'POST') {
  const form = new FormData()
  ;(files ?? []).forEach((file) => form.append('files', file))

  Object.entries(fields).forEach(([key, value]) => {
    if (value == null) return
    form.append(key, typeof value === 'object' ? JSON.stringify(value) : value)
  })

  const token = authToken()

  let response
  try {
    response = await fetch(new URL(API_BASE_URL + path, location.origin), {
      method,
      // No Content-Type: the browser sets it with the multipart boundary.
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
  } catch {
    throw new ApiError('Cannot reach the server. Please check that the backend is running.', 0)
  }

  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    if (response.status === 401 && token) handleExpiredSession()
    throw new ApiError(
      payload?.message ?? 'The upload could not be completed.',
      response.status,
      payload?.error?.fields ?? null,
    )
  }

  return unwrap(payload)
}
