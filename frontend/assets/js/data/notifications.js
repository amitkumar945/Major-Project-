/**
 * Mock notification feed.
 *
 * Notifications are generated from the seeded complaints so that every alert a
 * user sees actually corresponds to a complaint that exists in the system.
 * Each notification carries a `recipientId`, which is how the notification
 * service filters the feed per logged-in user.
 */

import { NOTIFICATION_TYPES, STATUS } from '../utils/constants.js'
import { daysUntil } from '../utils/helpers.js'
import { complaints } from './complaints.js'
import { admins } from './users.js'

const ADMIN_ID = admins[0].id

/** Shift a complaint timestamp slightly so alerts do not share one instant. */
function offsetTime(iso, minutes) {
  return new Date(new Date(iso).getTime() + minutes * 60 * 1000).toISOString()
}

function make(recipientId, type, title, message, complaint, at, read) {
  return {
    id: `NTF-${complaint.id.slice(-5)}-${type}-${recipientId.slice(-4)}`,
    recipientId,
    type,
    title,
    message,
    complaintId: complaint.id,
    createdAt: at,
    read,
  }
}

/**
 * Build every notification implied by a complaint's current state.
 * Older complaints are marked as already read so the unread badge stays
 * realistic instead of showing every notification as new.
 */
function notificationsForComplaint(complaint) {
  const items = []
  const studentId = complaint.submittedBy.id
  const officerId = complaint.assignedOfficer?.id
  const ageDays = Math.abs(daysUntil(complaint.submittedAt))
  const seen = ageDays > 5

  items.push(
    make(
      studentId,
      NOTIFICATION_TYPES.SUBMITTED,
      'Complaint registered successfully',
      `Your complaint "${complaint.title}" has been registered with reference ${complaint.id}.`,
      complaint,
      complaint.submittedAt,
      seen,
    ),
  )

  if (officerId) {
    items.push(
      make(
        studentId,
        NOTIFICATION_TYPES.OFFICER_ASSIGNED,
        'Officer assigned to your complaint',
        `${complaint.assignedOfficer.name} (${complaint.assignedOfficer.designation}) is now handling ${complaint.id}.`,
        complaint,
        offsetTime(complaint.submittedAt, 180),
        seen,
      ),
    )
    items.push(
      make(
        officerId,
        NOTIFICATION_TYPES.ASSIGNED,
        'New complaint assigned to you',
        `${complaint.id} - ${complaint.title} has been assigned to you with ${complaint.priority} priority.`,
        complaint,
        offsetTime(complaint.submittedAt, 185),
        seen,
      ),
    )
  }

  if (complaint.status === STATUS.IN_PROGRESS) {
    items.push(
      make(
        studentId,
        NOTIFICATION_TYPES.STATUS_CHANGED,
        'Status updated to In Progress',
        `Work has started on ${complaint.id}. You will be notified once the resolution is submitted.`,
        complaint,
        complaint.updatedAt,
        false,
      ),
    )
  }

  if (complaint.resolution) {
    items.push(
      make(
        studentId,
        NOTIFICATION_TYPES.RESOLUTION_SUBMITTED,
        'Resolution report submitted',
        `${complaint.assignedOfficer?.name ?? 'The department officer'} submitted a resolution report for ${complaint.id}.`,
        complaint,
        offsetTime(complaint.resolution.completedAt, -90),
        seen,
      ),
    )
  }

  if (complaint.status === STATUS.RESOLVED || complaint.status === STATUS.CLOSED) {
    items.push(
      make(
        studentId,
        NOTIFICATION_TYPES.RESOLVED,
        'Complaint resolved',
        `${complaint.id} has been marked as resolved. Please review the work done.`,
        complaint,
        complaint.resolvedAt ?? complaint.updatedAt,
        seen,
      ),
    )
    if (!complaint.feedback) {
      items.push(
        make(
          studentId,
          NOTIFICATION_TYPES.FEEDBACK_REQUESTED,
          'Your feedback is requested',
          `Please rate the resolution provided for ${complaint.id}. Your feedback helps us improve campus services.`,
          complaint,
          offsetTime(complaint.resolvedAt ?? complaint.updatedAt, 60),
          false,
        ),
      )
    }
  }

  const remaining = daysUntil(complaint.deadline)
  const open = ![STATUS.RESOLVED, STATUS.CLOSED].includes(complaint.status)

  if (open && remaining >= 0 && remaining <= 1 && officerId) {
    items.push(
      make(
        officerId,
        NOTIFICATION_TYPES.DEADLINE_APPROACHING,
        'Resolution deadline approaching',
        `${complaint.id} must be resolved within ${remaining === 0 ? 'today' : '1 day'}.`,
        complaint,
        offsetTime(complaint.deadline, -720),
        false,
      ),
    )
  }

  if (complaint.status === STATUS.ESCALATED) {
    const escalationMessage = `${complaint.id} crossed its deadline by ${complaint.daysOverdue} day(s) and has been escalated to Level ${complaint.escalationLevel} - ${complaint.escalationAuthority}.`
    items.push(
      make(studentId, NOTIFICATION_TYPES.ESCALATED, 'Your complaint has been escalated', escalationMessage, complaint, complaint.updatedAt, false),
    )
    items.push(
      make(ADMIN_ID, NOTIFICATION_TYPES.ESCALATED, 'Complaint escalated', escalationMessage, complaint, complaint.updatedAt, false),
    )
    if (officerId) {
      items.push(
        make(officerId, NOTIFICATION_TYPES.ESCALATED, 'Escalation raised on your complaint', escalationMessage, complaint, complaint.updatedAt, false),
      )
    }
  }

  if (complaint.status === STATUS.REOPENED) {
    const reopenMessage = `${complaint.id} was reopened by the complainant because the resolution was not satisfactory.`
    if (officerId) {
      items.push(
        make(officerId, NOTIFICATION_TYPES.STATUS_CHANGED, 'Complaint reopened', reopenMessage, complaint, complaint.updatedAt, false),
      )
    }
    items.push(
      make(ADMIN_ID, NOTIFICATION_TYPES.STATUS_CHANGED, 'Complaint reopened', reopenMessage, complaint, complaint.updatedAt, false),
    )
  }

  return items
}

/** Newest first, which is the order the notification page renders. */
export const notifications = complaints
  .flatMap(notificationsForComplaint)
  .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))

export default notifications
