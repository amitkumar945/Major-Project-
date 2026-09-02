/**
 * AI classification panel and the duplicate-complaint alert.
 *
 * The numbers currently come from the keyword-and-similarity simulation in
 * `services/complaintService.js`. When the Flask `/api/ai/classify` endpoint is
 * ready it will return exactly this shape, so this component will not change.
 */

import { esc, html, icon } from './dom.js'
import { priorityBadge, progressBar, statusBadge } from './ui.js'
import { formatDate, toPercent } from '../utils/helpers.js'

function metric({ glyph, label, body }) {
  return html(
    '<div class="ai-metric">',
    `<span class="ai-metric__label">${icon(glyph, 'icon-sm')}${esc(label)}</span>`,
    `<div class="ai-metric__value">${body}</div>`,
    '</div>',
  )
}

/**
 * @param {object} options
 * @param {object|null} options.analysis  result from `analyseComplaint`
 * @param {boolean} [options.loading]
 * @param {string} [options.error]
 * @param {boolean} [options.readOnly]    hide the run button on details screens
 */
export function aiAnalysisCard({ analysis = null, loading = false, error = '', readOnly = false } = {}) {
  let body

  if (loading) {
    body = html(
      '<div class="ai-thinking">',
      `<span class="ai-thinking__orb">${icon('cpu', 'icon-xl')}</span>`,
      '<p class="strong" style="margin-top:var(--sp-4)">Analysing your complaint…</p>',
      '<p class="muted">Finding the right department and checking for similar complaints.</p>',
      '</div>',
    )
  } else if (error) {
    body = `<p class="alert alert--danger" role="alert">${esc(error)}</p>`
  } else if (!analysis) {
    body = html(
      '<div class="center" style="padding:var(--sp-8) 0">',
      '<p class="strong" style="font-size:var(--fs-md)">Ready when you are</p>',
      '<p class="muted" style="margin-top:.5rem;max-width:44ch;margin-inline:auto">Tap the button above. We will pick the right department, set how urgent it is, and check whether someone has already reported the same thing.</p>',
      '</div>',
    )
  } else {
    body = html(
      '<div class="ai-metrics">',

      metric({
        glyph: 'building',
        label: 'Department identified',
        body: `<span class="strong">${esc(analysis.department)}</span>`,
      }),

      metric({ glyph: 'zap', label: 'Priority', body: priorityBadge(analysis.priority) }),

      metric({
        glyph: 'gauge',
        label: 'How sure we are',
        body: progressBar({
          value: analysis.confidence * 100,
          tone: analysis.confidence >= 0.85 ? 'success' : 'warning',
          valueLabel: toPercent(analysis.confidence),
          small: true,
        }),
      }),

      metric({
        glyph: 'copy',
        label: 'Chance it is already reported',
        body: progressBar({
          value: analysis.duplicateProbability * 100,
          tone: analysis.duplicateProbability >= 0.5 ? 'danger' : 'slate',
          valueLabel: toPercent(analysis.duplicateProbability),
          small: true,
        }),
      }),

      '</div>',

      '<div style="margin-top:var(--sp-3)">',
      metric({
        glyph: 'user-cog',
        label: 'Officer suggested',
        body: html(
          `<span class="strong">${esc(analysis.suggestedOfficerName ?? analysis.suggestedOfficer)}</span>`,
          analysis.suggestedOfficerName
            ? `<span class="cell-sub">${esc(analysis.suggestedOfficer)}</span>`
            : '',
          '<p class="faint" style="font-size:var(--fs-xs);margin-top:.375rem;font-weight:400">Chosen because this officer currently has the lightest workload in the department.</p>',
        ),
      }),
      '</div>',

      analysis.keywords?.length
        ? html(
            '<div style="margin-top:var(--sp-4)">',
            '<p class="muted" style="font-weight:500">Words we picked up from your description</p>',
            `<div class="chips" style="margin-top:.5rem">${analysis.keywords
              .map((word) => `<span class="chip">${esc(word)}</span>`)
              .join('')}</div>`,
            '</div>',
          )
        : '',

      analysis.alternatives?.length > 1
        ? html(
            '<div style="margin-top:var(--sp-4)">',
            '<p class="muted" style="font-weight:500">Other departments considered</p>',
            '<div class="stack-sm" style="margin-top:.5rem;gap:.5rem">',
            analysis.alternatives
              .map((alternative) => {
                const top = analysis.alternatives[0].score || 1
                return progressBar({
                  value: (alternative.score / top) * 100,
                  tone: alternative.department === analysis.department ? '' : 'slate',
                  label: alternative.department,
                  valueLabel: `${alternative.score} match${alternative.score === 1 ? '' : 'es'}`,
                  small: true,
                })
              })
              .join(''),
            '</div></div>',
          )
        : '',

      '<p class="faint" style="font-size:var(--fs-xs);margin-top:var(--sp-4);padding-top:var(--sp-3);border-top:1px solid var(--border-soft)">',
      'Set automatically. You can change the department on the first step if this looks wrong.',
      '</p>',
    )
  }

  return html(
    '<section class="ai-card" data-ai-card>',
    '<header class="ai-card__head">',
    '<div class="row">',
    `<span class="ai-card__mark">${icon('sparkles', 'icon-md')}</span>`,
    '<div>',
    '<h2 class="strong" style="font-size:var(--fs-md)">Automatic check</h2>',
    '<p class="muted">You don’t need to select the department. We identify it for you and check for similar complaints.</p>',
    '</div></div>',
    readOnly
      ? ''
      : `<button type="button" class="btn ${analysis ? 'btn--secondary' : 'btn--primary'} btn--sm" data-run-ai ${
          loading ? 'disabled' : ''
        }>${icon('zap', 'icon-sm')}${analysis ? 'Check again' : 'Start check'}</button>`,
    '</header>',
    `<div class="card__body">${body}</div>`,
    '</section>',
  )
}

/* ======================================================== DUPLICATES ====== */

/**
 * "Possible duplicate complaints found".
 *
 * The user is never blocked - they can always continue - but they get the
 * chance to follow an existing complaint instead of filing the same issue twice.
 */
export function duplicateAlert(duplicates = [], { detailsHref, showActions = true } = {}) {
  if (!duplicates.length) return ''

  const rows = duplicates
    .map((duplicate) => {
      const tone =
        duplicate.similarity >= 70 ? 'is-high' : duplicate.similarity >= 40 ? 'is-mid' : 'is-low'

      return html(
        '<li class="dupe-row">',
        '<div class="grow" style="min-width:0">',
        '<div class="row-wrap" style="gap:.5rem">',
        `<span class="cell-id">${esc(duplicate.id)}</span>`,
        statusBadge(duplicate.status),
        `<span class="muted" style="font-size:var(--fs-xs)">${esc(formatDate(duplicate.submittedAt))}</span>`,
        '</div>',
        `<p class="strong" style="margin-top:.25rem">${esc(duplicate.title)}</p>`,
        `<p class="muted" style="font-size:var(--fs-xs)">${esc(duplicate.department)}</p>`,
        '</div>',
        '<div class="row" style="gap:var(--sp-4)">',
        '<div class="right">',
        '<p class="muted" style="font-size:var(--fs-xs)">Similar</p>',
        `<p class="dupe-row__score ${tone}">${duplicate.similarity}%</p>`,
        '</div>',
        `<a class="btn btn--secondary btn--sm" href="${esc(detailsHref)}?id=${encodeURIComponent(duplicate.id)}">
           ${icon('external-link', 'icon-sm')}Open
         </a>`,
        '</div></li>',
      )
    })
    .join('')

  return html(
    '<section class="dupes anim-up" role="alert" data-duplicates>',
    '<header class="dupes__head">',
    `<span class="dupes__mark">${icon('copy', 'icon-md')}</span>`,
    '<div>',
    '<h2 class="strong" style="font-size:var(--fs-md);color:var(--amber-700)">Someone may have reported this already</h2>',
    '<p style="font-size:var(--fs-sm);color:var(--amber-700)">Have a quick look below. If none of these match your problem, carry on.</p>',
    '</div></header>',
    `<ul>${rows}</ul>`,
    showActions
      ? html(
          '<footer style="display:flex;justify-content:flex-end;gap:var(--sp-2);padding:var(--sp-3) var(--sp-5);border-top:1px solid var(--amber-100)">',
          '<button type="button" class="btn btn--warning" data-continue-anyway>None of these — continue</button>',
          '</footer>',
        )
      : '',
    '</section>',
  )
}
