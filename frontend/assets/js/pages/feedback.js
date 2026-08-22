/**
 * Feedback page.
 *
 * Two lists: complaints that are resolved but not yet rated, and the ratings
 * already given.
 */

import { esc, icon, mount, qs, ready } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { emptyState, errorState, loadingState, starRating, statusBadge } from '../components/ui.js'
import { getAllComplaints } from '../services/complaintService.js'
import { ROLES, STATUS } from '../utils/constants.js'
import { formatDate } from '../utils/helpers.js'

const DETAILS = '/student/complaint-details.html'

function pendingCard(complaint) {
  return `
    <article class="card card--hover" style="padding:var(--sp-4)">
      <div class="between" style="align-items:flex-start">
        <div class="grow" style="min-width:0">
          <a class="cell-id" href="${DETAILS}?id=${encodeURIComponent(complaint.id)}">${esc(complaint.id)}</a>
          <h3 style="font-size:var(--fs-base);margin-top:.25rem">${esc(complaint.title)}</h3>
          <p class="muted" style="font-size:var(--fs-xs);margin-top:.25rem">
            ${esc(complaint.department)} · Resolved on ${esc(formatDate(complaint.resolvedAt ?? complaint.updatedAt))}
          </p>
        </div>
        ${statusBadge(complaint.status)}
      </div>
      <a class="btn btn--primary btn--sm" style="margin-top:var(--sp-4)"
         href="${DETAILS}?id=${encodeURIComponent(complaint.id)}">
        ${icon('star', 'icon-sm')}Rate this resolution
      </a>
    </article>`
}

function ratedCard(complaint) {
  return `
    <article class="card" style="padding:var(--sp-4)">
      <div class="between" style="align-items:flex-start">
        <div class="grow" style="min-width:0">
          <a class="cell-id" href="${DETAILS}?id=${encodeURIComponent(complaint.id)}">${esc(complaint.id)}</a>
          <h3 style="font-size:var(--fs-base);margin-top:.25rem">${esc(complaint.title)}</h3>
        </div>
        <span class="badge ${complaint.feedback.satisfied ? 'badge--resolved' : 'badge--pending'}">
          ${complaint.feedback.satisfied ? 'Satisfied' : 'Not satisfied'}
        </span>
      </div>

      <div style="margin-top:var(--sp-3)">${starRating(complaint.feedback.rating, { size: 'icon-md' })}</div>
      <p style="margin-top:var(--sp-3)">${esc(complaint.feedback.comment)}</p>
      <p class="muted" style="font-size:var(--fs-xs);margin-top:var(--sp-2)">
        Submitted on ${esc(formatDate(complaint.feedback.at))}
      </p>
    </article>`
}

async function load(user) {
  mount('#lists', loadingState('Loading your complaints…'))

  try {
    const complaints = await getAllComplaints({ userId: user.id })

    const closed = complaints.filter((complaint) =>
      [STATUS.RESOLVED, STATUS.CLOSED].includes(complaint.status),
    )
    const pending = closed.filter((complaint) => !complaint.feedback)
    const rated = closed.filter((complaint) => complaint.feedback)

    qs('#lists').innerHTML = `
      <div class="stack">
        <section class="card">
          <header class="card__head">
            <div>
              <h2 class="card__title">Awaiting your feedback</h2>
              <p class="card__subtitle">Resolved complaints you have not rated yet</p>
            </div>
            <span class="badge badge--progress">${pending.length}</span>
          </header>
          <div class="card__body">
            ${
              pending.length
                ? `<div class="grid grid-2">${pending.map(pendingCard).join('')}</div>`
                : emptyState({
                    icon: 'check-circle',
                    title: 'No pending feedback',
                    message: 'You have rated every resolved complaint. Thank you.',
                  })
            }
          </div>
        </section>

        <section class="card">
          <header class="card__head">
            <div>
              <h2 class="card__title">Feedback you have given</h2>
              <p class="card__subtitle">Your ratings help the departments improve</p>
            </div>
            <span class="badge badge--resolved">${rated.length}</span>
          </header>
          <div class="card__body">
            ${
              rated.length
                ? `<div class="grid grid-2">${rated.map(ratedCard).join('')}</div>`
                : emptyState({
                    icon: 'star',
                    title: 'No feedback yet',
                    message: 'Once a complaint is resolved you can rate how the work was done.',
                  })
            }
          </div>
        </section>
      </div>`
  } catch (error) {
    mount('#lists', errorState({ message: error.message, retryId: 'retry' }))
    qs('#retry')?.addEventListener('click', () => load(user))
  }
}

ready(() => {
  const user = requireRole(ROLES.STUDENT)
  if (!user) return

  renderShell(user, { title: 'Feedback' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'Feedback',
      lead: 'Rate how your complaints were resolved, or reopen the ones that were not.',
      crumbs: [{ label: 'Dashboard', href: '/student/dashboard.html' }, { label: 'Feedback' }],
    })}
    <div id="lists"></div>`

  load(user)
})
