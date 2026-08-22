/**
 * Pieces of the complaint screens that are shared between the submission form
 * and the details/tracking pages: the map, the evidence gallery, the deadline
 * banner, the officer card and the remarks thread.
 */

import { esc, html, icon } from './dom.js'
import { avatar } from './ui.js'
import {
  formatCoordinate,
  formatDate,
  formatDateTime,
  formatFileSize,
  getDeadlineState,
} from '../utils/helpers.js'

/* ================================================================== MAP === */

/**
 * Map view for a geo-tagged complaint.
 *
 * The markup rendered here is the offline fallback: an inline-SVG campus grid
 * that needs no API key and no network. When a point is present it is also
 * tagged with `data-map`, and `hydrateMaps()` swaps in a real Leaflet /
 * OpenStreetMap view once the library loads. If the CDN is unreachable the SVG
 * simply stays, so the prototype is always demonstrable.
 */
export function mapPreview({ latitude, longitude, address = '', accuracy = 0, tall = false } = {}) {
  const hasPoint = latitude != null && longitude != null

  // Serialised for hydrateMaps(); esc() keeps the attribute safe.
  const mapData = hasPoint
    ? ` data-map="${esc(JSON.stringify({ latitude, longitude, address, accuracy }))}"`
    : ''

  return html(
    `<div class="map ${tall ? 'map--tall' : ''}"${mapData} role="img" aria-label="${
      hasPoint
        ? `Map showing the complaint location at latitude ${esc(latitude)}, longitude ${esc(longitude)}`
        : 'Map preview, no location selected'
    }">`,

    // simulated campus surface: greens, blocks and roads
    `<svg class="map__svg" viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
       <rect width="400" height="240" fill="#eef2f7"/>
       <rect x="18" y="16" width="96" height="62" rx="6" fill="#dcefe0"/>
       <rect x="284" y="150" width="100" height="74" rx="6" fill="#dcefe0"/>
       <rect x="140" y="22" width="70" height="48" rx="4" fill="#e2e8f0"/>
       <rect x="236" y="30" width="58" height="40" rx="4" fill="#e2e8f0"/>
       <rect x="40" y="150" width="86" height="56" rx="4" fill="#e2e8f0"/>
       <rect x="160" y="160" width="64" height="44" rx="4" fill="#e2e8f0"/>
       <rect x="308" y="86" width="66" height="42" rx="4" fill="#e2e8f0"/>
       <path d="M0 100 H400" stroke="#ffffff" stroke-width="14"/>
       <path d="M0 100 H400" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="6 8"/>
       <path d="M132 0 V240" stroke="#ffffff" stroke-width="12"/>
       <path d="M132 0 V240" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="6 8"/>
       <path d="M296 0 V240" stroke="#ffffff" stroke-width="9"/>
       <path d="M0 196 H400" stroke="#ffffff" stroke-width="8"/>
     </svg>`,

    hasPoint
      ? html(
          '<span class="map__accuracy" aria-hidden="true"></span>',
          `<span class="map__pin" aria-hidden="true">${icon('map-pin', 'icon-md')}</span>`,
        )
      : '',

    '<div class="map__strip">',
    hasPoint
      ? html(
          `<p class="strong truncate" style="font-size:var(--fs-xs)">${esc(address || 'Location captured')}</p>`,
          `<p class="map__coords">${esc(formatCoordinate(latitude))}, ${esc(formatCoordinate(longitude))}${
            accuracy ? ` · ±${esc(accuracy)} m` : ''
          }</p>`,
        )
      : '<p class="muted" style="font-size:var(--fs-xs)">No location captured yet.</p>',
    '</div>',

    '<span class="map__tag">Campus map preview</span>',
    '</div>',
  )
}

/**
 * Upgrade every `mapPreview()` placeholder on the page to a live Leaflet map.
 *
 * Call it after the page has been mounted. Placeholders without a captured
 * point, and any that have already been hydrated, are skipped. Leaflet is
 * imported dynamically so pages that never show a map do not pay for it.
 *
 * @param {ParentNode} root  where to look for placeholders
 */
export async function hydrateMaps(root = document) {
  const nodes = [...root.querySelectorAll('[data-map]:not([data-map-ready])')]
  if (!nodes.length) return

  let renderLocationMap
  try {
    ;({ renderLocationMap } = await import('./leafletMap.js'))
  } catch {
    return // keep the SVG fallback
  }

  await Promise.all(
    nodes.map(async (node) => {
      let location
      try {
        location = JSON.parse(node.dataset.map)
      } catch {
        return
      }

      // Marks the node before awaiting, so a second call cannot double-render.
      node.dataset.mapReady = 'true'

      const map = await renderLocationMap(node, location, {
        onFail: () => delete node.dataset.mapReady,
      })

      // renderLocationMap() clears the container, so the SVG fallback is gone
      // on success; on failure the placeholder is left exactly as it was.
      if (!map) delete node.dataset.mapReady
      else node.removeAttribute('role')
    }),
  )
}

/* ============================================================= EVIDENCE === */

const FILE_ICONS = { image: 'image', pdf: 'file-text', doc: 'paperclip' }

/**
 * Read-only view of the files attached to a complaint.
 *
 * Seeded complaints only carry file metadata because there is no file server
 * yet, so a labelled tile stands in for the image. Files chosen during this
 * browser session do have a preview and are shown.
 */
export function evidenceGallery(evidence = []) {
  if (!evidence.length) {
    return html(
      '<div class="state" style="padding:var(--sp-8) var(--sp-4)">',
      `<span class="state__icon">${icon('paperclip', 'icon-xl')}</span>`,
      '<p class="state__title">No evidence attached</p>',
      '<p class="state__text">No photographs or documents were uploaded with this complaint.</p>',
      '</div>',
    )
  }

  const tiles = evidence
    .map((file) => html(
      '<li class="gallery__item">',
      '<div class="gallery__media">',
      file.url
        ? `<img src="${esc(file.url)}" alt="${esc(file.name)}">`
        : html(
            icon(FILE_ICONS[file.kind] ?? 'paperclip', 'icon-xl'),
            `<span class="gallery__kind">${esc(file.kind)}</span>`,
          ),
      '</div>',
      '<div class="gallery__foot">',
      `<p class="truncate" style="font-size:var(--fs-xs);font-weight:500" title="${esc(file.name)}">${esc(file.name)}</p>`,
      `<p class="muted" style="font-size:11px">${esc(formatFileSize(file.size))}</p>`,
      '</div></li>',
    ))
    .join('')

  return `<ul class="gallery">${tiles}</ul>`
}

/* ============================================================= DEADLINE === */

/**
 * Expected-resolution banner.
 * Amber when the deadline is close, red once it has passed - at which point the
 * escalation message is shown.
 */
export function deadlineBanner(complaint) {
  const { state, days } = getDeadlineState(complaint)

  const config = {
    met: {
      tone: 'success',
      glyph: 'check-circle',
      title: 'Resolved within the committed timeline',
      text: `This complaint was closed on ${formatDate(complaint.resolvedAt ?? complaint.updatedAt)}.`,
    },
    overdue: {
      tone: 'danger',
      glyph: 'alert-octagon',
      title: 'Complaint has been escalated',
      text: `The resolution deadline of ${formatDate(complaint.deadline)} was exceeded by ${days} day${
        days === 1 ? '' : 's'
      }. The matter has been raised to ${complaint.escalationAuthority ?? 'the department head'}.`,
    },
    'due-soon': {
      tone: 'warning',
      glyph: 'clock',
      title: days === 0 ? 'Deadline is today' : 'Deadline is approaching',
      text: `This complaint must be resolved by ${formatDate(complaint.deadline)}. The department has been reminded.`,
    },
    'on-track': {
      tone: 'muted',
      glyph: 'calendar-clock',
      title: 'Expected resolution date',
      text: `Work is expected to be completed by ${formatDate(complaint.deadline)} (${days} day${
        days === 1 ? '' : 's'
      } remaining).`,
    },
  }[state]

  return html(
    `<div class="alert alert--${config.tone}">`,
    `<span class="alert__icon">${icon(config.glyph, 'icon-lg')}</span>`,
    '<div class="grow">',
    `<p class="alert__title">${esc(config.title)}</p>`,
    `<p class="alert__text">${esc(config.text)}</p>`,
    '</div></div>',
  )
}

/* ============================================================== OFFICER === */

/** Handling officer panel, with a contact link. */
export function officerCard(officer) {
  if (!officer) {
    return html(
      '<div class="state" style="padding:var(--sp-8) var(--sp-4)">',
      `<span class="state__icon">${icon('user', 'icon-xl')}</span>`,
      '<p class="state__title">Officer not assigned yet</p>',
      '<p class="state__text">The grievance cell will assign a department officer shortly.</p>',
      '</div>',
    )
  }

  return html(
    '<div class="row" style="gap:.875rem">',
    avatar(officer.name, '#4338ca', 'md'),
    '<div class="grow" style="min-width:0">',
    `<p class="strong truncate">${esc(officer.name)}</p>`,
    `<p class="muted truncate">${esc(officer.designation)}</p>`,
    '</div></div>',

    '<dl class="stack-sm" style="margin-top:var(--sp-4);gap:.625rem">',
    `<div class="row"><dt class="sr-only">Department</dt>${icon('building', 'icon-sm')}<dd class="truncate">${esc(officer.department)}</dd></div>`,
    `<div class="row"><dt class="sr-only">Email</dt>${icon('mail', 'icon-sm')}<dd class="truncate"><a href="mailto:${esc(officer.email)}">${esc(officer.email)}</a></dd></div>`,
    `<div class="row"><dt class="sr-only">Employee ID</dt>${icon('id-card', 'icon-sm')}<dd>${esc(officer.employeeId ?? '—')}</dd></div>`,
    '</dl>',

    `<a class="btn btn--secondary btn--sm" style="margin-top:var(--sp-4)" href="mailto:${esc(officer.email)}">
       ${icon('mail', 'icon-sm')}Email officer
     </a>`,
  )
}

/* ============================================================== REMARKS === */

/** Conversation thread of officer and administrator remarks. */
export function remarksThread(remarks = []) {
  if (!remarks.length) {
    return '<p class="muted">No remarks have been recorded on this complaint yet.</p>'
  }

  return remarks
    .map((remark) => html(
      '<article class="remark">',
      avatar(remark.author, '#64748b', 'sm'),
      '<div class="grow" style="min-width:0">',
      '<div class="row-wrap" style="gap:.5rem">',
      `<span class="remark__author">${esc(remark.author)}</span>`,
      `<span class="remark__role">${esc(remark.role)}</span>`,
      `<span class="remark__time" style="margin-left:auto">${esc(formatDateTime(remark.at))}</span>`,
      '</div>',
      `<p class="remark__text">${esc(remark.message)}</p>`,
      '</div></article>',
    ))
    .join('')
}
