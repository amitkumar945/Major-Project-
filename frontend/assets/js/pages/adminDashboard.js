/**
 * Administration dashboard - campus-wide figures and charts.
 */

import { esc, icon, mount, qs, ready } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { errorState, progressBar, skeletonCards, statCard } from '../components/ui.js'
import { complaintTable } from '../components/complaintTable.js'
import { activateCharts, barChartH, barChartV, chartCard, donutChart, lineChart } from '../components/charts.js'
import { getAllComplaints } from '../services/complaintService.js'
import { getAnalyticsOverview } from '../services/analyticsService.js'
import { getDepartments } from '../services/departmentService.js'
import { PRIORITY_RAMP, SERIES, STATUS_GROUPS, statusGroupOf } from '../utils/chartTheme.js'
import { ROLES } from '../utils/constants.js'

const DETAILS = '/admin/complaint-details.html'

function departmentPanel(departments) {
  return `
    <section class="card">
      <header class="card__head">
        <div>
          <h2 class="card__title">Department performance</h2>
          <p class="card__subtitle">Resolution rate across the four departments</p>
        </div>
        <a class="btn btn--secondary btn--sm" href="/admin/departments.html">
          Manage${icon('arrow-right', 'icon-sm')}
        </a>
      </header>
      <div class="card__body stack-sm">
        ${departments
          .map(
            (department) => `
          <div>
            ${progressBar({
              value: department.resolutionRate,
              label: department.name,
              valueLabel: `${department.resolutionRate}%`,
              tone:
                department.resolutionRate >= 90
                  ? 'success'
                  : department.resolutionRate >= 70
                    ? 'warning'
                    : 'danger',
              small: true,
            })}
            <p class="muted" style="font-size:var(--fs-xs);margin-top:.25rem">
              ${department.totalComplaints} total · ${department.resolvedComplaints} resolved ·
              ${department.pendingComplaints} pending
            </p>
          </div>`,
          )
          .join('')}
      </div>
    </section>`
}

async function load(user) {
  const root = qs('#root')
  const header = pageHeader({
    title: 'Administration dashboard',
    lead: 'Campus-wide view of every grievance and how quickly it is being resolved.',
    actions: `<a class="btn btn--primary" href="/admin/analytics.html">${icon('bar-chart', 'icon-sm')}Full analytics</a>`,
  })

  root.innerHTML = header + skeletonCards(8)

  try {
    const [overview, complaints, departments] = await Promise.all([
      getAnalyticsOverview(),
      getAllComplaints(),
      getDepartments(),
    ])

    const metrics = overview.metrics

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

    const priorityData = overview.byPriority.map((entry) => ({
      ...entry,
      color: PRIORITY_RAMP[entry.name],
    }))

    const recent = [...complaints]
      .sort((a, b) => new Date(b.submittedAt) - new Date(a.submittedAt))
      .slice(0, 6)

    root.innerHTML = `
      ${header}
      <div class="stack">
        <div class="grid grid-4">
          ${statCard({ label: 'Total Complaints', value: metrics.total, icon: 'clipboard-list', href: '/admin/complaints.html' })}
          ${statCard({ label: "Today's Complaints", value: metrics.today, icon: 'file-plus', tone: 'info' })}
          ${statCard({ label: 'Pending', value: metrics.pending, icon: 'clock', tone: 'warning', href: '/admin/complaints.html?status=Pending' })}
          ${statCard({ label: 'In Progress', value: metrics.inProgress, icon: 'activity', tone: 'info', href: '/admin/complaints.html?status=In+Progress' })}
          ${statCard({ label: 'Resolved', value: metrics.resolved, icon: 'check-circle', tone: 'success', href: '/admin/complaints.html?status=Resolved' })}
          ${statCard({ label: 'Escalated', value: metrics.escalated, icon: 'shield-alert', tone: 'danger', href: '/admin/escalations.html' })}
          ${statCard({ label: 'Avg. Resolution Time', value: `${metrics.avgResolutionDays} days`, icon: 'gauge', tone: 'purple' })}
          ${statCard({ label: 'Satisfaction Rate', value: `${metrics.satisfactionRate}%`, icon: 'star', tone: 'success', hint: `${metrics.avgRating} out of 5 average` })}
        </div>

        <div class="grid grid-2">
          ${chartCard({
            title: 'Complaints by Status',
            subtitle: `${metrics.total} complaints in total`,
            chart: donutChart(statusData),
            legend: statusData.map((entry) => ({ label: entry.name, color: entry.color, value: entry.value })),
            tableHead: ['Status', 'Complaints'],
            tableRows: statusData.map((entry) => [entry.name, entry.value]),
            empty: !metrics.total,
          })}

          ${chartCard({
            title: 'Complaints by Department',
            subtitle: 'Where the workload sits',
            chart: barChartH(overview.byDepartment),
            tableHead: ['Department', 'Complaints'],
            tableRows: overview.byDepartment.map((entry) => [entry.name, entry.value]),
            empty: overview.byDepartment.every((entry) => entry.value === 0),
          })}
        </div>

        <div class="grid grid-2">
          ${chartCard({
            title: 'Monthly Trend',
            subtitle: 'Registered against resolved, last twelve months',
            chart: lineChart(
              overview.monthlyTrend.map((entry) => entry.month),
              [
                { name: 'Registered', color: SERIES.primary, values: overview.monthlyTrend.map((entry) => entry.registered) },
                { name: 'Resolved', color: SERIES.positive, values: overview.monthlyTrend.map((entry) => entry.resolved) },
              ],
            ),
            legend: [
              { label: 'Registered', color: SERIES.primary },
              { label: 'Resolved', color: SERIES.positive },
            ],
            tableHead: ['Month', 'Registered', 'Resolved'],
            tableRows: overview.monthlyTrend.map((entry) => [entry.month, entry.registered, entry.resolved]),
          })}

          ${chartCard({
            title: 'Complaints by Priority',
            subtitle: 'Darker means more urgent',
            chart: barChartV(priorityData),
            tableHead: ['Priority', 'Complaints'],
            tableRows: priorityData.map((entry) => [entry.name, entry.value]),
            empty: priorityData.every((entry) => entry.value === 0),
          })}
        </div>

        ${departmentPanel(departments)}

        <section class="card">
          <header class="card__head">
            <h2 class="card__title">Latest complaints</h2>
            <a class="btn btn--secondary btn--sm" href="/admin/complaints.html">
              View all${icon('arrow-right', 'icon-sm')}
            </a>
          </header>
          <div class="card__body card__body--flush">
            ${complaintTable({
              complaints: recent,
              columns: ['id', 'title', 'user', 'department', 'priority', 'status', 'deadline'],
              detailsHref: DETAILS,
              sortable: false,
              showUserOnCard: true,
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
  const user = requireRole(ROLES.ADMIN)
  if (!user) return
  renderShell(user, { title: 'Admin Dashboard' })
  load(user)
})
