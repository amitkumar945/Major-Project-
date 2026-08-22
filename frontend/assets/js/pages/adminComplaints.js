/**
 * Master complaint table with inline administrative actions.
 */

import { icon, on, qs, ready } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { confirmDialog } from '../components/modal.js'
import { toast } from '../components/toast.js'
import { createComplaintList, FILTER_FIELDS } from '../components/complaintListView.js'
import { closeComplaint, escalateComplaint, getAllComplaints } from '../services/complaintService.js'
import { ACTIVE_STATUSES, ROLES, STATUS } from '../utils/constants.js'

const DETAILS = '/admin/complaint-details.html'

ready(() => {
  const user = requireRole(ROLES.ADMIN)
  if (!user) return

  renderShell(user, { title: 'All Complaints' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'All complaints',
      lead: 'Every grievance registered on the portal, with the actions you can take on each.',
      crumbs: [{ label: 'Dashboard', href: '/admin/dashboard.html' }, { label: 'Complaints' }],
      actions: `
        <button type="button" class="btn btn--secondary" id="toggle-map">
          ${icon('map-pin', 'icon-sm')}<span data-label>Map view</span>
        </button>
        <a class="btn btn--secondary" href="/admin/escalations.html">${icon('shield-alert', 'icon-sm')}Escalations</a>`,
    })}
    <section class="card" id="map-panel" hidden>
      <header class="card__head">
        <h2 class="card__title">Complaint map</h2>
        <p class="card__subtitle" id="map-count"></p>
      </header>
      <div class="card__body">
        <div class="map map--full" id="complaint-map"></div>
      </div>
    </section>
    <section class="card" id="list"></section>`

  const list = createComplaintList({
    container: '#list',
    columns: ['id', 'title', 'user', 'department', 'officer', 'priority', 'status', 'deadline'],
    fields: [
      FILTER_FIELDS.department,
      FILTER_FIELDS.status,
      FILTER_FIELDS.priority,
      FILTER_FIELDS.category,
    ],
    detailsHref: DETAILS,
    showUserOnCard: true,
    searchPlaceholder: 'Search by ID, title, complainant or officer…',
    actions: (complaint) => {
      const open = ACTIVE_STATUSES.includes(complaint.status)
      return `
        <a class="btn-icon" href="${DETAILS}?id=${encodeURIComponent(complaint.id)}"
           aria-label="View ${complaint.id}" title="View details">${icon('eye', 'icon-md')}</a>
        ${
          open
            ? `<button type="button" class="btn-icon" data-escalate="${complaint.id}"
                 aria-label="Escalate ${complaint.id}" title="Escalate">${icon('shield-alert', 'icon-md')}</button>`
            : ''
        }
        ${
          complaint.status !== STATUS.CLOSED
            ? `<button type="button" class="btn-icon btn-icon--danger" data-close-complaint="${complaint.id}"
                 aria-label="Close ${complaint.id}" title="Close complaint">${icon('x-circle', 'icon-md')}</button>`
            : ''
        }`
    },
    emptyState: {
      title: 'No complaints found',
      message: 'Nothing matches the current filters.',
    },
  })

  /* ------------------------------------------------------------ map view */

  const mapPanel = qs('#map-panel')
  const toggle = qs('#toggle-map')
  let mapLoaded = false

  async function showMap() {
    const count = qs('#map-count')
    count.textContent = 'Loading complaint locations…'

    try {
      const complaints = await getAllComplaints()
      const tagged = complaints.filter((item) => item.location?.latitude != null)

      const { renderComplaintsMap } = await import('../components/leafletMap.js')
      const map = await renderComplaintsMap(qs('#complaint-map'), tagged, {
        onSelect: (complaint) => {
          window.location.href = `${DETAILS}?id=${encodeURIComponent(complaint.id)}`
        },
      })

      if (!map) {
        count.textContent = 'The map could not be loaded. Check your internet connection.'
        return
      }

      count.textContent = `${tagged.length} of ${complaints.length} complaints are geo-tagged.`
      mapLoaded = true
    } catch (error) {
      count.textContent = `Unable to load the map: ${error.message}`
    }
  }

  toggle.addEventListener('click', () => {
    const showing = mapPanel.hidden
    mapPanel.hidden = !showing
    qs('[data-label]', toggle).textContent = showing ? 'Hide map' : 'Map view'
    if (showing && !mapLoaded) showMap()
  })

  on('#list', 'click', '[data-escalate]', async (event, button) => {
    const id = button.dataset.escalate
    const confirmed = await confirmDialog({
      title: `Escalate ${id}?`,
      message: 'The complaint moves to the next authority level and everyone involved is notified.',
      confirmLabel: 'Escalate',
      tone: 'warning',
    })
    if (!confirmed) return

    try {
      await escalateComplaint(id, user.name)
      toast.success(`${id} has been escalated.`)
      list.reload()
    } catch (error) {
      toast.error(error.message)
    }
  })

  on('#list', 'click', '[data-close-complaint]', async (event, button) => {
    const id = button.dataset.closeComplaint
    const confirmed = await confirmDialog({
      title: `Close ${id}?`,
      message: 'A closed complaint leaves the active queues. The complainant can still reopen it.',
      confirmLabel: 'Close complaint',
      tone: 'danger',
    })
    if (!confirmed) return

    try {
      await closeComplaint(id, user.name)
      toast.success(`${id} has been closed.`)
      list.reload()
    } catch (error) {
      toast.error(error.message)
    }
  })
})
