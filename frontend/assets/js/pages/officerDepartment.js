/**
 * Whole-department queue plus the workload of every colleague.
 *
 * This is what makes workload-based assignment visible: an officer can see who
 * is carrying how much before asking for a complaint to be reassigned.
 */

import { esc, icon, mount, qs, ready } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { avatar, errorState, loadingState, progressBar, statCard } from '../components/ui.js'
import { createComplaintList, FILTER_FIELDS } from '../components/complaintListView.js'
import { getStatistics } from '../services/complaintService.js'
import { getOfficers } from '../services/officerService.js'
import { ROLES } from '../utils/constants.js'

const DETAILS = '/officer/complaint-details.html'

function officerRow(officer, busiest, isMe) {
  return `
    <li class="card" style="padding:var(--sp-4);${isMe ? 'border-color:var(--brand-300)' : ''}">
      <div class="row" style="gap:.875rem">
        ${avatar(officer.name, officer.avatarColor, 'sm')}
        <div class="grow" style="min-width:0">
          <p class="strong truncate">
            ${esc(officer.name)}
            ${isMe ? '<span class="badge badge--review" style="margin-left:.375rem">You</span>' : ''}
          </p>
          <p class="muted truncate" style="font-size:var(--fs-xs)">${esc(officer.designation)}</p>
        </div>
        <span class="workload__count" style="font-size:var(--fs-lg)">${officer.workload.active}</span>
      </div>
      <div style="margin-top:var(--sp-3)">
        ${progressBar({
          value: officer.workload.active,
          max: busiest || 1,
          tone: officer.workload.active > busiest * 0.7 ? 'danger' : officer.workload.active > busiest * 0.4 ? 'warning' : 'success',
          small: true,
        })}
      </div>
      <p class="muted" style="font-size:var(--fs-xs);margin-top:.5rem">
        ${officer.workload.resolvedTotal} resolved · ${officer.workload.avgResolutionDays} day average
      </p>
    </li>`
}

async function loadTeam(user) {
  try {
    const [officers, summary] = await Promise.all([
      getOfficers({ department: user.department, activeOnly: true }),
      getStatistics({ department: user.department }),
    ])

    const busiest = Math.max(...officers.map((officer) => officer.workload.active), 1)

    qs('#team').innerHTML = `
      <div class="grid grid-4">
        ${statCard({ label: 'Department total', value: summary.total, icon: 'clipboard-list' })}
        ${statCard({ label: 'Open', value: summary.total - summary.resolved, icon: 'activity', tone: 'warning' })}
        ${statCard({ label: 'Resolved', value: summary.resolved, icon: 'check-circle', tone: 'success' })}
        ${statCard({ label: 'Overdue', value: summary.overdue, icon: 'alert-triangle', tone: 'danger' })}
      </div>

      <section class="card" style="margin-top:var(--sp-5)">
        <header class="card__head">
          <div>
            <h2 class="card__title">Team workload</h2>
            <p class="card__subtitle">Active complaints per officer — the lightest gets the next assignment</p>
          </div>
        </header>
        <div class="card__body">
          <ul class="grid grid-3">
            ${officers.map((officer) => officerRow(officer, busiest, officer.id === user.id)).join('')}
          </ul>
        </div>
      </section>`
  } catch (error) {
    mount('#team', errorState({ message: error.message }))
  }
}

ready(() => {
  const user = requireRole(ROLES.OFFICER)
  if (!user) return

  renderShell(user, { title: 'Department Queue' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: user.department,
      lead: 'Every complaint in your department, and how the work is shared.',
      crumbs: [{ label: 'Dashboard', href: '/officer/dashboard.html' }, { label: 'Department Queue' }],
      actions: `<a class="btn btn--secondary" href="/officer/complaints.html">${icon('clipboard-list', 'icon-sm')}My queue</a>`,
    })}
    <div class="stack">
      <div id="team">${loadingState('Loading department summary…')}</div>
      <section class="card" id="list"></section>
    </div>`

  loadTeam(user)

  createComplaintList({
    container: '#list',
    scope: { department: user.department },
    columns: ['id', 'title', 'user', 'officer', 'priority', 'status', 'deadline'],
    fields: [FILTER_FIELDS.status, FILTER_FIELDS.priority, FILTER_FIELDS.category],
    detailsHref: DETAILS,
    showUserOnCard: true,
    searchPlaceholder: 'Search the department queue…',
    actions: (complaint) =>
      `<a class="btn-icon" href="${DETAILS}?id=${encodeURIComponent(complaint.id)}"
          aria-label="Open ${complaint.id}" title="Open complaint">${icon('eye', 'icon-md')}</a>`,
    emptyState: {
      title: 'No complaints in this department',
      message: 'Nothing matches the current filters.',
    },
  })
})
