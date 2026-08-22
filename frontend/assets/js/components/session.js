/**
 * Session helpers used by every protected page.
 *
 * This is the vanilla equivalent of the React AuthContext: one place that
 * knows who is signed in, and one place that decides whether a page may be
 * shown at all.
 */

import { getStoredSession, logout as serviceLogout } from '../services/authService.js'
import { ROLE_LABELS } from '../utils/constants.js'
import { HOME_PAGE } from './navigation.js'

/** The signed-in user, or null. */
export function currentUser() {
  return getStoredSession()?.user ?? null
}

export function isSignedIn() {
  return Boolean(currentUser())
}

export function roleLabel(role) {
  return ROLE_LABELS[role] ?? 'User'
}

/**
 * Guard a page. Call this at the top of every dashboard script.
 *
 *   const user = requireRole('student')
 *
 * If nobody is signed in the visitor is sent to the login page and returned
 * here afterwards. If the wrong role is signed in they are sent to their own
 * dashboard instead, so a student can never open an admin screen.
 *
 * @returns {object|null} the user, or null when a redirect is happening
 */
export function requireRole(role) {
  const user = currentUser()

  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search)
    location.replace(`/login.html?next=${next}`)
    return null
  }

  if (role && user.role !== role) {
    location.replace(HOME_PAGE[user.role] ?? '/login.html')
    return null
  }

  return user
}

/** Sign out and return to the landing page. */
export async function signOut() {
  await serviceLogout()
  location.href = '/index.html'
}
