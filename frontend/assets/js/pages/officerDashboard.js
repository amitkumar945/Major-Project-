/**
 * Department officer dashboard.
 * Workload counters, priority mix, resolution performance and the newest
 * complaints assigned to this officer.
 */

import { icon, mount, qs, ready } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { errorState, progressBar, skeletonCards, statCard } from '../components/ui.js'
import { complaintTable } from '../components/complaintTable.js'
import { activateCharts, barChartV, chartCard, donutChart } from '../components/charts.js'
import { getAllComplaints, getStatistics } from '../services/complaintService.js'
import { getOfficerById } from '../services/officerService.js'
import { PRIORITY_RAMP, STATUS_GROUPS, statusGroupOf } from '../utils/chartTheme.js'
import { PRIORITY_LIST, ROLES } from '../utils/constants.js'

const DETAILS = '/officer/complaint-details.html'

function performanceCard(officer, summary) {
  const resolutionRate = summary.total ? Math.round((summary.resolved / summary.total) * 100) : 0

  return `
    <section class="card">
      <header class="card__head">
        <div>
          <h2 class="card__title">Your performance</h2>
          <p class="card__subtitle">Across all complaints assigned to you</p>
        </div>
      </header>
      <div class="card__body stack-sm">
        ${progressBar({
          value: resolutionRate,
          tone: resolutionRate >= 80 ? 'success' : resolutionRate >= 50 ? 'warning' : 'danger',
          label: 'Resolution rate',
          valueLabel: `${resolutionRate}%`,
        })}

        <div class="grid grid-3" style="margin-top:var(--sp-4)">
          <div>
            <p class="muted" style="font-size:var(--fs-xs)">Total resolved</p>
            <p class="strong tnum" style="font-size:var(--fs-lg)">${officer.workload.resolvedTotal}</p>
          </div>
          <div>
            <p class="muted" style="font-size:var(--fs-xs)">Average days</p>
            <p class="strong tnum" style="font-size:var(--fs-lg)">${officer.workload.avgResolutionDays}</p>
          </div>
          <div>
            <p class="muted" style="font-size:var(--fs-xs)">Rating</p>
            <p class="strong tnum" style="font-size:var(--fs-lg)">${officer.workload.rating} / 5</p>
          </div>
        </div>
      </div>
    </section>`
}

async function load(user) {
  const root = qs('#root')
  const header = pageHeader({
    title: `Good to see you, ${user.name.split(' ').slice(-1)[0]}`,
    lead: `${user.designation} · ${user.department}`,
  })

  root.innerHTML = header + skeletonCards(6)

  try {
    const [summary, complaints, officer] = await Promise.all([
      getStatistics({ officerId: user.id }),
      getAllComplaints({ officerId: user.id }),
      getOfficerById(user.id),
    ])

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

    const priorityData = PRIORITY_LIST.map((priority) => ({
      name: priority,
      value: complaints.filter((complaint) => complaint.priority === priority).length,
      color: PRIORITY_RAMP[priority],
    }))

    const statusTotal = statusData.reduce((sum, entry) => sum + entry.value, 0)

    root.innerHTML = `
      ${header}
      <div class="stack">
        <div class="grid grid-3">
          ${statCard({ label: 'Assigned to me', value: summary.total, icon: 'clipboard-list', href: '/officer/complaints.html' })}
          ${statCard({ label: 'Pending', value: summary.pending, icon: 'clock', tone: 'warning', href: '/officer/complaints.html?status=Pending' })}
          ${statCard({ label: 'In Progress', value: summary.inProgress, icon: 'activity', tone: 'info', href: '/officer/complaints.html?status=In+Progress' })}
          ${statCard({ label: 'Resolved', value: summary.resolved, icon: 'check-circle', tone: 'success', href: '/officer/complaints.html?status=Resolved' })}
          ${statCard({ label: 'Overdue', value: summary.overdue, icon: 'alert-triangle', tone: 'danger', hint: 'Past the resolution deadline' })}
          ${statCard({ label: 'Escalated', value: summary.escalated, icon: 'shield-alert', tone: 'danger', href: '/officer/complaints.html?status=Escalated' })}
        </div>

        <div class="grid grid-3">
          ${chartCard({
            title: 'My complaints by status',
            subtitle: `${statusTotal} complaint${statusTotal === 1 ? '' : 's'} assigned`,
            chart: donutChart(statusData),
            legend: statusData.map((entry) => ({ label: entry.name, color: entry.color, value: entry.value })),
            tableHead: ['Status', 'Complaints'],
            tableRows: statusData.map((entry) => [entry.name, entry.value]),
            empty: statusTotal === 0,
          })}

          ${chartCard({
            title: 'Priority mix',
            subtitle: 'Darker means more urgent',
            chart: barChartV(priorityData),
            tableHead: ['Priority', 'Complaints'],
            tableRows: priorityData.map((entry) => [entry.name, entry.value]),
            empty: priorityData.every((entry) => entry.value === 0),
          })}

          ${performanceCard(officer, summary)}
        </div>

        <section class="card">
          <header class="card__head">
            <h2 class="card__title">Recently assigned</h2>
            <a class="btn btn--secondary btn--sm" href="/officer/complaints.html">
              View queue${icon('arrow-right', 'icon-sm')}
            </a>
          </header>
          <div class="card__body card__body--flush">
            ${complaintTable({
              complaints: complaints.slice(0, 6),
              columns: ['id', 'title', 'user', 'priority', 'status', 'deadline'],
              detailsHref: DETAILS,
              sortable: false,
              showUserOnCard: true,
              emptyTitle: 'No complaints assigned to you',
              emptyMessage: 'New complaints for your department will appear here.',
            })}
          </div>
        </section>
      </div>`

    activateCharts(root)
  } catch (error) {
    mount('#root', errorState({ message: error.message, retryId: 'retry' }))
    qs('#retry')?.addEventListener('click', () => load(user))
  }
}

ready(() => {
  const user = requireRole(ROLES.OFFICER)
  if (!user) return
  renderShell(user, { title: 'Officer Dashboard' })
  load(user)
})
