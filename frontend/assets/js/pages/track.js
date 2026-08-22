/**
 * Public complaint tracking.
 *
 * Anyone with a reference number can see the status of a complaint without
 * signing in. Personal contact details are deliberately not shown here.
 */

import { esc, icon, mount, on, qs, ready, setLoading } from '../components/dom.js'
import { renderPublicChrome } from '../components/publicChrome.js'
import { errorState, infoRow, priorityBadge, statusBadge } from '../components/ui.js'
import { complaintTimeline } from '../components/timeline.js'
import { deadlineBanner, hydrateMaps, mapPreview } from '../components/complaintParts.js'
import { trackComplaint } from '../services/complaintService.js'
import { formatDate, formatDateTime } from '../utils/helpers.js'

function searchView(prefill = '') {
  return `
    <section class="section" style="padding-block:var(--sp-12)">
      <div class="container" style="max-width:44rem">
        <div class="section__head">
          <p class="section__eyebrow">Track a complaint</p>
          <h1 class="section__title">Where has my complaint reached?</h1>
          <p class="section__lead">
            Enter the reference number you received when the complaint was registered.
          </p>
        </div>

        <form class="card" id="track-form" novalidate style="padding:var(--sp-5)">
          <div class="field" data-field="reference">
            <label class="field__label" for="reference">Complaint reference number</label>
            <div class="field__wrap">
              <span class="icon-left">${icon('file-search', 'icon-sm')}</span>
              <input type="text" class="field__control mono" id="reference" name="reference"
                     value="${esc(prefill)}" placeholder="DSVV-GRV-2026-00101"
                     autocomplete="off" spellcheck="false" required>
            </div>
            <p class="field__hint">The number looks like DSVV-GRV-2026-00101.</p>
          </div>

          <button type="submit" class="btn btn--primary btn--block btn--lg" style="margin-top:var(--sp-4)">
            ${icon('search', 'icon-md')}Track complaint
          </button>
        </form>

        <div id="result" style="margin-top:var(--sp-6)"></div>
      </div>
    </section>`
}

function resultView(complaint) {
  return `
    <div class="stack anim-up">
      ${deadlineBanner(complaint)}

      <section class="card">
        <header class="card__head">
          <div class="grow" style="min-width:0">
            <p class="cell-id" style="font-size:var(--fs-sm)">${esc(complaint.id)}</p>
            <h2 class="card__title" style="margin-top:.25rem">${esc(complaint.title)}</h2>
          </div>
          <div class="row" style="gap:.5rem">
            ${priorityBadge(complaint.priority)}${statusBadge(complaint.status)}
          </div>
        </header>

        <div class="card__body">
          <div class="info-list">
            ${infoRow('Department', esc(complaint.department))}
            ${infoRow('Category', esc(complaint.category))}
            ${infoRow('Location', esc(complaint.location?.address ?? '—'))}
            ${infoRow('Submitted on', esc(formatDateTime(complaint.submittedAt)))}
            ${infoRow('Last updated', esc(formatDateTime(complaint.updatedAt)))}
            ${infoRow('Expected resolution', esc(formatDate(complaint.deadline)))}
            ${infoRow(
              'Handled by',
              complaint.assignedOfficer
                ? `${esc(complaint.assignedOfficer.name)} <span class="cell-sub">${esc(complaint.assignedOfficer.designation)}</span>`
                : '<span class="faint">Not assigned yet</span>',
            )}
          </div>
        </div>
      </section>

      <div class="split">
        <section class="card">
          <header class="card__head"><h2 class="card__title">Status timeline</h2></header>
          <div class="card__body">${complaintTimeline(complaint.timeline)}</div>
        </section>

        <div class="stack">
          <section class="card">
            <header class="card__head"><h2 class="card__title">Location</h2></header>
            <div class="card__body">
              ${mapPreview({ ...complaint.location })}
            </div>
          </section>

          ${
            complaint.resolution
              ? `<section class="card">
                   <header class="card__head"><h2 class="card__title">Resolution</h2></header>
                   <div class="card__body">
                     <p>${esc(complaint.resolution.notes)}</p>
                     <p class="muted" style="margin-top:var(--sp-3)">
                       Completed by ${esc(complaint.resolution.completedBy)} on
                       ${esc(formatDate(complaint.resolution.completedAt))}
                     </p>
                   </div>
                 </section>`
              : ''
          }
        </div>
      </div>

      <p class="note-dashed">
        Sign in to see the full history of your complaints, add remarks and give feedback.
      </p>
    </div>`
}

ready(() => {
  renderPublicChrome()

  const prefill = new URLSearchParams(location.search).get('id') ?? ''
  mount('#root', searchView(prefill))

  const form = qs('#track-form')
  const result = qs('#result')

  async function lookup(reference) {
    const button = qs('button[type="submit"]', form)
    setLoading(button, true, 'Searching…')
    result.innerHTML = ''

    try {
      const complaint = await trackComplaint(reference)
      result.innerHTML = resultView(complaint)
      hydrateMaps(result)
    } catch (error) {
      result.innerHTML = errorState({
        title: 'Complaint not found',
        message: error.message,
      })
    } finally {
      setLoading(button, false)
    }
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault()
    const reference = qs('#reference').value.trim()
    if (!reference) {
      qs('#reference').focus()
      return
    }
    lookup(reference)
  })

  // Deep link: /track.html?id=DSVV-GRV-2026-00101 looks it up immediately.
  if (prefill) lookup(prefill)
})
