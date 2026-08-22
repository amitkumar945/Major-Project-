/**
 * Small presentational pieces shared by every screen.
 *
 * Each function returns an HTML string, so a page can compose a screen the way
 * it would compose components:
 *
 *   mount('#list', complaints.map(complaintCard).join(''))
 */

import { esc, html, icon } from './dom.js'
import {
  ESCALATION_STYLES,
  PRIORITY,
  PRIORITY_STYLES,
  STATUS_STYLES,
} from '../utils/constants.js'
import { formatDate, getDeadlineState, getInitials, truncate } from '../utils/helpers.js'

/* =============================================================== BADGES === */

/** Coloured pill for a complaint status. */
export function statusBadge(status) {
  const modifier = STATUS_STYLES[status] ?? 'badge--submitted'
  return `<span class="badge ${modifier}"><span class="badge__dot"></span>${esc(status)}</span>`
}

const PRIORITY_ICONS = {
  [PRIORITY.LOW]: 'arrow-down',
  [PRIORITY.MEDIUM]: 'minus',
  [PRIORITY.HIGH]: 'arrow-up',
  [PRIORITY.URGENT]: 'alert-triangle',
}

/** Coloured pill for a complaint priority, with a direction icon. */
export function priorityBadge(priority) {
  const modifier = PRIORITY_STYLES[priority] ?? 'badge--low'
  const glyph = PRIORITY_ICONS[priority] ?? 'minus'
  return `<span class="badge ${modifier}">${icon(glyph, 'icon-sm')}${esc(priority)}</span>`
}

/** Pill showing which escalation level a complaint has reached. */
export function escalationBadge(level) {
  const modifier = ESCALATION_STYLES[level] ?? 'badge--progress'
  return `<span class="badge ${modifier}">Level ${esc(level)}</span>`
}

/* =============================================================== AVATAR === */

export function avatar(name, color = '#4f46e5', size = 'md') {
  return `<span class="avatar avatar--${esc(size)}" style="background:${esc(color)}" aria-hidden="true">${esc(getInitials(name))}</span>`
}

/* ================================================================ STATES === */

/** "No complaints found" and friends. */
export function emptyState({ icon: glyph = 'inbox', title = 'Nothing here yet', message = '', action = '' }) {
  return html(
    '<div class="state">',
    `<span class="state__icon">${icon(glyph, 'icon-xl')}</span>`,
    `<p class="state__title">${esc(title)}</p>`,
    message && `<p class="state__text">${esc(message)}</p>`,
    action && `<div class="state__action">${action}</div>`,
    '</div>',
  )
}

/** Shown when a service call fails. Always offers a way to try again. */
export function errorState({
  title = 'Unable to load data',
  message = 'Something went wrong while fetching the information. Please try again.',
  retryId = '',
} = {}) {
  return html(
    '<div class="state state--error" role="alert">',
    `<span class="state__icon">${icon('server-crash', 'icon-xl')}</span>`,
    `<p class="state__title">${esc(title)}</p>`,
    `<p class="state__text">${esc(message)}</p>`,
    retryId &&
      `<div class="state__action"><button type="button" class="btn btn--secondary" id="${esc(retryId)}">${icon('refresh')}Try again</button></div>`,
    '</div>',
  )
}

export function loadingState(label = 'Loading…') {
  return `<div class="loading" role="status"><span class="loading__spinner"></span><p>${esc(label)}</p></div>`
}

/** Grey blocks that stand in for a table while it loads. */
export function skeletonTable(rows = 6, columns = 6) {
  const row = `<div class="row" style="gap:var(--sp-3)">${Array.from(
    { length: columns },
    () => '<div class="skeleton grow" style="height:1.5rem"></div>',
  ).join('')}</div>`

  return html(
    '<div class="stack-sm" style="padding:var(--sp-5)">',
    '<div class="skeleton" style="height:2.25rem"></div>',
    Array.from({ length: rows }, () => row).join(''),
    '</div>',
  )
}

/** Grey blocks that stand in for the dashboard summary strip. */
export function skeletonCards(count = 4) {
  const card = html(
    '<div class="card" style="padding:var(--sp-5)">',
    '<div class="skeleton" style="height:1rem;width:6rem"></div>',
    '<div class="skeleton" style="height:2rem;width:4rem;margin-top:var(--sp-4)"></div>',
    '</div>',
  )
  return `<div class="grid grid-4">${Array.from({ length: count }, () => card).join('')}</div>`
}

/* ============================================================= PROGRESS === */

export function progressBar({ value = 0, max = 100, tone = '', label = '', valueLabel = '', small = false }) {
  const percent = Math.min(Math.max((value / max) * 100, 0), 100)
  return html(
    `<div class="progress ${small ? 'progress--sm' : ''}">`,
    (label || valueLabel) &&
      html(
        '<div class="progress__head">',
        label && `<span class="progress__label">${esc(label)}</span>`,
        valueLabel && `<span class="progress__value">${esc(valueLabel)}</span>`,
        '</div>',
      ),
    `<div class="progress__track" role="progressbar" aria-valuenow="${Math.round(percent)}" aria-valuemin="0" aria-valuemax="100" aria-label="${esc(label || 'Progress')}">`,
    `<div class="progress__bar ${tone ? `progress__bar--${esc(tone)}` : ''}" style="width:${percent}%"></div>`,
    '</div></div>',
  )
}

/* ================================================================ STATS === */

/** Dashboard summary tile. */
export function statCard({ label, value, icon: glyph, tone = '', hint = '', href = '' }) {
  const inner = html(
    `<p class="stat__label">${esc(label)}</p>`,
    `<p class="stat__value">${esc(value)}</p>`,
    hint && `<p class="stat__hint">${esc(hint)}</p>`,
    glyph && `<span class="stat__icon">${icon(glyph, 'icon-lg')}</span>`,
  )

  const classes = `card card--hover stat ${tone ? `stat--${esc(tone)}` : ''}`
  return href
    ? `<a class="${classes}" href="${esc(href)}">${inner}</a>`
    : `<div class="${classes}">${inner}</div>`
}

/* ============================================================== RATING === */

/** Star rating. Read-only unless `interactive` is true. */
export function starRating(value = 0, { interactive = false, size = 'icon-lg' } = {}) {
  const labels = { 1: 'Very poor', 2: 'Not satisfied', 3: 'Average', 4: 'Good', 5: 'Excellent' }

  const stars = [1, 2, 3, 4, 5]
    .map(
      (star) => html(
        `<button type="button" class="rating__star ${star <= value ? 'is-on' : ''}"`,
        interactive ? ` data-star="${star}"` : ' disabled',
        ` aria-label="${star} star${star > 1 ? 's' : ''} - ${labels[star]}">`,
        icon('star', size),
        '</button>',
      ),
    )
    .join('')

  return html(
    '<div class="rating">',
    `<div class="rating__stars" ${interactive ? 'role="radiogroup" aria-label="Select a rating"' : `role="img" aria-label="Rated ${value} out of 5"`}>${stars}</div>`,
    value > 0 ? `<span class="rating__label">${esc(labels[value])}</span>` : '',
    '</div>',
  )
}

/* =============================================================== ALERTS === */

export function alertBox({ tone = 'info', icon: glyph = 'info', title = '', text = '' }) {
  return html(
    `<div class="alert alert--${esc(tone)}">`,
    `<span class="alert__icon">${icon(glyph, 'icon-lg')}</span>`,
    '<div class="grow">',
    title && `<p class="alert__title">${esc(title)}</p>`,
    text && `<p class="alert__text">${esc(text)}</p>`,
    '</div></div>',
  )
}

/* =========================================================== PAGINATION === */

/** Page numbers with ellipses: 1 … 4 5 [6] 7 8 … 20 */
function pageNumbers(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1)

  const pages = [1]
  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)

  if (start > 2) pages.push('…')
  for (let page = start; page <= end; page += 1) pages.push(page)
  if (end < total - 1) pages.push('…')
  pages.push(total)

  return pages
}

export function pagination({ page, totalPages, total, pageSize }) {
  if (!total) return ''

  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)

  const buttons = pageNumbers(page, totalPages)
    .map((item) =>
      item === '…'
        ? '<span class="page-gap">…</span>'
        : `<button type="button" class="page-btn" data-page="${item}" ${item === page ? 'aria-current="page"' : ''}>${item}</button>`,
    )
    .join('')

  return html(
    '<nav class="pagination" aria-label="Pagination">',
    '<div class="row-wrap">',
    `<p class="muted">Showing <span class="strong tnum">${from}</span>–<span class="strong tnum">${to}</span> of <span class="strong tnum">${total}</span></p>`,
    '<label class="row muted" style="gap:var(--sp-2)">Rows',
    `<select class="field__control" style="width:auto;padding:.25rem 1.75rem .25rem .5rem" data-page-size aria-label="Rows per page">`,
    [5, 10, 25, 50]
      .map((size) => `<option value="${size}" ${size === pageSize ? 'selected' : ''}>${size}</option>`)
      .join(''),
    '</select></label>',
    '</div>',
    '<div class="pagination__pages">',
    `<button type="button" class="page-btn" data-page="${page - 1}" ${page <= 1 ? 'disabled' : ''} aria-label="Previous page">${icon('chevron-left', 'icon-sm')}</button>`,
    buttons,
    `<button type="button" class="page-btn" data-page="${page + 1}" ${page >= totalPages ? 'disabled' : ''} aria-label="Next page">${icon('chevron-right', 'icon-sm')}</button>`,
    '</div></nav>',
  )
}

/* ============================================================= DETAILS === */

/** Label/value row used on the complaint details and profile screens. */
export function infoRow(label, value) {
  return html(
    '<div class="info-row">',
    `<span class="info-row__label">${esc(label)}</span>`,
    `<span class="info-row__value">${value}</span>`,
    '</div>',
  )
}

/* ======================================================== COMPLAINT CARD === */

/** Card view of a complaint, used instead of the table on small screens. */
export function complaintCard(complaint, { linkBase, showUser = false, footer = '' } = {}) {
  const deadline = getDeadlineState(complaint)

  const deadlineNote =
    deadline.state === 'met'
      ? ''
      : html(
          `<p class="deadline-note ${deadline.state === 'overdue' ? 'is-overdue' : deadline.state === 'due-soon' ? 'is-soon' : 'is-ok'}">`,
          deadline.state === 'overdue'
            ? `Overdue by ${deadline.days} day${deadline.days === 1 ? '' : 's'}`
            : deadline.state === 'due-soon'
              ? `Due ${deadline.days === 0 ? 'today' : 'tomorrow'}`
              : `Due on ${formatDate(complaint.deadline)}`,
          '</p>',
        )

  return html(
    '<article class="card card--hover c-card">',
    '<div class="c-card__body">',
    '<div class="between">',
    `<a class="cell-id" href="${esc(linkBase)}?id=${encodeURIComponent(complaint.id)}">${esc(complaint.id)}</a>`,
    `<div class="row" style="gap:.375rem">${priorityBadge(complaint.priority)}${statusBadge(complaint.status)}</div>`,
    '</div>',
    `<h3 class="c-card__title"><a href="${esc(linkBase)}?id=${encodeURIComponent(complaint.id)}">${esc(complaint.title)}</a></h3>`,
    `<p class="c-card__desc">${esc(truncate(complaint.description, 120))}</p>`,
    '<div class="c-card__meta">',
    `<div>${icon('building', 'icon-sm')}<span class="truncate">${esc(complaint.department)}</span></div>`,
    `<div>${icon('calendar', 'icon-sm')}<span>${esc(formatDate(complaint.submittedAt))}</span></div>`,
    `<div>${icon('map-pin', 'icon-sm')}<span class="truncate">${esc(complaint.location?.address ?? '—')}</span></div>`,
    showUser
      ? `<div>${icon('user', 'icon-sm')}<span class="truncate">${esc(complaint.submittedBy?.name ?? '—')}</span></div>`
      : '',
    '</div>',
    deadlineNote,
    '</div>',
    footer && `<div class="c-card__foot">${footer}</div>`,
    '</article>',
  )
}
