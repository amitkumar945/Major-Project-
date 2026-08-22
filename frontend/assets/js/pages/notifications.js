/**
 * Notification centre - shared by all three roles.
 *
 * The page it sits in decides the role, so `/student/notifications.html`,
 * `/officer/notifications.html` and `/admin/notifications.html` all run this
 * one script.
 */

import { icon, mount, on, qs, ready } from '../components/dom.js'
import { pageHeader, refreshUnreadBadge, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { emptyState, errorState, loadingState } from '../components/ui.js'
import { notificationItem } from '../components/notificationItem.js'
import { toast } from '../components/toast.js'
import {
  deleteNotification,
  getNotifications,
  markAllAsRead,
  markAsRead,
} from '../services/notificationService.js'
import { ROLES } from '../utils/constants.js'

const ROLE = location.pathname.startsWith('/officer/')
  ? ROLES.OFFICER
  : location.pathname.startsWith('/admin/')
    ? ROLES.ADMIN
    : ROLES.STUDENT

const DETAILS = `/${ROLE}/complaint-details.html`
const HOME = `/${ROLE}/dashboard.html`

let user = null
let items = []
let filter = 'all'

function view() {
  const unread = items.filter((item) => !item.read).length
  const shown = filter === 'unread' ? items.filter((item) => !item.read) : items

  const tabs = [
    { id: 'all', label: 'All', count: items.length },
    { id: 'unread', label: 'Unread', count: unread },
  ]
    .map(
      (tab) => `
      <button type="button" class="tab" role="tab" data-tab="${tab.id}"
              aria-selected="${filter === tab.id}">
        ${tab.label}<span class="tab__count">${tab.count}</span>
      </button>`,
    )
    .join('')

  return `
    <section class="card">
      <header class="card__head">
        <div class="grow"><div class="tabs" role="tablist">${tabs}</div></div>
        ${
          unread
            ? `<button type="button" class="btn btn--secondary btn--sm" data-read-all>
                 ${icon('check', 'icon-sm')}Mark all as read</button>`
            : ''
        }
      </header>

      <div class="card__body card__body--flush">
        ${
          shown.length
            ? shown.map((item) => notificationItem(item, { detailsHref: DETAILS })).join('')
            : emptyState({
                icon: 'bell',
                title: filter === 'unread' ? 'No unread notifications' : 'No notifications yet',
                message:
                  filter === 'unread'
                    ? 'You are all caught up.'
                    : 'Updates about your complaints will appear here.',
              })
        }
      </div>
    </section>`
}

function draw() {
  qs('#list-area').innerHTML = view()
}

async function load() {
  mount('#list-area', loadingState('Loading notifications…'))

  try {
    items = await getNotifications(user.id)
    draw()
  } catch (error) {
    mount('#list-area', errorState({ message: error.message, retryId: 'retry' }))
    qs('#retry')?.addEventListener('click', load)
  }
}

ready(() => {
  user = requireRole(ROLE)
  if (!user) return

  renderShell(user, { title: 'Notifications' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'Notifications',
      lead: 'Every update on the complaints you are involved with.',
      crumbs: [{ label: 'Dashboard', href: HOME }, { label: 'Notifications' }],
    })}
    <div id="list-area"></div>`

  load()

  const area = qs('#list-area')

  on(area, 'click', '[data-tab]', (event, button) => {
    filter = button.dataset.tab
    draw()
  })

  on(area, 'click', '[data-mark-read]', async (event, button) => {
    const id = button.closest('[data-id]').dataset.id
    await markAsRead(id)
    items = items.map((item) => (item.id === id ? { ...item, read: true } : item))
    draw()
    refreshUnreadBadge(user)
  })

  on(area, 'click', '[data-read-all]', async () => {
    await markAllAsRead(user.id)
    items = items.map((item) => ({ ...item, read: true }))
    draw()
    refreshUnreadBadge(user)
    toast.success('All notifications marked as read.')
  })

  on(area, 'click', '[data-delete]', async (event, button) => {
    const id = button.closest('[data-id]').dataset.id
    await deleteNotification(id)
    items = items.filter((item) => item.id !== id)
    draw()
    refreshUnreadBadge(user)
    toast.info('Notification removed.')
  })
})
