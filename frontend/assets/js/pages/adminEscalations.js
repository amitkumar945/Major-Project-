/**
 * Escalation management - every complaint that has crossed its deadline,
 * with how far overdue it is and which authority now owns it.
 */

import { esc, icon, mount, on, qs, ready } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import {
  alertBox,
  emptyState,
  errorState,
  escalationBadge,
  loadingState,
  priorityBadge,
  statCard,
  statusBadge,
} from '../components/ui.js'
import { confirmDialog } from '../components/modal.js'
import { toast } from '../components/toast.js'
import { escalateComplaint, getEscalations } from '../services/complaintService.js'
import { ESCALATION_LEVELS, ROLES } from '../utils/constants.js'
import { formatDate } from '../utils/helpers.js'

const DETAILS = '/admin/complaint-details.html'

function ladder() {
  return `
    <section class="card">
      <header class="card__head">
        <div>
          <h2 class="card__title">Escalation ladder</h2>
          <p class="card__subtitle">Who owns a complaint as it ages past its deadline</p>
        </div>
      </header>
      <div class="card__body">
        <ol class="grid grid-3">
          ${ESCALATION_LEVELS.map(
            (rule) => `
            <li class="card" style="padding:var(--sp-4);box-shadow:none">
              <div class="row" style="gap:.625rem">
                ${escalationBadge(rule.level)}
                <span class="strong">${esc(rule.authority)}</span>
              </div>
              <p class="muted" style="font-size:var(--fs-xs);margin-top:.5rem">
                ${
                  rule.afterDays === 0
                    ? 'From the moment the deadline is missed'
                    : `Once the complaint is ${rule.afterDays}+ days overdue`
                }
              </p>
            </li>`,
          ).join('')}
        </ol>
      </div>
    </section>`
}

function row(complaint) {
  return `
    <tr>
      <td><a class="cell-id" href="${DETAILS}?id=${encodeURIComponent(complaint.id)}">${esc(complaint.id)}</a></td>
      <td>
        <span class="strong">${esc(complaint.title)}</span>
        <span class="cell-sub">${esc(complaint.submittedBy?.name ?? '')}</span>
      </td>
      <td class="nowrap">${esc(complaint.department)}</td>
      <td>
        ${
          complaint.assignedOfficer
            ? `<span class="strong">${esc(complaint.assignedOfficer.name)}</span>
               <span class="cell-sub">${esc(complaint.assignedOfficer.designation)}</span>`
            : '<span class="faint" style="font-style:italic">Not assigned</span>'
        }
      </td>
      <td class="nowrap">${esc(formatDate(complaint.deadline))}</td>
      <td class="tnum"><span class="deadline-note is-overdue" style="display:inline-block;margin:0">
        ${complaint.daysOverdue} day${complaint.daysOverdue === 1 ? '' : 's'}
      </span></td>
      <td>${escalationBadge(complaint.escalationLevel)}</td>
      <td class="nowrap">${esc(complaint.escalationAuthority)}</td>
      <td>${priorityBadge(complaint.priority)}</td>
      <td>${statusBadge(complaint.status)}</td>
      <td>
        <div class="cell-actions">
          <a class="btn-icon" href="${DETAILS}?id=${encodeURIComponent(complaint.id)}"
             aria-label="View ${esc(complaint.id)}" title="View details">${icon('eye', 'icon-md')}</a>
          ${
            complaint.escalationLevel < 3
              ? `<button type="button" class="btn-icon" data-raise="${esc(complaint.id)}"
                   aria-label="Raise ${esc(complaint.id)} a level" title="Raise a level">${icon('trending-up', 'icon-md')}</button>`
              : ''
          }
        </div>
      </td>
    </tr>`
}

function view(escalations) {
  if (!escalations.length) {
    return `
      ${alertBox({
        tone: 'success',
        icon: 'check-circle',
        title: 'Nothing is overdue',
        text: 'Every open complaint is currently within its resolution deadline.',
      })}
      ${ladder()}`
  }

  const byLevel = (level) => escalations.filter((item) => item.escalationLevel === level).length
  const worst = Math.max(...escalations.map((item) => item.daysOverdue))

  return `
    <div class="stack">
      <div class="grid grid-4">
        ${statCard({ label: 'Overdue complaints', value: escalations.length, icon: 'alert-triangle', tone: 'danger' })}
        ${statCard({ label: 'Level 1 — Officer', value: byLevel(1), icon: 'user-cog', tone: 'warning' })}
        ${statCard({ label: 'Level 2 — Dept. Head', value: byLevel(2), icon: 'users', tone: 'warning' })}
        ${statCard({ label: 'Level 3 — Administration', value: byLevel(3), icon: 'shield-alert', tone: 'danger', hint: `Worst case ${worst} days overdue` })}
      </div>

      ${ladder()}

      <section class="card">
        <header class="card__head">
          <div>
            <h2 class="card__title">Overdue complaints</h2>
            <p class="card__subtitle">Sorted by how far past the deadline they are</p>
          </div>
        </header>
        <div class="card__body card__body--flush">
          <div class="table-wrap scroll-slim">
            <table class="table" style="min-width:1100px">
              <thead>
                <tr>
                  <th scope="col">Complaint ID</th>
                  <th scope="col">Title</th>
                  <th scope="col">Department</th>
                  <th scope="col">Officer</th>
                  <th scope="col">Deadline</th>
                  <th scope="col">Days Overdue</th>
                  <th scope="col">Level</th>
                  <th scope="col">Current Authority</th>
                  <th scope="col">Priority</th>
                  <th scope="col">Status</th>
                  <th scope="col" class="right">Action</th>
                </tr>
              </thead>
              <tbody>${escalations.map(row).join('')}</tbody>
            </table>
          </div>
        </div>
      </section>
    </div>`
}

async function load(user) {
  mount('#area', loadingState('Checking deadlines…'))

  try {
    const escalations = await getEscalations()
    qs('#area').innerHTML = escalations.length
      ? view(escalations)
      : `<div class="stack">${view(escalations)}</div>`
  } catch (error) {
    mount('#area', errorState({ message: error.message, retryId: 'retry' }))
    qs('#retry')?.addEventListener('click', () => load(user))
  }
}

ready(() => {
  const user = requireRole(ROLES.ADMIN)
  if (!user) return

  renderShell(user, { title: 'Escalations' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'Escalation management',
      lead: 'Complaints that have crossed their resolution deadline and moved up the ladder.',
      crumbs: [{ label: 'Dashboard', href: '/admin/dashboard.html' }, { label: 'Escalations' }],
    })}
    <div id="area"></div>`

  load(user)

  on('#area', 'click', '[data-raise]', async (event, button) => {
    const id = button.dataset.raise
    const confirmed = await confirmDialog({
      title: `Raise ${id} to the next level?`,
      message: 'The complaint moves to a higher authority and everyone involved is notified.',
      confirmLabel: 'Raise level',
      tone: 'warning',
    })
    if (!confirmed) return

    try {
      await escalateComplaint(id, user.name)
      toast.success(`${id} raised to the next escalation level.`)
      load(user)
    } catch (error) {
      toast.error(error.message)
    }
  })
})
