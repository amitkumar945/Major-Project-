/**
 * Department service.
 *
 * The department master list together with live complaint counters, plus the
 * create / update / delete actions on the admin screen.
 *
 *   GET    /api/departments          ?activeOnly=
 *   GET    /api/departments/:code
 *   POST   /api/departments
 *   PUT    /api/departments/:code    /status
 *   DELETE /api/departments/:code
 *
 * Counters (total, resolved, pending, escalated, resolutionRate) are computed
 * server-side from the real complaint collection.
 */

import { request } from './mockApi.js'

/** Department list enriched with officer count and complaint counters. */
export async function getDepartments({ activeOnly = false } = {}) {
  return request('/departments', { query: { activeOnly } })
}

export async function getDepartmentByCode(code) {
  return request(`/departments/${encodeURIComponent(code)}`)
}

export async function createDepartment(values) {
  return request('/departments', { method: 'POST', body: values })
}

export async function updateDepartment(code, changes) {
  return request(`/departments/${encodeURIComponent(code)}`, { method: 'PUT', body: changes })
}

export async function deleteDepartment(code) {
  return request(`/departments/${encodeURIComponent(code)}`, { method: 'DELETE' })
}

/** Activate or deactivate a department without deleting it. */
export async function toggleDepartmentStatus(code) {
  return request(`/departments/${encodeURIComponent(code)}/status`, { method: 'PUT', body: {} })
}
