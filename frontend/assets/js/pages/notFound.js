/**
 * 404 page.
 */

import { icon, mount, ready } from '../components/dom.js'
import { renderPublicChrome } from '../components/publicChrome.js'
import { currentUser } from '../components/session.js'
import { HOME_PAGE } from '../components/navigation.js'

ready(() => {
  renderPublicChrome()

  const user = currentUser()
  const home = user ? HOME_PAGE[user.role] : '/index.html'

  mount('#root', `
    <div class="container" style="padding-block:var(--sp-16)">
      <div class="state" style="max-width:32rem;margin-inline:auto">
        <span class="state__icon">${icon('file-search', 'icon-xl')}</span>
        <p style="font-size:var(--fs-3xl);font-weight:600;color:var(--heading);font-variant-numeric:tabular-nums">404</p>
        <p class="state__title">This page does not exist</p>
        <p class="state__text">
          The address you opened is not part of the grievance portal. It may have been moved, or the
          link may be incorrect.
        </p>
        <div class="state__action row-wrap" style="justify-content:center">
          <a class="btn btn--primary" href="${home}">${icon('home', 'icon-sm')}Go to ${user ? 'dashboard' : 'home page'}</a>
          <a class="btn btn--secondary" href="/track.html">${icon('file-search', 'icon-sm')}Track a complaint</a>
        </div>
      </div>
    </div>`)
})
