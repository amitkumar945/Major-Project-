/**
 * Dashboard shell - sidebar, top bar and page header.
 *
 * Every dashboard page has the same three lines of markup in its <body>:
 *
 *   <div id="sidebar"></div>
 *   <div class="app__main"><div id="topbar"></div><main class="page">…</main></div>
 *
 * and this module fills them in. That is how the navigation stays in one place
 * without a templating engine.
 */

import { esc, icon, on, qs, qsa } from './dom.js'
import { avatar } from './ui.js'
import { confirmDialog } from './modal.js'
import { MENUS } from './navigation.js'
import { roleLabel, signOut } from './session.js'
import { getUnreadCount } from '../services/notificationService.js'
import { APP_NAME, UNIVERSITY_SHORT } from '../utils/constants.js'

/* ------------------------------------------------------------- sidebar --- */

function sidebarMarkup(user, activeHref) {
  const items = (MENUS[user.role] ?? [])
    .map((item) => {
      const active = activeHref.startsWith(item.href) ? 'is-active' : ''
      const badge = item.badge === 'unread'
        ? '<span class="badge badge--counter" data-unread-badge hidden>0</span>'
        : ''
      return `<a class="sidebar__link ${active}" href="${esc(item.href)}" ${active ? 'aria-current="page"' : ''}>
                ${icon(item.icon, 'icon-md')}<span class="grow">${esc(item.label)}</span>${badge}
              </a>`
    })
    .join('')

  return `
    <aside class="sidebar" id="app-sidebar">
      <div class="sidebar__head">
        <a class="logo logo--light logo--sm" href="/index.html">
          <span class="logo__mark">${icon('shield-check', 'icon-md')}</span>
          <span>
            <span class="logo__name">${esc(UNIVERSITY_SHORT)} ${esc(APP_NAME)}</span>
          </span>
        </a>
        <button type="button" class="btn-icon sidebar__close" data-close-sidebar
                aria-label="Close menu" style="color:var(--slate-400)">
          ${icon('x', 'icon-md')}
        </button>
      </div>

      <nav class="sidebar__nav scroll-slim" aria-label="Main">
        <p class="sidebar__section">${esc(roleLabel(user.role))}</p>
        ${items}
      </nav>

      <div class="sidebar__foot">
        <div class="sidebar__user">
          ${avatar(user.name, user.avatarColor, 'sm')}
          <span class="grow" style="min-width:0">
            <span class="sidebar__user-name truncate">${esc(user.name)}</span>
            <span class="sidebar__user-role truncate">${esc(user.userId ?? user.employeeId ?? '')}</span>
          </span>
        </div>
        <button type="button" class="sidebar__logout" data-logout>
          ${icon('log-out', 'icon-md')}Logout
        </button>
      </div>
    </aside>`
}

/* -------------------------------------------------------------- topbar --- */

function topbarMarkup(user, title) {
  return `
    <header class="topbar">
      <button type="button" class="btn-icon topbar__toggle" data-open-sidebar aria-label="Open menu"
              aria-controls="app-sidebar" aria-expanded="false">
        ${icon('menu', 'icon-md')}
      </button>

      <p class="strong truncate" style="font-size:var(--fs-md)">${esc(title)}</p>

      <div class="topbar__actions">
        <a class="btn-icon bell" href="${esc(notificationsHref(user.role))}" aria-label="Notifications">
          ${icon('bell', 'icon-md')}
          <span class="bell__dot" data-unread-badge hidden>0</span>
        </a>

        <div class="menu">
          <button type="button" class="btn-icon" data-account aria-haspopup="true" aria-expanded="false"
                  aria-label="Account menu" style="width:auto;padding-inline:.25rem">
            ${avatar(user.name, user.avatarColor, 'xs')}
            ${icon('chevron-down', 'icon-sm')}
          </button>
          <div class="menu__panel" data-account-panel hidden>
            <div class="menu__header">
              <p class="strong truncate">${esc(user.name)}</p>
              <p class="muted truncate">${esc(user.email)}</p>
            </div>
            <a class="menu__item" href="${esc(profileHref(user.role))}">${icon('user', 'icon-sm')}My profile</a>
            <a class="menu__item" href="${esc(notificationsHref(user.role))}">${icon('bell', 'icon-sm')}Notifications</a>
            <button type="button" class="menu__item menu__item--danger" data-logout>
              ${icon('log-out', 'icon-sm')}Logout
            </button>
          </div>
        </div>
      </div>
    </header>`
}

function notificationsHref(role) {
  return `/${role}/notifications.html`
}

function profileHref(role) {
  return `/${role}/profile.html`
}

/* ------------------------------------------------------------ page head --- */

/**
 * Page title block with breadcrumbs and action buttons.
 * `crumbs` is [{ label, href }]; the last entry is rendered as the current page.
 */
export function pageHeader({ title, lead = '', crumbs = [], actions = '' }) {
  const trail = crumbs
    .map((crumb, index) => {
      const separator = index > 0 ? icon('chevron-right', 'icon-sm') : ''
      const body = crumb.href
        ? `<a href="${esc(crumb.href)}">${esc(crumb.label)}</a>`
        : `<span class="is-current">${esc(crumb.label)}</span>`
      return separator + body
    })
    .join('')

  return `
    <div class="page__head">
      ${crumbs.length ? `<nav class="page__crumbs" aria-label="Breadcrumb">${trail}</nav>` : ''}
      <div class="page__bar">
        <div class="grow">
          <h1 class="page__title">${esc(title)}</h1>
          ${lead ? `<p class="page__lead">${esc(lead)}</p>` : ''}
        </div>
        ${actions ? `<div class="page__actions">${actions}</div>` : ''}
      </div>
    </div>`
}

/* -------------------------------------------------------------- render --- */

/**
 * Draw the shell and wire up the drawer, the account menu and logout.
 * Call once at the top of every dashboard page script.
 */
export function renderShell(user, { title }) {
  const activeHref = location.pathname

  qs('#sidebar').outerHTML = sidebarMarkup(user, activeHref)
  qs('#topbar').outerHTML = topbarMarkup(user, title)

  document.title = `${title} · ${UNIVERSITY_SHORT} ${APP_NAME}`

  wireDrawer()
  wireAccountMenu()
  wireLogout()
  refreshUnreadBadge(user)
}

/* The sidebar is a drawer below 1024px and a fixed column above it. */
function wireDrawer() {
  const sidebar = qs('#app-sidebar')
  let overlay = null

  function open() {
    sidebar.classList.add('is-open')
    qs('[data-open-sidebar]')?.setAttribute('aria-expanded', 'true')
    overlay = document.createElement('div')
    overlay.className = 'sidebar-overlay'
    overlay.addEventListener('click', close)
    document.body.appendChild(overlay)
    document.body.style.overflow = 'hidden'
  }

  function close() {
    sidebar.classList.remove('is-open')
    qs('[data-open-sidebar]')?.setAttribute('aria-expanded', 'false')
    overlay?.remove()
    overlay = null
    document.body.style.overflow = ''
  }

  on(document, 'click', '[data-open-sidebar]', open)
  on(document, 'click', '[data-close-sidebar]', close)

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('is-open')) close()
  })

  // Tidy up if the window is resized past the breakpoint while the drawer is open.
  window.addEventListener('resize', () => {
    if (window.innerWidth >= 1024 && sidebar.classList.contains('is-open')) close()
  })
}

function wireAccountMenu() {
  const button = qs('[data-account]')
  const panel = qs('[data-account-panel]')
  if (!button || !panel) return

  function setOpen(open) {
    panel.hidden = !open
    button.setAttribute('aria-expanded', String(open))
  }

  button.addEventListener('click', (event) => {
    event.stopPropagation()
    setOpen(panel.hidden)
  })

  document.addEventListener('click', (event) => {
    if (!panel.hidden && !panel.contains(event.target)) setOpen(false)
  })

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setOpen(false)
  })
}

function wireLogout() {
  on(document, 'click', '[data-logout]', async () => {
    const confirmed = await confirmDialog({
      title: 'Sign out of your account?',
      message: 'You will need to sign in again to view or raise complaints.',
      confirmLabel: 'Sign out',
      tone: 'warning',
    })
    if (confirmed) await signOut()
  })
}

/** Unread count shown on the bell and beside the sidebar link. */
export async function refreshUnreadBadge(user) {
  try {
    const count = await getUnreadCount(user.id)
    qsa('[data-unread-badge]').forEach((badge) => {
      badge.textContent = count > 99 ? '99+' : String(count)
      badge.hidden = count === 0
    })
  } catch {
    /* The badge is not important enough to interrupt the page. */
  }
}
