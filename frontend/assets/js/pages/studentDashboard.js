/**
 * Student / staff dashboard.
 * Summary counters, quick actions, three charts and the most recent complaints.
 */

import { esc, icon, mount, qs, ready } from '../components/dom.js'
import { renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { complaintProgress, errorState, priorityBadge, skeletonCards, statCard, statusBadge } from '../components/ui.js'
import { complaintTable } from '../components/complaintTable.js'
import { activateCharts, barChartH, barChartV, chartCard, donutChart } from '../components/charts.js'
import { getStatistics, getAllComplaints } from '../services/complaintService.js'
import { getDashboardCharts, getMyFeedback } from '../services/analyticsService.js'
import { PRIORITY_RAMP, STATUS_GROUPS, statusGroupOf } from '../utils/chartTheme.js'
import { ASSETS, ROLES } from '../utils/constants.js'

const DETAILS = '/student/complaint-details.html'

/**
 * Welcome area using only the authenticated profile fields.
 */
function welcome(user) {
  const firstName = user.name?.trim().split(/\s+/)[0] || 'there'
  const role = user.userType === 'Staff' ? 'Staff' : 'Student'
  const details = [
    { label: role === 'Staff' ? 'Staff ID' : 'Student ID', value: user.userId, icon: 'id-card' },
    { label: 'Course', value: user.course, icon: 'graduation-cap' },
    { label: 'Department', value: user.department, icon: 'building' },
  ].filter((item) => typeof item.value === 'string' && item.value.trim() && item.value !== '—')

  return `
    <section class="student-hero" aria-labelledby="dashboard-welcome-title">
      <div class="student-hero__copy">
        <p class="student-hero__eyebrow">DSVV Grievance Management System</p>
        <h1 id="dashboard-welcome-title">Welcome back, ${esc(firstName)}</h1>
        <p class="student-hero__lead">Your campus concerns and updates, together in one place.</p>
        <div class="student-hero__details">
          ${details.map((item) => `
            <span class="student-hero__detail">
              ${icon(item.icon, 'icon-sm')}
              <span><span class="student-hero__detail-label">${esc(item.label)}</span><strong>${esc(item.value)}</strong></span>
            </span>`).join('')}
        </div>
        <a class="btn btn--primary student-hero__cta" href="/student/new-complaint.html">
          ${icon('plus', 'icon-md')}Submit a grievance
        </a>
      </div>
      <div class="student-hero__art">
        <img src="${esc(ASSETS.campus)}" alt="Illustrated university campus">
        <span class="student-hero__art-label">Campus services</span>
      </div>
    </section>`
}

function quickActions() {
  const actions = [
    { label: 'My Complaints', glyph: 'clipboard-list', href: '/student/complaints.html' },
    { label: 'Track Complaint', glyph: 'file-search', href: '/track.html' },
    { label: 'Notifications', glyph: 'bell', href: '/student/notifications.html' },
    { label: 'Feedback', glyph: 'star', href: '/student/feedback.html' },
    { label: 'Profile', glyph: 'user', href: '/student/profile.html' },
    { label: 'Help & Support', glyph: 'life-buoy', href: '/student/help.html' },
  ]

  return `
    <nav class="quick-grid dashboard-links" aria-label="Quick links">
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
        title: 'Complaint Status Overview',
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

  root.innerHTML = welcome(user) + skeletonCards(6)

  try {
    const [summary, chartData, recent, feedback] = await Promise.all([
      getStatistics({ userId: user.id }),
      getDashboardCharts({ userId: user.id }),
      getAllComplaints({ userId: user.id }),
      getMyFeedback().catch(() => null),
    ])
    const urgentCount = recent.filter((complaint) => complaint.priority?.toLowerCase() === 'urgent').length
    const feedbackPending = feedback?.pendingCount ?? recent.filter((complaint) =>
      ['Resolved', 'Closed'].includes(complaint.status) && !complaint.feedback,
    ).length
    const latest = recent[0]

    root.innerHTML = `
      ${welcome(user)}
      <section class="dashboard-stats" aria-label="Complaint overview">
        ${statCard({ label: 'Total Complaints', value: summary.total, icon: 'clipboard-list', href: '/student/complaints.html' })}
        ${statCard({ label: 'Pending', value: summary.pending, icon: 'clock', tone: 'warning', href: '/student/complaints.html?status=Pending' })}
        ${statCard({ label: 'In Progress', value: summary.inProgress, icon: 'activity', tone: 'info', href: '/student/complaints.html?status=In+Progress' })}
        ${statCard({ label: 'Resolved', value: summary.resolved, icon: 'check-circle', tone: 'success', href: '/student/complaints.html?status=Resolved' })}
        ${statCard({ label: 'Urgent', value: urgentCount, icon: 'alert-triangle', tone: 'danger', href: '/student/complaints.html?priority=Urgent' })}
        ${statCard({ label: 'Feedback Pending', value: feedbackPending, icon: 'star', tone: 'purple', href: '/student/feedback.html' })}
        ${statCard({ label: 'Reopened', value: summary.reopened, icon: 'rotate-ccw', tone: 'purple', href: '/student/complaints.html?status=Reopened' })}
      </section>

      <section class="dashboard-section">
        <div class="dashboard-section__head">
          <div><p class="dashboard-kicker">At a glance</p><h2>Complaint overview</h2></div>
          <a class="dashboard-text-link" href="/student/complaints.html">View all complaints${icon('arrow-right', 'icon-sm')}</a>
        </div>
        ${charts(recent, chartData.byDepartment, chartData.byPriority)}
      </section>

      <div class="dashboard-focus">
        <section class="card dashboard-panel">
          <header class="card__head">
            <div><h2 class="card__title">Track Your Complaint</h2><p class="card__subtitle">Latest update from your complaint queue</p></div>
            ${latest ? statusBadge(latest.status) : ''}
          </header>
          <div class="card__body">
            ${latest ? `
              <div class="dashboard-track__summary">
                <div><a class="dashboard-track__title" href="${DETAILS}?id=${encodeURIComponent(latest.id)}">${esc(latest.title)}</a>
                  <p class="muted">${esc(latest.id)}${latest.department ? ` · ${esc(latest.department)}` : ''}</p></div>
                ${priorityBadge(latest.priority)}
              </div>
              ${complaintProgress(latest)}
              <a class="dashboard-text-link" href="${DETAILS}?id=${encodeURIComponent(latest.id)}">Open complaint details${icon('arrow-right', 'icon-sm')}</a>
            ` : `<div class="dashboard-empty"><p>No complaints to track yet.</p><a href="/student/new-complaint.html">Submit your first complaint${icon('arrow-right', 'icon-sm')}</a></div>`}
          </div>
        </section>

        <aside class="card dashboard-feedback">
          <span class="dashboard-feedback__icon">${icon('message-square', 'icon-lg')}</span>
          <p class="dashboard-kicker">Your experience matters</p>
          <h2>Feedback & suggestions</h2>
          <p>${feedbackPending ? `${feedbackPending} resolved complaint${feedbackPending === 1 ? '' : 's'} awaiting your feedback.` : 'Share feedback on resolved complaints or send a suggestion to the team.'}</p>
          <a class="btn btn--outline" href="/student/feedback.html">Open Feedback${icon('arrow-right', 'icon-sm')}</a>
        </aside>
      </div>

      <section class="card dashboard-recent">
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
      <section class="dashboard-quicklinks"><div class="dashboard-section__head"><div><p class="dashboard-kicker">Useful destinations</p><h2>Quick Links</h2></div></div>${quickActions()}</section>`

    activateCharts(root)
  } catch (error) {
    mount('#root', errorState({ message: error.message, retryId: 'retry' }))
    qs('#retry')?.addEventListener('click', () => load(user))
  }
}

ready(() => {
  const user = requireRole(ROLES.STUDENT)
  if (!user) return
  renderShell(user, { title: 'Dashboard' })
  load(user)
})
