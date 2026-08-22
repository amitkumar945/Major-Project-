/**
 * One row in the notification feed.
 *
 * The icon and colour for each notification type are decided here, so the
 * notification page and any future dropdown look the same.
 */

import { esc, html, icon } from './dom.js'
import { NOTIFICATION_TYPES } from '../utils/constants.js'
import { timeAgo } from '../utils/helpers.js'

const TYPES = {
  [NOTIFICATION_TYPES.SUBMITTED]: { glyph: 'file-plus', tone: 'brand' },
  [NOTIFICATION_TYPES.ASSIGNED]: { glyph: 'user-check', tone: 'sky' },
  [NOTIFICATION_TYPES.OFFICER_ASSIGNED]: { glyph: 'user-check', tone: 'sky' },
  [NOTIFICATION_TYPES.STATUS_CHANGED]: { glyph: 'refresh', tone: 'amber' },
  [NOTIFICATION_TYPES.RESOLUTION_SUBMITTED]: { glyph: 'file-check', tone: 'green' },
  [NOTIFICATION_TYPES.RESOLVED]: { glyph: 'check-circle', tone: 'green' },
  [NOTIFICATION_TYPES.DEADLINE_APPROACHING]: { glyph: 'clock', tone: 'amber' },
  [NOTIFICATION_TYPES.ESCALATED]: { glyph: 'alert-octagon', tone: 'red' },
  [NOTIFICATION_TYPES.FEEDBACK_REQUESTED]: { glyph: 'message-heart', tone: 'purple' },
}

export function notificationItem(notification, { detailsHref }) {
  const look = TYPES[notification.type] ?? { glyph: 'bell', tone: '' }

  return html(
    `<article class="notif ${notification.read ? '' : 'is-unread'}" data-id="${esc(notification.id)}">`,
    `<span class="notif__icon ${look.tone ? `notif__icon--${look.tone}` : ''}">${icon(look.glyph, 'icon-md')}</span>`,
    '<div class="grow" style="min-width:0">',
    '<div class="between" style="align-items:flex-start">',
    `<h3 class="notif__title">${esc(notification.title)}${
      notification.read ? '' : '<span class="notif__unread-dot" aria-label="Unread"></span>'
    }</h3>`,
    `<time class="muted nowrap" datetime="${esc(notification.createdAt)}">${esc(timeAgo(notification.createdAt))}</time>`,
    '</div>',
    `<p class="notif__msg">${esc(notification.message)}</p>`,
    '<div class="notif__acts">',
    notification.complaintId
      ? `<a href="${esc(detailsHref)}?id=${encodeURIComponent(notification.complaintId)}" class="strong" style="color:var(--brand-600)">View ${esc(notification.complaintId)}</a>`
      : '',
    notification.read ? '' : '<button type="button" data-mark-read>Mark as read</button>',
    '<button type="button" data-delete>Delete</button>',
    '</div></div></article>',
  )
}

export default notificationItem
