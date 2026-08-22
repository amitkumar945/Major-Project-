/**
 * Analytics - eight charts across departments, officers, priorities and time.
 */

import { esc, icon, mount, qs, ready } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { errorState, loadingState, statCard, starRating } from '../components/ui.js'
import {
  activateCharts,
  barChartH,
  barChartV,
  chartCard,
  donutChart,
  groupedBars,
  lineChart,
} from '../components/charts.js'
import { getAnalyticsOverview, getFeedbackEntries } from '../services/analyticsService.js'
import { getAllComplaints } from '../services/complaintService.js'
import {
  PRIORITY_RAMP,
  RATING_RAMP,
  SERIES,
  STATUS_GROUPS,
  statusGroupOf,
} from '../utils/chartTheme.js'
import { ROLES } from '../utils/constants.js'
import { formatDate } from '../utils/helpers.js'

function feedbackPanel(entries) {
  const recent = entries.slice(0, 5)

  return `
    <section class="card">
      <header class="card__head">
        <div>
          <h2 class="card__title">Recent feedback</h2>
          <p class="card__subtitle">What complainants said about the resolution</p>
        </div>
      </header>
      <div class="card__body stack-sm">
        ${
          recent.length
            ? recent
                .map(
                  (entry) => `
            <article class="card" style="padding:var(--sp-4);box-shadow:none">
              <div class="between" style="align-items:flex-start">
                <div class="grow" style="min-width:0">
                  <p class="strong truncate">${esc(entry.complaintTitle)}</p>
                  <p class="muted" style="font-size:var(--fs-xs)">
                    ${esc(entry.department)} · ${esc(entry.officer)} · ${esc(formatDate(entry.at))}
                  </p>
                </div>
                <span class="badge ${entry.satisfied ? 'badge--resolved' : 'badge--pending'}">
                  ${entry.satisfied ? 'Satisfied' : 'Not satisfied'}
                </span>
              </div>
              <div style="margin-top:var(--sp-2)">${starRating(entry.rating, { size: 'icon-sm' })}</div>
              <p style="margin-top:var(--sp-2)">${esc(entry.comment)}</p>
            </article>`,
                )
                .join('')
            : '<p class="muted">No feedback has been submitted yet.</p>'
        }
      </div>
    </section>`
}

async function load(user) {
  mount('#area', loadingState('Building the analytics…'))

  try {
    const [overview, complaints, feedback] = await Promise.all([
      getAnalyticsOverview(),
      getAllComplaints(),
      getFeedbackEntries(),
    ])

    const metrics = overview.metrics

    /* ---------------------------------------------------------- charts */

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

    const satisfactionData = overview.satisfaction.map((entry, index) => ({
      name: entry.rating,
      value: entry.count,
      // Ordinal ramp: 1 star lightest, 5 stars darkest.
      color: RATING_RAMP[overview.satisfaction.length - 1 - index],
    }))

    const officers = overview.officerPerformance.slice(0, 6)

    qs('#area').innerHTML = `
      <div class="stack">
        <div class="grid grid-4">
          ${statCard({ label: 'Total complaints', value: metrics.total, icon: 'clipboard-list' })}
          ${statCard({ label: 'Resolution rate', value: `${metrics.resolutionRate}%`, icon: 'check-circle', tone: 'success' })}
          ${statCard({ label: 'Avg. resolution time', value: `${metrics.avgResolutionDays} days`, icon: 'gauge', tone: 'purple' })}
          ${statCard({ label: 'Satisfaction', value: `${overview.averageRating} / 5`, icon: 'star', tone: 'warning', hint: `${overview.feedbackCount} ratings received` })}
        </div>

        <div class="grid grid-2">
          ${chartCard({
            title: '1. Complaints by Department',
            subtitle: 'Where the workload sits',
            chart: barChartH(overview.byDepartment),
            tableHead: ['Department', 'Complaints'],
            tableRows: overview.byDepartment.map((entry) => [entry.name, entry.value]),
          })}

          ${chartCard({
            title: '2. Complaints by Status',
            subtitle: `${metrics.total} complaints in total`,
            chart: donutChart(statusData),
            legend: statusData.map((entry) => ({ label: entry.name, color: entry.color, value: entry.value })),
            tableHead: ['Status', 'Complaints'],
            tableRows: statusData.map((entry) => [entry.name, entry.value]),
            empty: !metrics.total,
          })}

          ${chartCard({
            title: '3. Complaints by Priority',
            subtitle: 'Darker means more urgent',
            chart: barChartV(priorityData),
            tableHead: ['Priority', 'Complaints'],
            tableRows: priorityData.map((entry) => [entry.name, entry.value]),
          })}

          ${chartCard({
            title: '4. Monthly Complaint Trend',
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
            title: '5. Resolution Time by Department',
            subtitle: 'Average days taken against the target',
            chart: groupedBars(
              overview.resolutionTime.map((entry) => entry.name),
              [
                { name: 'Actual', color: SERIES.accent, values: overview.resolutionTime.map((entry) => entry.avgDays) },
                { name: 'Target', color: SERIES.neutral, values: overview.resolutionTime.map((entry) => entry.targetDays) },
              ],
            ),
            legend: [
              { label: 'Actual days', color: SERIES.accent },
              { label: 'Target days', color: SERIES.neutral },
            ],
            tableHead: ['Department', 'Actual days', 'Target days'],
            tableRows: overview.resolutionTime.map((entry) => [entry.name, entry.avgDays, entry.targetDays]),
          })}

          ${chartCard({
            title: '6. Officer Performance',
            subtitle: 'Resolved against currently active, top six officers',
            chart: groupedBars(
              officers.map((officer) => officer.name.split(' ').slice(-1)[0]),
              [
                { name: 'Resolved', color: SERIES.positive, values: officers.map((officer) => officer.resolved) },
                { name: 'Active', color: SERIES.accent, values: officers.map((officer) => officer.active) },
              ],
            ),
            legend: [
              { label: 'Resolved', color: SERIES.positive },
              { label: 'Active', color: SERIES.accent },
            ],
            tableHead: ['Officer', 'Department', 'Resolved', 'Active', 'Avg. days', 'Rating'],
            tableRows: overview.officerPerformance.map((officer) => [
              officer.name,
              officer.department,
              officer.resolved,
              officer.active,
              officer.avgDays,
              officer.rating,
            ]),
          })}

          ${chartCard({
            title: '7. Department Performance',
            subtitle: 'Resolution rate per department',
            chart: barChartH(
              overview.departmentPerformance.map((entry) => ({ name: entry.name, value: entry.resolutionRate })),
              { unit: '%' },
            ),
            tableHead: ['Department', 'Total', 'Resolved', 'Pending', 'Rate %', 'Satisfaction'],
            tableRows: overview.departmentPerformance.map((entry) => [
              entry.name,
              entry.total,
              entry.resolved,
              entry.pending,
              entry.resolutionRate,
              entry.satisfaction,
            ]),
          })}

          ${chartCard({
            title: '8. Satisfaction Rating',
            subtitle: 'How complainants rated the resolutions',
            chart: barChartV(satisfactionData),
            tableHead: ['Rating', 'Responses'],
            tableRows: satisfactionData.map((entry) => [entry.name, entry.value]),
          })}
        </div>

        ${feedbackPanel(feedback)}
      </div>`

    activateCharts(qs('#area'))
  } catch (error) {
    mount('#area', errorState({ message: error.message, retryId: 'retry' }))
    qs('#retry')?.addEventListener('click', () => load(user))
  }
}

ready(() => {
  const user = requireRole(ROLES.ADMIN)
  if (!user) return

  renderShell(user, { title: 'Analytics' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'Analytics',
      lead: 'Eight views of how the grievance system is performing.',
      crumbs: [{ label: 'Dashboard', href: '/admin/dashboard.html' }, { label: 'Analytics' }],
      actions: `<button type="button" class="btn btn--secondary" onclick="window.print()">${icon('printer', 'icon-sm')}Print</button>`,
    })}
    <div id="area"></div>`

  load(user)
})
