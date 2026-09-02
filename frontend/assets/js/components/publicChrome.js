/**
 * Navbar and footer for the public pages (landing, tracking, 404).
 *
 * The navbar knows whether somebody is signed in, so a returning user sees
 * "Go to dashboard" instead of "Login".
 */

import { esc, icon, on, qs } from './dom.js'
import { currentUser } from './session.js'
import { HOME_PAGE } from './navigation.js'
import {
  APP_NAME,
  ASSETS,
  CONTACT,
  UNIVERSITY_NAME,
  UNIVERSITY_SHORT,
} from '../utils/constants.js'

const LINKS = [
  { label: 'Home', href: '/index.html#top', match: 'home' },
  { label: 'Departments', href: '/index.html#departments' },
  { label: 'How It Works', href: '/index.html#how' },
  { label: 'Track Complaint', href: '/track.html', match: 'track' },
  { label: 'FAQ', href: '/index.html#faq' },
]

/**
 * The DSVV crest.
 *
 * `ASSETS.logo` is a neutral placeholder emblem, not the official crest. The
 * markup also renders a CSS placeholder mark underneath the image, and
 * `onerror` removes the image if the file is ever missing, so the placeholder
 * shows through instead of a broken-image icon.
 */
function logoMark() {
  return `
    <span class="logo__mark-wrap">
      <span class="logo__mark logo__mark--placeholder" aria-hidden="true">${esc(UNIVERSITY_SHORT)}</span>
      <img class="logo__img" src="${esc(ASSETS.logo)}" alt="${esc(UNIVERSITY_NAME)} logo"
           width="44" height="44" loading="eager"
           onerror="this.remove()">
    </span>`
}

export function logo({ light = false, small = false } = {}) {
  return `
    <a class="logo ${light ? 'logo--light' : ''} ${small ? 'logo--sm' : ''}" href="/index.html">
      ${logoMark()}
      <span>
        <span class="logo__name">${esc(UNIVERSITY_NAME)}</span>
        <span class="logo__sub">${esc(APP_NAME)}</span>
      </span>
    </a>`
}

/** Which nav item should carry the active pill, based on the current URL. */
function activeKey() {
  const path = location.pathname
  if (path.endsWith('/track.html')) return 'track'
  if (path === '/' || path.endsWith('/index.html')) return 'home'
  return ''
}

/**
 * @param user           signed-in user, or null
 * @param hideDashboard  the home page keeps its navbar to a plain "Login"
 *                       call to action; the dashboard is reached after
 *                       signing in. Other public pages still offer the
 *                       shortcut to a returning user.
 */
function navActions(user, hideDashboard = false) {
  if (user && !hideDashboard) {
    return `<a class="btn btn--primary btn--sm" href="${esc(HOME_PAGE[user.role])}">
              ${icon('dashboard', 'icon-sm')}Go to dashboard
            </a>`
  }
  return `
    <a class="btn btn--ghost btn--sm" href="/login.html">${icon('log-in', 'icon-sm')}Login</a>
    <a class="btn btn--primary btn--sm" href="/register.html">${icon('user-plus', 'icon-sm')}Register</a>`
}

export function renderNavbar(target = '#navbar', { hideDashboard = false } = {}) {
  const user = currentUser()
  const active = activeKey()
  const links = LINKS.map((link) => {
    const isActive = link.match && link.match === active
    return `<a class="navbar__link ${isActive ? 'is-active' : ''}"
               ${isActive ? 'aria-current="page"' : ''}
               href="${esc(link.href)}">${esc(link.label)}</a>`
  }).join('')

  const node = qs(target)
  if (!node) return

  node.outerHTML = `
    <header class="navbar" id="top">
      <div class="container">
        <div class="navbar__inner">
          ${logo()}
          <nav class="navbar__links" aria-label="Primary">${links}</nav>
          <div class="navbar__actions">${navActions(user, hideDashboard)}</div>
          <button type="button" class="btn-icon navbar__toggle" data-nav-toggle
                  aria-label="Open menu" aria-expanded="false" aria-controls="nav-mobile">
            ${icon('menu', 'icon-md')}
          </button>
        </div>
        <nav class="navbar__mobile" id="nav-mobile" aria-label="Primary (mobile)">
          ${links}
          <div class="navbar__mobile-actions">${navActions(user, hideDashboard)}</div>
        </nav>
      </div>
    </header>`

  const toggle = qs('[data-nav-toggle]')
  const mobile = qs('#nav-mobile')
  toggle?.addEventListener('click', () => {
    const open = mobile.classList.toggle('is-open')
    toggle.setAttribute('aria-expanded', String(open))
  })

  // Close the mobile menu after following a link.
  on(mobile, 'click', 'a', () => {
    mobile.classList.remove('is-open')
    toggle?.setAttribute('aria-expanded', 'false')
  })
}

export function renderFooter(target = '#footer') {
  const node = qs(target)
  if (!node) return

  const year = new Date().getFullYear()

  /*
     No social-media accounts are recorded anywhere in the project, so the
     "Follow us" column from the reference design is deliberately omitted
     rather than filled with invented profile links. Same for a telephone
     number — only the address and mailbox that already exist are shown.
  */
  node.outerHTML = `
    <footer class="footer">
      <div class="container">
        <div class="footer__grid">
          <div class="footer__brand">
            ${logo({ light: true })}
            <p class="footer__place">
              ${icon('map-pin', 'icon-sm')}
              <span>${esc(CONTACT.location)}</span>
            </p>
          </div>

          <div>
            <p class="footer__heading">Quick Links</p>
            <ul class="footer__list">
              <li><a href="/index.html#top">Home</a></li>
              <li><a href="/index.html#departments">Departments</a></li>
              <li><a href="/index.html#how">How It Works</a></li>
              <li><a href="/track.html">Track Complaint</a></li>
              <li><a href="/index.html#faq">FAQ</a></li>
            </ul>
          </div>

          <div>
            <p class="footer__heading">Contact Us</p>
            <ul class="footer__list">
              <li class="footer__item">
                ${icon('map-pin', 'icon-sm')}
                <span>${esc(CONTACT.location)}</span>
              </li>
              <li class="footer__item">
                ${icon('mail', 'icon-sm')}
                <a href="mailto:${esc(CONTACT.email)}">${esc(CONTACT.email)}</a>
              </li>
            </ul>
          </div>
        </div>

        <div class="footer__bottom">
          <p>© ${year} ${esc(UNIVERSITY_NAME)}. All rights reserved.</p>
        </div>
      </div>
    </footer>`
}

/** Convenience for pages that use both. */
export function renderPublicChrome(options = {}) {
  renderNavbar('#navbar', options)
  renderFooter()
}
