/**
 * Landing page.
 *
 * The content is written directly in `index.html`; this script only injects the
 * shared navbar and footer and makes the FAQ accordion work.
 */

import { on, qsa, ready } from '../components/dom.js'
import { renderPublicChrome } from '../components/publicChrome.js'

ready(() => {
  // The public home page leads with "Login" rather than a dashboard shortcut;
  // the dashboard is reached after signing in.
  renderPublicChrome({ hideDashboard: true })

  // FAQ accordion. Opening one answer closes the others.
  on('#faq-list', 'click', '.faq__q', (event, button) => {
    const panel = document.getElementById(button.getAttribute('aria-controls'))
    const willOpen = button.getAttribute('aria-expanded') === 'false'

    qsa('.faq__q').forEach((other) => {
      other.setAttribute('aria-expanded', 'false')
      document.getElementById(other.getAttribute('aria-controls')).hidden = true
    })

    if (willOpen) {
      button.setAttribute('aria-expanded', 'true')
      panel.hidden = false
    }
  })

  revealOnScroll()
})

/**
 * Fade each marked block in the first time it scrolls into view.
 *
 * Visitors who prefer reduced motion never see the transition — the CSS only
 * defines it inside a `prefers-reduced-motion: no-preference` query — so the
 * class is simply added and the content shows immediately. If
 * IntersectionObserver is unavailable the blocks are revealed straight away
 * rather than left invisible.
 */
function revealOnScroll() {
  const blocks = qsa('.reveal')
  if (!blocks.length || !('IntersectionObserver' in window)) return

  // Opt the page into the hidden-then-revealed styling only now that the
  // observer below is guaranteed to run and put the content back.
  document.documentElement.classList.add('js-reveal')

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        entry.target.classList.add('is-visible')
        observer.unobserve(entry.target)
      })
    },
    { rootMargin: '0px 0px -10% 0px', threshold: 0.05 },
  )

  blocks.forEach((block) => observer.observe(block))
}
