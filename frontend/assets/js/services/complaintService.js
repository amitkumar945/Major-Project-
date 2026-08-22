/**
 * Complaint service.
 *
 * Talks to the Flask API. Every function keeps the signature it had while the
 * data was mocked, so no page or component needed changing:
 *
 *   GET    /api/complaints              filter / sort / paginate
 *   GET    /api/complaints/:id
 *   GET    /api/complaints/track/:ref   public tracking
 *   POST   /api/complaints              create (JSON or multipart with files)
 *   PUT    /api/complaints/:id/status   /priority  /deadline  /reassign
 *   POST   /api/complaints/:id/remarks  /resolve  /assign  /escalate
 *                                       /close  /reopen  /feedback
 *   POST   /api/ai/classify             /duplicates
 *
 * The AI prediction now runs on the server; `analyseComplaint()` returns the
 * same object shape the AI card already renders.
 */

import { request, upload } from './mockApi.js'

/* --------------------------------------------------------------- queries */

/**
 * Filter, sort and paginate complaints.
 * Returns `{ items, total, page, pageSize, totalPages }`.
 *
 * @param {object} options - search, department, priority, status, category,
 *   dateFrom, dateTo, userId, officerId, onlyActive, sortBy, sortDir,
 *   page, pageSize
 */
export async function getComplaints(options = {}) {
  return request('/complaints', { query: options })
}

/** Every complaint matching the filters, without pagination (for charts). */
export async function getAllComplaints(options = {}) {
  const result = await request('/complaints', {
    query: { ...options, page: 1, pageSize: 10000 },
  })
  return result.items
}

/** Complaints raised by the signed-in student. */
export async function getMyComplaints(options = {}) {
  return request('/complaints/my', { query: options })
}

/** The signed-in officer's work queue. */
export async function getAssignedComplaints(options = {}) {
  return request('/complaints/assigned', { query: options })
}

export async function getComplaintById(id) {
  return request(`/complaints/${encodeURIComponent(id)}`)
}

/** Public tracking lookup - no sign-in required. */
export async function trackComplaint(referenceId) {
  return request(`/complaints/track/${encodeURIComponent(referenceId.trim().toUpperCase())}`)
}

/**
 * Summary counters for the dashboard cards.
 * `scope` narrows the source list: { userId } | { officerId } | { department }.
 */
export async function getStatistics(scope = {}) {
  return request('/complaints/statistics', { query: scope })
}

/** Complaints that have crossed their deadline, for the escalation screen. */
export async function getEscalations() {
  return request('/complaints/escalations')
}

/** Timeline, remarks and assignment history for one complaint. */
export async function getComplaintHistory(id) {
  return request(`/complaints/${encodeURIComponent(id)}/history`)
}

/* -------------------------------------------------------------------- AI */

/**
 * Server-side classification: department, priority, duplicates and the
 * suggested officer. Same response shape the AI card already reads.
 */
export async function analyseComplaint({ title = '', description = '', category = '' }) {
  return request('/ai/classify', {
    method: 'POST',
    body: { title, description, category },
  })
}

/** Complaints that look like the one being written. */
export async function findDuplicates({ title = '', description = '', department = '' }) {
  const result = await request('/ai/duplicates', {
    method: 'POST',
    body: { title, description, department },
  })
  // The AI card expects a bare list.
  return result.duplicates ?? result.matches ?? []
}

/* ---------------------------------------------------------------- writes */

/**
 * Register a new complaint.
 *
 * When the form carries evidence files the request goes out as
 * multipart/form-data so the files upload in the same call; otherwise it is a
 * plain JSON POST.
 *
 * @param {object} payload - the five-step form draft
 * @param {object} user    - kept for signature compatibility; the server
 *                           identifies the complainant from the JWT
 */
export async function createComplaint(payload, user) {
  const files = (payload.evidence ?? [])
    .map((item) => item.file)
    .filter(Boolean)

  const fields = {
    title: payload.title,
    description: payload.description,
    category: payload.category,
    department: payload.department ?? '',
    location: payload.location ?? {},
  }

  if (files.length) {
    return upload('/complaints', files, fields)
  }

  return request('/complaints', { method: 'POST', body: fields })
}

/** Change status and append a timeline entry describing the change. */
export async function updateStatus(id, status, { actor, note } = {}) {
  return request(`/complaints/${encodeURIComponent(id)}/status`, {
    method: 'PUT',
    body: { status, note },
  })
}

export async function addRemark(id, { message, author, role }) {
  return request(`/complaints/${encodeURIComponent(id)}/remarks`, {
    method: 'POST',
    body: { message },
  })
}

/** Officer submits the resolution report and marks the complaint resolved. */
export async function submitResolution(id, { notes, proof = [], officer }) {
  const files = proof.map((item) => item.file).filter(Boolean)

  if (files.length) {
    return upload(`/complaints/${encodeURIComponent(id)}/resolve`, files, { notes })
  }

  return request(`/complaints/${encodeURIComponent(id)}/resolve`, {
    method: 'POST',
    body: { notes },
  })
}

/** Officer updates the promised completion date. */
export async function updateEstimatedCompletion(id, deadline, actor) {
  return request(`/complaints/${encodeURIComponent(id)}/deadline`, {
    method: 'PUT',
    body: { deadline: new Date(deadline).toISOString() },
  })
}

/** Admin assigns (or reassigns) a complaint to an officer. */
export async function assignOfficer(id, officerId, actor) {
  return request(`/complaints/${encodeURIComponent(id)}/assign`, {
    method: 'POST',
    body: { officerId },
  })
}

export async function changePriority(id, priority, actor) {
  return request(`/complaints/${encodeURIComponent(id)}/priority`, {
    method: 'PUT',
    body: { priority },
  })
}

export async function escalateComplaint(id, actor) {
  return request(`/complaints/${encodeURIComponent(id)}/escalate`, {
    method: 'POST',
    body: {},
  })
}

export async function closeComplaint(id, actor) {
  return request(`/complaints/${encodeURIComponent(id)}/close`, {
    method: 'POST',
    body: {},
  })
}

/** Complainant reopens a resolved complaint they are not satisfied with. */
export async function reopenComplaint(id, reason, actor) {
  return request(`/complaints/${encodeURIComponent(id)}/reopen`, {
    method: 'POST',
    body: { reason },
  })
}

/** Complainant rates the resolution. */
export async function submitFeedback(id, { rating, comment, satisfied }) {
  return request(`/complaints/${encodeURIComponent(id)}/feedback`, {
    method: 'POST',
    body: { rating, comment, satisfied },
  })
}

/** Attach further evidence to an existing complaint. */
export async function addEvidence(id, files) {
  return upload(`/complaints/${encodeURIComponent(id)}/evidence`, files)
}

/**
 * Delete every complaint, notification and rating (admin only).
 *
 * With the real backend this permanently removes rows from MongoDB - it is no
 * longer the harmless localStorage reset it was in the prototype. The admin
 * settings screen already asks for confirmation before calling it.
 */
export async function resetDemoData() {
  return request('/admin/reset-data', { method: 'POST', body: { confirm: true } })
}
