/**
 * Complaint details and tracking.
 *
 * The same page serves all three roles; the action panel on the right is what
 * changes. A student can give feedback or reopen, an officer can move the
 * complaint through its workflow, and an administrator can reassign, change the
 * priority, escalate or close it.
 */

import {
  esc,
  formValues,
  html,
  icon,
  mount,
  on,
  qs,
  ready,
  setLoading,
} from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import {
  alertBox,
  errorState,
  escalationBadge,
  infoRow,
  loadingState,
  priorityBadge,
  starRating,
  statusBadge,
} from '../components/ui.js'
import { toast } from '../components/toast.js'
import { confirmDialog, openModal } from '../components/modal.js'
import { complaintTimeline } from '../components/timeline.js'
import { aiAnalysisCard } from '../components/aiCard.js'
import {
  deadlineBanner,
  evidenceGallery,
  hydrateMaps,
  mapPreview,
  officerCard,
  remarksThread,
} from '../components/complaintParts.js'
import { createFileUpload } from '../components/fileUpload.js'
import {
  addRemark,
  assignOfficer,
  changePriority,
  closeComplaint,
  escalateComplaint,
  getComplaintById,
  reopenComplaint,
  submitFeedback,
  submitResolution,
  updateEstimatedCompletion,
  updateStatus,
} from '../services/complaintService.js'
import { getOfficers } from '../services/officerService.js'
import {
  OFFICER_STATUS_OPTIONS,
  PRIORITY_LIST,
  ROLES,
  STATUS,
} from '../utils/constants.js'
import { formatDate, formatDateTime } from '../utils/helpers.js'

/** Which role this copy of the page is running as, from the folder it sits in. */
const ROLE = location.pathname.startsWith('/officer/')
  ? ROLES.OFFICER
  : location.pathname.startsWith('/admin/')
    ? ROLES.ADMIN
    : ROLES.STUDENT

const HOME = {
  [ROLES.STUDENT]: '/student/dashboard.html',
  [ROLES.OFFICER]: '/officer/dashboard.html',
  [ROLES.ADMIN]: '/admin/dashboard.html',
}[ROLE]

const LIST = {
  [ROLES.STUDENT]: '/student/complaints.html',
  [ROLES.OFFICER]: '/officer/complaints.html',
  [ROLES.ADMIN]: '/admin/complaints.html',
}[ROLE]

let complaint = null
let user = null

/* ============================================================ MAIN VIEW === */

function detailsView() {
  const isClosed = [STATUS.RESOLVED, STATUS.CLOSED].includes(complaint.status)

  return html(
    '<div class="stack">',
    deadlineBanner(complaint),

    complaint.escalationLevel > 0 && complaint.status === STATUS.ESCALATED
      ? alertBox({
          tone: 'danger',
          icon: 'shield-alert',
          title: `Escalated to Level ${complaint.escalationLevel}`,
          text: `This complaint is now with ${complaint.escalationAuthority}. It is ${complaint.daysOverdue} day(s) past its deadline.`,
        })
      : '',

    '<div class="split">',

    /* ------------------------------------------------------------ left */
    '<div class="stack">',

    // complaint information
    '<section class="card">',
    '<header class="card__head">',
    '<div class="grow" style="min-width:0">',
    `<p class="cell-id" style="font-size:var(--fs-sm)">${esc(complaint.id)}</p>`,
    `<h2 class="card__title" style="margin-top:.25rem">${esc(complaint.title)}</h2>`,
    '</div>',
    `<div class="row" style="gap:.5rem">${priorityBadge(complaint.priority)}${statusBadge(complaint.status)}</div>`,
    '</header>',
    '<div class="card__body">',
    `<p style="white-space:pre-line">${esc(complaint.description)}</p>`,
    '<div class="info-list" style="margin-top:var(--sp-5)">',
    infoRow('Department', esc(complaint.department)),
    infoRow('Category', esc(complaint.category)),
    infoRow('Location', esc(complaint.location?.address ?? '—')),
    infoRow('Campus zone', esc(complaint.location?.block || '—')),
    infoRow('Submitted on', esc(formatDateTime(complaint.submittedAt))),
    infoRow('Last updated', esc(formatDateTime(complaint.updatedAt))),
    ROLE !== ROLES.STUDENT
      ? infoRow(
          'Raised by',
          `${esc(complaint.submittedBy?.name)} <span class="cell-sub">${esc(complaint.submittedBy?.userId ?? '')}</span>`,
        )
      : '',
    ROLE !== ROLES.STUDENT
      ? infoRow(
          'Contact',
          `<a href="mailto:${esc(complaint.submittedBy?.email)}" style="word-break:break-all">${esc(complaint.submittedBy?.email)}</a>`,
        )
      : '',
    complaint.escalationLevel > 0
      ? infoRow('Escalation', `${escalationBadge(complaint.escalationLevel)} <span class="muted">${esc(complaint.escalationAuthority ?? '')}</span>`)
      : '',
    '</div></div></section>',

    // evidence
    '<section class="card">',
    `<header class="card__head"><h2 class="card__title">Evidence</h2>
       <span class="muted">${complaint.evidence.length} file${complaint.evidence.length === 1 ? '' : 's'}</span></header>`,
    `<div class="card__body">${evidenceGallery(complaint.evidence)}</div>`,
    '</section>',

    // timeline
    '<section class="card">',
    '<header class="card__head"><h2 class="card__title">Status timeline</h2></header>',
    `<div class="card__body">${complaintTimeline(complaint.timeline)}</div>`,
    '</section>',

    // remarks
    '<section class="card">',
    '<header class="card__head"><h2 class="card__title">Remarks</h2></header>',
    `<div class="card__body">${remarksThread(complaint.remarks)}</div>`,
    ROLE !== ROLES.STUDENT
      ? `<footer class="card__foot">
           <form id="remark-form" class="row" style="gap:var(--sp-2);align-items:flex-start">
             <label class="sr-only" for="remark">Add a remark</label>
             <input type="text" class="field__control" id="remark" name="message"
                    placeholder="Add a remark visible to the complainant…" required>
             <button type="submit" class="btn btn--primary">${icon('send', 'icon-sm')}Post</button>
           </form>
         </footer>`
      : '',
    '</section>',

    // resolution report
    complaint.resolution
      ? html(
          '<section class="card">',
          '<header class="card__head"><h2 class="card__title">Resolution report</h2></header>',
          '<div class="card__body">',
          `<p style="white-space:pre-line">${esc(complaint.resolution.notes)}</p>`,
          `<p class="muted" style="margin-top:var(--sp-3)">Completed by ${esc(complaint.resolution.completedBy)} on ${esc(formatDateTime(complaint.resolution.completedAt))}</p>`,
          complaint.resolution.proof?.length
            ? `<div style="margin-top:var(--sp-4)">${evidenceGallery(complaint.resolution.proof)}</div>`
            : '',
          '</div></section>',
        )
      : '',

    // feedback already given
    complaint.feedback
      ? html(
          '<section class="card">',
          '<header class="card__head"><h2 class="card__title">Feedback</h2></header>',
          '<div class="card__body">',
          starRating(complaint.feedback.rating),
          `<p style="margin-top:var(--sp-3)">${esc(complaint.feedback.comment)}</p>`,
          `<p class="muted" style="margin-top:var(--sp-2)">Submitted on ${esc(formatDate(complaint.feedback.at))}</p>`,
          '</div></section>',
        )
      : '',

    '</div>',

    /* ----------------------------------------------------------- right */
    '<div class="stack split__aside">',
    actionPanel(isClosed),

    '<section class="card">',
    '<header class="card__head"><h2 class="card__title">Assigned officer</h2></header>',
    `<div class="card__body">${officerCard(complaint.assignedOfficer)}</div>`,
    '</section>',

    '<section class="card">',
    '<header class="card__head"><h2 class="card__title">Location</h2></header>',
    `<div class="card__body">${mapPreview({ ...complaint.location })}</div>`,
    '</section>',

    complaint.ai ? aiAnalysisCard({ analysis: complaint.ai, readOnly: true }) : '',

    '</div>',
    '</div></div>',
  )
}

/* ========================================================= ACTION PANEL === */

function actionPanel(isClosed) {
  if (ROLE === ROLES.STUDENT) return studentActions(isClosed)
  if (ROLE === ROLES.OFFICER) return officerActions(isClosed)
  return adminActions()
}

function studentActions(isClosed) {
  if (!isClosed) {
    return html(
      '<section class="card">',
      '<header class="card__head"><h2 class="card__title">What happens next</h2></header>',
      '<div class="card__body">',
      '<p class="muted">Your complaint is being handled. You will be notified at every status change, and you can rate the work once it is resolved.</p>',
      `<a class="btn btn--secondary btn--block" style="margin-top:var(--sp-4)" href="${LIST}">${icon('clipboard-list', 'icon-sm')}All my complaints</a>`,
      '</div></section>',
    )
  }

  if (complaint.feedback) {
    return html(
      '<section class="card">',
      '<header class="card__head"><h2 class="card__title">Not satisfied?</h2></header>',
      '<div class="card__body">',
      '<p class="muted">You have already rated this resolution. If the problem has come back, you can reopen the complaint.</p>',
      `<button type="button" class="btn btn--warning btn--block" style="margin-top:var(--sp-4)" data-reopen>
         ${icon('rotate-ccw', 'icon-sm')}Reopen complaint</button>`,
      '</div></section>',
    )
  }

  return html(
    '<section class="card">',
    '<header class="card__head"><h2 class="card__title">Rate this resolution</h2></header>',
    '<div class="card__body">',
    '<form id="feedback-form" class="stack-sm" novalidate>',
    '<div class="field" data-field="rating">',
    '<span class="field__label">Your rating<span class="field__req">*</span></span>',
    `<div id="rating-widget">${starRating(0, { interactive: true })}</div>`,
    '<input type="hidden" name="rating" id="rating-value" value="0">',
    '</div>',
    '<div class="field" data-field="comment">',
    '<label class="field__label" for="comment">Comments<span class="field__req">*</span></label>',
    '<textarea class="field__control" id="comment" name="comment" rows="4" placeholder="Was the problem fixed properly? How was the response time?"></textarea>',
    '</div>',
    '<div id="satisfaction" hidden>',
    alertBox({
      tone: 'warning',
      icon: 'alert-triangle',
      title: 'I am not satisfied with the resolution',
      text: 'You can submit this rating and then reopen the complaint so the department looks at it again.',
    }),
    '</div>',
    `<button type="submit" class="btn btn--primary btn--block">${icon('send', 'icon-sm')}Submit feedback</button>`,
    `<button type="button" class="btn btn--secondary btn--block" data-reopen>${icon('rotate-ccw', 'icon-sm')}Reopen complaint</button>`,
    '</form>',
    '</div></section>',
  )
}

function officerActions(isClosed) {
  if (isClosed) {
    return html(
      '<section class="card">',
      '<header class="card__head"><h2 class="card__title">Complaint closed</h2></header>',
      '<div class="card__body">',
      '<p class="muted">This complaint has been resolved. No further action is required unless the complainant reopens it.</p>',
      '</div></section>',
    )
  }

  const options = OFFICER_STATUS_OPTIONS.map(
    (status) =>
      `<option value="${esc(status)}" ${complaint.status === status ? 'selected' : ''}>${esc(status)}</option>`,
  ).join('')

  const deadlineValue = new Date(complaint.deadline).toISOString().slice(0, 10)

  return html(
    '<section class="card">',
    '<header class="card__head"><h2 class="card__title">Manage this complaint</h2></header>',
    '<div class="card__body stack-sm">',

    complaint.status === STATUS.ASSIGNED
      ? `<button type="button" class="btn btn--primary btn--block" data-accept>
           ${icon('check-circle', 'icon-sm')}Accept complaint</button>`
      : '',

    '<div class="field">',
    '<label class="field__label" for="status-select">Change status</label>',
    `<select class="field__control" id="status-select">${options}</select>`,
    '</div>',
    `<button type="button" class="btn btn--secondary btn--block" data-status>${icon('refresh', 'icon-sm')}Update status</button>`,

    '<div class="field" style="margin-top:var(--sp-3)">',
    '<label class="field__label" for="deadline-input">Estimated completion</label>',
    `<input type="date" class="field__control" id="deadline-input" value="${esc(deadlineValue)}">`,
    '</div>',
    `<button type="button" class="btn btn--secondary btn--block" data-deadline>${icon('calendar-clock', 'icon-sm')}Update date</button>`,

    '<hr>',
    `<button type="button" class="btn btn--success btn--block" data-resolve>
       ${icon('check-circle', 'icon-sm')}Submit resolution</button>`,
    '</div></section>',
  )
}

function adminActions() {
  const priorities = PRIORITY_LIST.map(
    (priority) =>
      `<option value="${esc(priority)}" ${complaint.priority === priority ? 'selected' : ''}>${esc(priority)}</option>`,
  ).join('')

  const isClosed = [STATUS.RESOLVED, STATUS.CLOSED].includes(complaint.status)

  return html(
    '<section class="card">',
    '<header class="card__head"><h2 class="card__title">Administrative actions</h2></header>',
    '<div class="card__body stack-sm">',

    `<button type="button" class="btn btn--primary btn--block" data-assign>
       ${icon('user-cog', 'icon-sm')}${complaint.assignedOfficer ? 'Reassign officer' : 'Assign officer'}</button>`,

    '<div class="field" style="margin-top:var(--sp-2)">',
    '<label class="field__label" for="priority-select">Priority</label>',
    `<select class="field__control" id="priority-select">${priorities}</select>`,
    '<p class="field__hint">Changing the priority recalculates the deadline.</p>',
    '</div>',
    `<button type="button" class="btn btn--secondary btn--block" data-priority>${icon('zap', 'icon-sm')}Change priority</button>`,

    '<hr>',
    isClosed
      ? ''
      : `<button type="button" class="btn btn--warning btn--block" data-escalate>
           ${icon('shield-alert', 'icon-sm')}Escalate complaint</button>`,
    complaint.status === STATUS.CLOSED
      ? ''
      : `<button type="button" class="btn btn--danger btn--block" data-close>
           ${icon('x-circle', 'icon-sm')}Close complaint</button>`,
    '</div></section>',
  )
}

/* ============================================================== ACTIONS === */

/** Re-fetch and redraw after any change. */
async function refresh(message) {
  complaint = await getComplaintById(complaint.id)
  draw()
  if (message) toast.success(message, 'Updated')
}

function draw() {
  qs('#root').innerHTML =
    pageHeader({
      title: 'Complaint details',
      lead: complaint.title,
      crumbs: [
        { label: 'Dashboard', href: HOME },
        { label: 'Complaints', href: LIST },
        { label: complaint.id },
      ],
      actions: `<a class="btn btn--secondary" href="${LIST}">${icon('arrow-left', 'icon-sm')}Back to list</a>`,
    }) + detailsView()

  wire()
  hydrateMaps() // upgrades the location card to Leaflet when it is reachable
}

/* ---------------------------------------------------------- student bits */

function wireStudent() {
  const form = qs('#feedback-form')

  on('#rating-widget', 'click', '[data-star]', (event, button) => {
    const value = Number(button.dataset.star)
    qs('#rating-value').value = String(value)
    qs('#rating-widget').innerHTML = starRating(value, { interactive: true })
    qs('#satisfaction').hidden = value > 2
  })

  form?.addEventListener('submit', async (event) => {
    event.preventDefault()
    const values = formValues(form)
    const rating = Number(values.rating)
    const button = qs('button[type="submit"]', form)

    if (!rating) {
      toast.warning('Please select a star rating first.', 'Rating required')
      return
    }
    if (!values.comment || values.comment.length < 10) {
      toast.warning('Please write a short comment (at least 10 characters).', 'Comment required')
      return
    }

    setLoading(button, true, 'Submitting…')
    try {
      await submitFeedback(complaint.id, {
        rating,
        comment: values.comment,
        satisfied: rating >= 3,
      })
      await refresh('Thank you for your feedback.')
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message)
    }
  })

  on('#root', 'click', '[data-reopen]', async () => {
    const confirmed = await confirmDialog({
      title: 'Reopen this complaint?',
      message: 'The complaint will go back to the department with its full history attached, and a fresh deadline will be set.',
      confirmLabel: 'Reopen complaint',
      tone: 'warning',
    })
    if (!confirmed) return

    try {
      await reopenComplaint(complaint.id, 'The problem has not been resolved satisfactorily.', user.name)
      await refresh('The complaint has been reopened.')
    } catch (error) {
      toast.error(error.message)
    }
  })
}

/* ---------------------------------------------------------- officer bits */

function wireOfficer() {
  on('#root', 'click', '[data-accept]', async (event, button) => {
    setLoading(button, true, 'Accepting…')
    try {
      await updateStatus(complaint.id, STATUS.ACCEPTED, {
        actor: user.name,
        note: 'The officer has accepted this complaint and will begin work.',
      })
      await refresh('Complaint accepted.')
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message)
    }
  })

  on('#root', 'click', '[data-status]', async (event, button) => {
    const status = qs('#status-select').value
    if (status === complaint.status) {
      toast.info('The complaint is already in that status.')
      return
    }

    setLoading(button, true, 'Updating…')
    try {
      await updateStatus(complaint.id, status, { actor: user.name })
      await refresh(`Status changed to ${status}.`)
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message)
    }
  })

  on('#root', 'click', '[data-deadline]', async (event, button) => {
    const value = qs('#deadline-input').value
    if (!value) {
      toast.warning('Choose a date first.')
      return
    }

    setLoading(button, true, 'Saving…')
    try {
      await updateEstimatedCompletion(complaint.id, value, user.name)
      await refresh('Estimated completion date updated.')
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message)
    }
  })

  on('#root', 'click', '[data-resolve]', () => openResolutionDialog())

  on('#remark-form', 'submit', async (event) => {
    event.preventDefault()
    await postRemark(event.target)
  })
}

function openResolutionDialog() {
  const modal = openModal({
    title: 'Submit resolution',
    description: 'Describe the work done and attach proof if you have it.',
    size: 'lg',
    body: `
      <form id="resolution-form" novalidate class="stack-sm">
        <div class="field" data-field="notes">
          <label class="field__label" for="notes">Resolution notes<span class="field__req">*</span></label>
          <textarea class="field__control" id="notes" name="notes" rows="5" required
                    placeholder="What was wrong, what was done, and what was tested afterwards."></textarea>
          <p class="field__hint">This is shown to the complainant, so write it in plain language.</p>
        </div>
        <div id="proof-upload"></div>
      </form>`,
    footer: `
      <button type="button" class="btn btn--secondary" data-close>Cancel</button>
      <button type="button" class="btn btn--success" data-confirm-resolve>
        ${icon('check-circle', 'icon-sm')}Mark as resolved
      </button>`,
  })

  const proof = createFileUpload('#proof-upload', {
    label: 'Proof of work (optional)',
    maxFiles: 3,
  })

  on(modal.element, 'click', '[data-confirm-resolve]', async (event, button) => {
    const notes = qs('#notes', modal.element).value.trim()
    if (notes.length < 15) {
      toast.warning('Please describe the work done in at least 15 characters.', 'Notes required')
      return
    }

    const confirmed = await confirmDialog({
      title: 'Mark this complaint as resolved?',
      message: 'The complainant will be notified and asked to rate the work. This cannot be undone by you.',
      confirmLabel: 'Yes, mark resolved',
      tone: 'success',
    })
    if (!confirmed) return

    setLoading(button, true, 'Submitting…')
    try {
      await submitResolution(complaint.id, { notes, proof: proof.files(), officer: user })
      modal.close()
      await refresh('Resolution submitted. The complainant has been notified.')
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message)
    }
  })
}

/* ------------------------------------------------------------ admin bits */

function wireAdmin() {
  on('#root', 'click', '[data-assign]', () => openAssignDialog())

  on('#root', 'click', '[data-priority]', async (event, button) => {
    const priority = qs('#priority-select').value
    if (priority === complaint.priority) {
      toast.info('That is already the current priority.')
      return
    }

    setLoading(button, true, 'Saving…')
    try {
      await changePriority(complaint.id, priority, user.name)
      await refresh(`Priority changed to ${priority}.`)
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message)
    }
  })

  on('#root', 'click', '[data-escalate]', async () => {
    const confirmed = await confirmDialog({
      title: 'Escalate this complaint?',
      message: 'The complaint moves to the next authority level and everyone involved is notified.',
      confirmLabel: 'Escalate',
      tone: 'warning',
    })
    if (!confirmed) return

    try {
      await escalateComplaint(complaint.id, user.name)
      await refresh('Complaint escalated.')
    } catch (error) {
      toast.error(error.message)
    }
  })

  on('#root', 'click', '[data-close]', async () => {
    const confirmed = await confirmDialog({
      title: 'Close this complaint?',
      message: 'A closed complaint is removed from the active queues. The complainant can still reopen it.',
      confirmLabel: 'Close complaint',
      tone: 'danger',
    })
    if (!confirmed) return

    try {
      await closeComplaint(complaint.id, user.name)
      await refresh('Complaint closed.')
    } catch (error) {
      toast.error(error.message)
    }
  })

  on('#remark-form', 'submit', async (event) => {
    event.preventDefault()
    await postRemark(event.target)
  })
}

async function openAssignDialog() {
  const modal = openModal({
    title: 'Assign an officer',
    description: 'Officers are listed with their current workload — the lightest first.',
    size: 'lg',
    body: loadingState('Loading officers…'),
  })

  try {
    const officers = await getOfficers({ activeOnly: true })
    const sorted = [...officers].sort((a, b) => a.workload.active - b.workload.active)

    qs('.modal__body', modal.element).innerHTML = `
      <form id="assign-form">
        <div class="radio-cards" style="grid-template-columns:1fr">
          ${sorted
            .map(
              (officer) => `
            <label class="radio-card">
              <input type="radio" name="officerId" value="${esc(officer.id)}"
                     ${complaint.assignedOfficer?.id === officer.id ? 'checked' : ''}>
              <span class="grow" style="min-width:0">
                <span class="radio-card__title">${esc(officer.name)}</span>
                <span class="radio-card__desc">${esc(officer.designation)} · ${esc(officer.department)}</span>
                <span class="workload" style="margin-top:.5rem">
                  <span class="workload__count">${officer.workload.active}</span>
                  <span class="muted" style="font-size:var(--fs-xs)">active complaints</span>
                </span>
              </span>
            </label>`,
            )
            .join('')}
        </div>
      </form>`

    qs('.modal__foot', modal.element)?.remove()
    modal.panel.insertAdjacentHTML(
      'beforeend',
      `<footer class="modal__foot">
         <button type="button" class="btn btn--secondary" data-close>Cancel</button>
         <button type="button" class="btn btn--primary" data-confirm-assign>${icon('user-check', 'icon-sm')}Assign officer</button>
       </footer>`,
    )

    on(modal.element, 'click', '[data-confirm-assign]', async (event, button) => {
      const chosen = qs('input[name="officerId"]:checked', modal.element)
      if (!chosen) {
        toast.warning('Select an officer first.')
        return
      }

      setLoading(button, true, 'Assigning…')
      try {
        await assignOfficer(complaint.id, chosen.value, user.name)
        modal.close()
        await refresh('Officer assigned.')
      } catch (error) {
        setLoading(button, false)
        toast.error(error.message)
      }
    })
  } catch (error) {
    qs('.modal__body', modal.element).innerHTML = errorState({ message: error.message })
  }
}

/* ------------------------------------------------------------- shared --- */

async function postRemark(form) {
  const input = qs('#remark', form)
  const message = input.value.trim()
  if (!message) return

  const button = qs('button[type="submit"]', form)
  setLoading(button, true, 'Posting…')

  try {
    await addRemark(complaint.id, {
      message,
      author: user.name,
      role: ROLE === ROLES.ADMIN ? 'Admin' : 'Officer',
    })
    await refresh('Remark added.')
  } catch (error) {
    setLoading(button, false)
    toast.error(error.message)
  }
}

function wire() {
  if (ROLE === ROLES.STUDENT) wireStudent()
  else if (ROLE === ROLES.OFFICER) wireOfficer()
  else wireAdmin()
}

/* ================================================================ BOOT === */

async function load(id) {
  mount('#root', loadingState('Loading complaint details…'))

  try {
    complaint = await getComplaintById(id)
    draw()
  } catch (error) {
    mount(
      '#root',
      errorState({
        title: 'Unable to load complaint details',
        message: error.message,
        retryId: 'retry',
      }),
    )
    qs('#retry')?.addEventListener('click', () => load(id))
  }
}

ready(() => {
  user = requireRole(ROLE)
  if (!user) return

  renderShell(user, { title: 'Complaint Details' })

  const id = new URLSearchParams(location.search).get('id')
  if (!id) {
    mount(
      '#root',
      errorState({
        title: 'No complaint selected',
        message: 'Open a complaint from the list to see its details.',
      }),
    )
    return
  }

  load(id)
})
