/**
 * Authentication service.
 *
 * Talks to the real Flask backend:
 *
 *   POST /api/auth/login      /register      /logout
 *   PUT  /api/auth/profile    /password
 *   POST /api/auth/forgot-password
 *
 * Passwords are verified server-side against a bcrypt hash and the token
 * returned is a real signed JWT. The session object stored in localStorage
 * keeps the same `{ user, token, issuedAt }` shape the pages already expect,
 * so `components/session.js` and `requireRole()` did not change.
 */

import { readStorage, removeStorage, writeStorage } from '../utils/helpers.js'
import { ApiError, request } from './mockApi.js'

const SESSION_KEY = 'dsvv_auth_session'

/* ------------------------------------------------------------ session I/O */

/** The signed-in user, or null. Read once when the page boots. */
export function getStoredSession() {
  return readStorage(SESSION_KEY, null)
}

export function storeSession(session) {
  writeStorage(SESSION_KEY, session)
}

export function clearSession() {
  removeStorage(SESSION_KEY)
}

/* ---------------------------------------------------------------- actions */

/**
 * Sign in.
 *
 * @param {{identifier: string, password: string, role?: string}} credentials
 * @returns {Promise<{user: object, token: string, issuedAt: string}>}
 */
export async function login({ identifier, password, role }) {
  const session = await request('/auth/login', {
    method: 'POST',
    body: { identifier, password, role },
  })

  storeSession(session)
  return session
}

export async function logout() {
  try {
    await request('/auth/logout', { method: 'POST' })
  } catch {
    // A failed logout call must never trap the user in a signed-in state:
    // the token is discarded locally either way.
  }
  clearSession()
  return { success: true }
}

/**
 * Create an account and sign in straight away.
 * The API returns the same `{ user, token }` shape as login.
 */
export async function register(values) {
  const session = await request('/auth/register', {
    method: 'POST',
    body: {
      fullName: values.fullName,
      userId: values.userId,
      email: values.email,
      password: values.password,
      department: values.department,
      userType: values.userType ?? 'Student',
      mobile: values.mobile ?? '',
    },
  })

  storeSession(session)
  return session
}

/** Ask the server to email a password-reset code. */
export async function requestPasswordReset(email) {
  const result = await request('/auth/forgot-password', {
    method: 'POST',
    body: { email },
  })

  return {
    success: true,
    message: 'If that address is registered, a reset code has been sent to it.',
    ...result,
  }
}

/** Finish a reset: verify the emailed code, then set the new password. */
export async function resetPassword({ email, otp, newPassword }) {
  return request('/auth/reset-password', {
    method: 'POST',
    body: { email, otp, newPassword },
  })
}

/* -------------------------------------------------------------- OTP flow */

export async function sendOtp(email, purpose = 'verify_email') {
  return request('/auth/send-otp', { method: 'POST', body: { email, purpose } })
}

export async function verifyOtp(email, otp, purpose = 'verify_email') {
  return request('/auth/verify-otp', { method: 'POST', body: { email, otp, purpose } })
}

export async function resendOtp(email, purpose = 'verify_email') {
  return request('/auth/resend-otp', { method: 'POST', body: { email, purpose } })
}

/* --------------------------------------------------------------- profile */

/** Update the signed-in user's profile and refresh the stored session. */
export async function updateProfile(userId, changes) {
  const user = await request('/auth/profile', { method: 'PUT', body: changes })

  const session = getStoredSession()
  if (session) storeSession({ ...session, user })

  return user
}

export async function changePassword({ currentPassword, newPassword, confirmPassword }) {
  return request('/auth/password', {
    method: 'PUT',
    body: { currentPassword, newPassword, confirmPassword },
  })
}

/**
 * Re-read the signed-in user from the server.
 * Also confirms the stored token is still valid.
 */
export async function refreshSession() {
  const user = await request('/auth/me')

  const session = getStoredSession()
  if (session) storeSession({ ...session, user })

  return user
}
