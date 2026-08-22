/**
 * The officer's own work queue.
 */

import { icon, qs, ready } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { createComplaintList, FILTER_FIELDS } from '../components/complaintListView.js'
import { ROLES } from '../utils/constants.js'

const DETAILS = '/officer/complaint-details.html'

ready(() => {
  const user = requireRole(ROLES.OFFICER)
  if (!user) return

  renderShell(user, { title: 'Assigned Complaints' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'Assigned complaints',
      lead: 'Every complaint that is currently your responsibility.',
      crumbs: [{ label: 'Dashboard', href: '/officer/dashboard.html' }, { label: 'Assigned Complaints' }],
      actions: `<a class="btn btn--secondary" href="/officer/department.html">${icon('layers', 'icon-sm')}Department queue</a>`,
    })}
    <section class="card" id="list"></section>`

  createComplaintList({
    container: '#list',
    scope: { officerId: user.id },
    columns: ['id', 'title', 'user', 'category', 'priority', 'status', 'deadline'],
    fields: [FILTER_FIELDS.status, FILTER_FIELDS.priority, FILTER_FIELDS.category],
    detailsHref: DETAILS,
    showUserOnCard: true,
    searchPlaceholder: 'Search by ID, title or complainant…',
    actions: (complaint) =>
      `<a class="btn btn--primary btn--sm" href="${DETAILS}?id=${encodeURIComponent(complaint.id)}">
         ${icon('wrench', 'icon-sm')}Manage
       </a>`,
    emptyState: {
      title: 'Nothing in your queue',
      message: 'No complaints match these filters. Try clearing them, or check the department queue.',
      action: `<a class="btn btn--secondary" href="/officer/department.html">${icon('layers', 'icon-sm')}Department queue</a>`,
    },
  })
})
