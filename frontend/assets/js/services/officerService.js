/**
 * Officer service.
 *
 * The officer directory with live workload figures, plus the admin actions:
 * add officer, edit officer, activate/deactivate and reassign department.
 *
 *   GET  /api/officers            ?department= &activeOnly= &search=
 *   GET  /api/officers/suggest    ?department=
 *   GET  /api/officers/:id        /complaints  /workload
 *   POST /api/officers            create
 *   PUT  /api/officers/:id        /status
 *
 * Workload is computed server-side from the real complaint counts, so the
 * "smart assignment" suggestion now reflects actual open work.
 */

import { request } from './mockApi.js'

export async function getOfficers({ department = '', search = '', activeOnly = false } = {}) {
  return request('/officers', { query: { department, search, activeOnly } })
}

export async function getOfficerById(id) {
  return request(`/officers/${encodeURIComponent(id)}`)
}

/**
 * The officer in a department with the lightest active workload.
 * Returns null when the department has no active officer.
 */
export async function suggestOfficer(department) {
  try {
    return await request('/officers/suggest', { query: { department } })
  } catch (error) {
    if (error.status === 404) return null
    throw error
  }
}

/** One officer's complaint queue. */
export async function getOfficerComplaints(id, options = {}) {
  return request(`/officers/${encodeURIComponent(id)}/complaints`, { query: options })
}

export async function createOfficer(values) {
  return request('/officers', { method: 'POST', body: values })
}

export async function updateOfficer(id, changes) {
  return request(`/officers/${encodeURIComponent(id)}`, { method: 'PUT', body: changes })
}

/** Toggle the account between active and inactive. */
export async function toggleOfficerStatus(id) {
  return request(`/officers/${encodeURIComponent(id)}/status`, { method: 'PUT', body: {} })
}
