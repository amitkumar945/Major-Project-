/**
 * Student / staff dashboard.
 * Summary counters, quick actions, three charts and the most recent complaints.
 */

import { esc, icon, mount, qs, ready } from '../components/dom.js'
import { renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { errorState, skeletonCards, statCard } from '../components/ui.js'
import { complaintTable } from '../components/complaintTable.js'
import { activateCharts, barChartH, barChartV, chartCard, donutChart } from '../components/charts.js'
import { getStatistics, getAllComplaints } from '../services/complaintService.js'
import { getDashboardCharts } from '../services/analyticsService.js'
import { PRIORITY_RAMP, STATUS_GROUPS, statusGroupOf } from '../utils/chartTheme.js'
import { ROLES } from '../utils/constants.js'

const DETAILS = '/student/complaint-details.html'

/**
 * The greeting and the one primary action, then four plain quick links.
 * Everything here is navigation only - no data is fetched or changed.
 */
function welcome(user) {
  return `
    <section class="welcome">
      <p class="welcome__hello">Hello, ${esc(user.name.split(' ')[0])}!</p>
      <h1 class="welcome__ask">How can we help you today?</h1>
      <a class="btn btn--lg welcome__cta" href="/student/new-complaint.html">
        ${icon('plus', 'icon-md')}Submit a Complaint
      </a>
    </section>`
}

function quickActions() {
  const actions = [
    { label: 'My Complaints',  glyph: 'clipboard-list', href: '/student/complaints.html' },
    { label: 'Track Complaint', glyph: 'file-search',   href: '/track.html' },
    { label: 'Notifications',  glyph: 'bell',           href: '/student/notifications.html' },
    { label: 'Help & Support', glyph: 'life-buoy',      href: '/student/help.html' },
  ]

  return `
    <nav class="quick-grid" aria-label="Quick actions">
      ${actions
        .map(
          (action) => `
        <a class="card card--hover quick-tile" href="${action.href}">
          <span class="quick-tile__icon">${icon(action.glyph, 'icon-lg')}</span>
          <span class="quick-tile__label">${action.label}</span>
        </a>`,
        )
        .join('')}
    </nav>`
}

/** Build the three dashboard charts from this user's complaints. */
function charts(complaints, byDepartment, byPriority) {
  const statusCounts = complaints.reduce((acc, complaint) => {
    const group = statusGroupOf(complaint.status)
    acc[group] = (acc[group] || 0) + 1
    return acc
  }, {})

  const statusData = STATUS_GROUPS.map((group) => ({
    name: group.key,
    value: statusCounts[group.key] || 0,
    color: group.color,
  })).filter((entry) => entry.value > 0)

  const statusTotal = statusData.reduce((sum, entry) => sum + entry.value, 0)

  const priorityData = byPriority.map((entry) => ({
    ...entry,
    color: PRIORITY_RAMP[entry.name],
  }))

  return `
    <div class="grid grid-3">
      ${chartCard({
        title: 'Complaints by Status',
        subtitle: `${statusTotal} complaint${statusTotal === 1 ? '' : 's'} in total`,
        chart: donutChart(statusData),
        legend: statusData.map((entry) => ({ label: entry.name, color: entry.color, value: entry.value })),
        tableHead: ['Status', 'Complaints', 'Share'],
        tableRows: statusData.map((entry) => [
          entry.name,
          entry.value,
          `${Math.round((entry.value / statusTotal) * 100)}%`,
        ]),
        empty: statusTotal === 0,
        emptyMessage: 'Register a complaint to see it here.',
      })}

      ${chartCard({
        title: 'Complaints by Department',
        subtitle: 'Where your complaints were routed',
        chart: barChartH(byDepartment),
        tableHead: ['Department', 'Complaints'],
        tableRows: byDepartment.map((entry) => [entry.name, entry.value]),
        empty: byDepartment.every((entry) => entry.value === 0),
      })}

      ${chartCard({
        title: 'Complaints by Priority',
        subtitle: 'Darker means more urgent',
        chart: barChartV(priorityData),
        tableHead: ['Priority', 'Complaints'],
        tableRows: priorityData.map((entry) => [entry.name, entry.value]),
        empty: priorityData.every((entry) => entry.value === 0),
      })}
    </div>`
}

async function load(user) {
  const root = qs('#root')

  root.innerHTML = welcome(user) + quickActions() + skeletonCards(3)

  try {
    const [summary, chartData, recent] = await Promise.all([
      getStatistics({ userId: user.id }),
      getDashboardCharts({ userId: user.id }),
      getAllComplaints({ userId: user.id }),
    ])

    root.innerHTML = `
      ${welcome(user)}
      ${quickActions()}

      <div class="stack">
        <section>
          <h2 class="section-label">Your complaints</h2>
          <div class="grid grid-3">
            ${statCard({ label: 'Pending', value: summary.pending, icon: 'clock', tone: 'warning', href: '/student/complaints.html?status=Pending' })}
            ${statCard({ label: 'In Progress', value: summary.inProgress, icon: 'activity', tone: 'info', href: '/student/complaints.html?status=In+Progress' })}
            ${statCard({ label: 'Resolved', value: summary.resolved, icon: 'check-circle', tone: 'success', href: '/student/complaints.html?status=Resolved' })}
          </div>
        </section>

        <section class="card">
          <header class="card__head">
            <h2 class="card__title">Recent complaints</h2>
            <a class="btn btn--secondary btn--sm" href="/student/complaints.html">
              View all${icon('arrow-right', 'icon-sm')}
            </a>
          </header>
          <div class="card__body card__body--flush">
            ${complaintTable({
              complaints: recent.slice(0, 5),
              columns: ['id', 'title', 'department', 'priority', 'status', 'submittedAt'],
              detailsHref: DETAILS,
              sortable: false,
              emptyTitle: 'You have not registered any complaint yet',
              emptyMessage: 'When you report a problem on campus it will appear here.',
              emptyAction: `<a class="btn btn--primary" href="/student/new-complaint.html">${icon('plus', 'icon-sm')}Submit your first complaint</a>`,
            })}
          </div>
        </section>

        <!-- Total, Reopened and the three charts keep every number they had.
             They are folded away so the home screen stays calm; one tap opens
             them. Nothing was removed. -->
        <details class="disclosure">
          <summary class="disclosure__summary">
            <span class="disclosure__icon">${icon('bar-chart', 'icon-md')}</span>
            <span class="grow">
              <span class="disclosure__title">Complaint statistics</span>
              <span class="disclosure__hint">Totals and charts by status, department and priority</span>
            </span>
            ${icon('chevron-down', 'icon-md')}
          </summary>
          <div class="disclosure__body stack">
            <div class="grid grid-2">
              ${statCard({ label: 'Total Complaints', value: summary.total, icon: 'clipboard-list', href: '/student/complaints.html' })}
              ${statCard({ label: 'Reopened', value: summary.reopened, icon: 'rotate-ccw', tone: 'purple', href: '/student/complaints.html?status=Reopened' })}
            </div>
            ${charts(recent, chartData.byDepartment, chartData.byPriority)}
          </div>
        </details>
      </div>`

    activateCharts(root)
  } catch (error) {
    mount('#root', errorState({ message: error.message, retryId: 'retry' }))
    qs('#retry')?.addEventListener('click', () => load(user))
  }
}

ready(() => {
  const user = requireRole(ROLES.STUDENT)
  if (!user) return
  renderShell(user, { title: 'Home' })
  load(user)
})
