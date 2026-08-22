/**
 * "My Complaints" - every complaint this user has registered.
 */

import { icon, qs, ready } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { createComplaintList, FILTER_FIELDS } from '../components/complaintListView.js'
import { ROLES } from '../utils/constants.js'

const DETAILS = '/student/complaint-details.html'

ready(() => {
  const user = requireRole(ROLES.STUDENT)
  if (!user) return

  renderShell(user, { title: 'My Complaints' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'My Complaints',
      lead: 'Every complaint you have registered, with its current status.',
      crumbs: [{ label: 'Dashboard', href: '/student/dashboard.html' }, { label: 'My Complaints' }],
      actions: `<a class="btn btn--primary" href="/student/new-complaint.html">${icon('plus', 'icon-sm')}New complaint</a>`,
    })}
    <section class="card" id="list"></section>`

  createComplaintList({
    container: '#list',
    scope: { userId: user.id },
    columns: ['id', 'title', 'department', 'priority', 'status', 'submittedAt', 'updatedAt'],
    fields: [FILTER_FIELDS.department, FILTER_FIELDS.status, FILTER_FIELDS.priority, FILTER_FIELDS.category],
    detailsHref: DETAILS,
    actions: (complaint) =>
      `<a class="btn-icon" href="${DETAILS}?id=${encodeURIComponent(complaint.id)}"
          aria-label="View ${complaint.id}" title="View details">${icon('eye', 'icon-md')}</a>`,
    emptyState: {
      title: 'No complaints found',
      message: 'Try changing the filters, or register a new complaint.',
      action: `<a class="btn btn--primary" href="/student/new-complaint.html">${icon('plus', 'icon-sm')}Submit a complaint</a>`,
    },
  })
})
