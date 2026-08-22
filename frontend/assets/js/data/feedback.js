/**
 * Feedback records.
 *
 * Feedback is always attached to a complaint, so the list is derived from the
 * seeded complaints rather than duplicated. The admin analytics screen uses
 * this flattened view.
 */

import { complaints } from './complaints.js'

export const feedbackEntries = complaints
  .filter((complaint) => complaint.feedback)
  .map((complaint) => ({
    id: `FB-${complaint.id.slice(-5)}`,
    complaintId: complaint.id,
    complaintTitle: complaint.title,
    department: complaint.department,
    officer: complaint.assignedOfficer?.name ?? '—',
    student: complaint.submittedBy.name,
    rating: complaint.feedback.rating,
    comment: complaint.feedback.comment,
    satisfied: complaint.feedback.satisfied,
    at: complaint.feedback.at,
  }))
  .sort((a, b) => new Date(b.at) - new Date(a.at))

/** Average star rating across all feedback. */
export function averageRating(entries = feedbackEntries) {
  if (!entries.length) return 0
  const total = entries.reduce((sum, entry) => sum + entry.rating, 0)
  return Number((total / entries.length).toFixed(2))
}

export default feedbackEntries
