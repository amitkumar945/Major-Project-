/**
 * Complaint lifecycle timeline.
 *
 * The tracking screen renders a fixed seven-stage journey. This module decides
 * how far a complaint has travelled along that journey and produces the list of
 * timeline entries with their timestamps and responsible person.
 */

import { STATUS } from './constants.js'
import { uid } from './helpers.js'

/** The canonical stages every complaint passes through. */
export const TIMELINE_STAGES = [
  {
    key: 'submitted',
    label: 'Complaint Submitted',
    description: 'Grievance registered on the portal and reference number generated.',
  },
  {
    key: 'classified',
    label: 'AI Classified',
    description: 'Department, priority and duplicate probability predicted automatically.',
  },
  {
    key: 'department',
    label: 'Assigned to Department',
    description: 'Routed to the responsible department for action.',
  },
  {
    key: 'officer',
    label: 'Officer Assigned',
    description: 'A department officer took ownership of the complaint.',
  },
  {
    key: 'started',
    label: 'Work Started',
    description: 'Field work or repair has begun on site.',
  },
  {
    key: 'resolution',
    label: 'Resolution Submitted',
    description: 'Officer submitted the resolution report and proof of work.',
  },
  {
    key: 'resolved',
    label: 'Resolved',
    description: 'Complaint closed and the complainant notified for feedback.',
  },
]

/**
 * How many stages are complete for a given status.
 * Returns an index into TIMELINE_STAGES (0 = only "Submitted" is done).
 */
export function stageIndexForStatus(status) {
  switch (status) {
    case STATUS.SUBMITTED:
      return 0
    case STATUS.UNDER_REVIEW:
      return 1
    case STATUS.ASSIGNED:
      return 2
    case STATUS.ACCEPTED:
      return 3
    case STATUS.IN_PROGRESS:
    case STATUS.PENDING:
    case STATUS.ESCALATED:
      return 4
    case STATUS.REOPENED:
      return 5
    case STATUS.RESOLVED:
    case STATUS.CLOSED:
      return 6
    default:
      return 0
  }
}

/**
 * Build the timeline for a complaint.
 *
 * Completed stages get a real timestamp spread between submission and the last
 * update; future stages are returned as `pending` so the UI can grey them out.
 */
export function buildTimeline(complaint) {
  const reached = stageIndexForStatus(complaint.status)
  const start = new Date(complaint.submittedAt).getTime()
  const end = new Date(complaint.updatedAt ?? complaint.submittedAt).getTime()
  const span = Math.max(end - start, 60 * 60 * 1000)

  const officerName = complaint.assignedOfficer?.name
  const actors = {
    submitted: complaint.submittedBy?.name ?? 'Complainant',
    classified: 'AI Classification Engine',
    department: 'Grievance Redressal Cell',
    officer: officerName ?? 'Department Head',
    started: officerName ?? 'Department Officer',
    resolution: officerName ?? 'Department Officer',
    resolved: 'Grievance Redressal Cell',
  }

  const entries = TIMELINE_STAGES.map((stage, index) => {
    const done = index <= reached
    // Spread completed stages evenly across the complaint's lifetime.
    const at = done
      ? new Date(start + (span * index) / Math.max(reached, 1)).toISOString()
      : null

    return {
      id: `${complaint.id}-${stage.key}`,
      key: stage.key,
      label: stage.label,
      description: stage.description,
      actor: actors[stage.key],
      at,
      state: index < reached ? 'done' : index === reached ? 'current' : 'pending',
    }
  })

  // Escalation and reopening are exceptions, so they are appended as extra rows.
  if (complaint.status === STATUS.ESCALATED) {
    entries.push({
      id: `${complaint.id}-escalated`,
      key: 'escalated',
      label: `Escalated to Level ${complaint.escalationLevel ?? 2}`,
      description:
        'Resolution deadline was exceeded, so the complaint moved to a higher authority.',
      actor: complaint.escalationAuthority ?? 'Department Head',
      at: complaint.updatedAt,
      state: 'current',
      variant: 'danger',
    })
  }

  if (complaint.status === STATUS.REOPENED) {
    entries.push({
      id: `${complaint.id}-reopened`,
      key: 'reopened',
      label: 'Complaint Reopened',
      description:
        'The complainant was not satisfied with the resolution and reopened the complaint.',
      actor: complaint.submittedBy?.name ?? 'Complainant',
      at: complaint.updatedAt,
      state: 'current',
      variant: 'warning',
    })
  }

  return entries
}

/**
 * Create a single extra timeline row.
 * Used when an officer or admin performs an action inside the running app.
 */
export function makeTimelineEntry({ label, description, actor, variant }) {
  return {
    id: uid('tl'),
    key: 'update',
    label,
    description,
    actor,
    at: new Date().toISOString(),
    state: 'done',
    variant,
  }
}
