/**
 * User service - students, staff and the account directory used by the admin.
 *
 *   GET /api/users            ?search= &userType= &department=
 *   GET /api/users/summary
 *   GET /api/users/:id
 *   PUT /api/users/:id/status
 */

import { request } from './mockApi.js'

/** Students and staff, with the number of complaints each has raised. */
export async function getUsers({ search = '', userType = '', department = '' } = {}) {
  return request('/users', { query: { search, userType, department } })
}

export async function getUserById(id) {
  return request(`/users/${encodeURIComponent(id)}`)
}

export async function toggleUserStatus(id) {
  return request(`/users/${encodeURIComponent(id)}/status`, { method: 'PUT', body: {} })
}

/** Headline counts for the admin "Students & Staff" page. */
export async function getUserSummary() {
  return request('/users/summary')
}

/** Create a student or staff account from the admin screen. */
export async function createUser(values) {
  return request('/users', { method: 'POST', body: values })
}
