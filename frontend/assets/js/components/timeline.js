/**
 * Vertical status timeline on the complaint tracking screen.
 *
 * Completed stages show a green tick and a timestamp, the current stage is
 * highlighted in the brand colour, and future stages are greyed out.
 */

import { esc, html, icon } from './dom.js'
import { formatDateTime } from '../utils/helpers.js'

const VARIANTS = {
  danger: { className: 'is-danger', glyph: 'alert-octagon' },
  warning: { className: 'is-warning', glyph: 'rotate-ccw' },
  success: { className: 'is-done', glyph: 'check' },
}

function stageLook(entry) {
  if (entry.variant && VARIANTS[entry.variant]) return VARIANTS[entry.variant]
  if (entry.state === 'done') return { className: 'is-done', glyph: 'check' }
  if (entry.state === 'current') return { className: 'is-current', glyph: 'clock' }
  return { className: 'is-pending', glyph: 'circle' }
}

export function complaintTimeline(timeline = []) {
  if (!timeline.length) {
    return '<p class="muted">No timeline information is available yet.</p>'
  }

  const items = timeline
    .map((entry) => {
      const look = stageLook(entry)
      return html(
        `<li class="timeline__item ${look.className}">`,
        `<span class="timeline__dot">${icon(look.glyph, 'icon-sm')}</span>`,
        '<div class="grow" style="min-width:0">',
        '<div class="timeline__head">',
        `<h3 class="timeline__label">${esc(entry.label)}</h3>`,
        entry.at
          ? `<time class="timeline__time" datetime="${esc(entry.at)}">${esc(formatDateTime(entry.at))}</time>`
          : '<span class="timeline__time">Pending</span>',
        '</div>',
        `<p class="timeline__desc">${esc(entry.description)}</p>`,
        entry.actor && entry.state !== 'pending'
          ? `<p class="timeline__actor">By <span class="strong">${esc(entry.actor)}</span></p>`
          : '',
        '</div></li>',
      )
    })
    .join('')

  return `<ol class="timeline">${items}</ol>`
}

export default complaintTimeline
