/**
 * Notification service.
 *
 *   GET    /api/notifications              ?unreadOnly= &type=
 *   GET    /api/notifications/unread-count
 *   PUT    /api/notifications/read-all
 *   PUT    /api/notifications/:id/read     /unread
 *   DELETE /api/notifications/:id
 *
 * The feed is stored in MongoDB and scoped to the signed-in user by the
 * server, so the `userId` arguments the pages still pass are accepted for
 * signature compatibility and ignored.
 */

import { request } from './mockApi.js'

export async function getNotifications(userId, { unreadOnly = false, type = '' } = {}) {
  return request('/notifications', { query: { unreadOnly, type } })
}

export async function getUnreadCount(userId) {
  const result = await request('/notifications/unread-count')
  return result.count
}

export async function markAsRead(id) {
  return request(`/notifications/${encodeURIComponent(id)}/read`, { method: 'PUT', body: {} })
}

export async function markAllAsRead(userId) {
  return request('/notifications/read-all', { method: 'PUT', body: {} })
}

export async function markAsUnread(id) {
  return request(`/notifications/${encodeURIComponent(id)}/unread`, { method: 'PUT', body: {} })
}

export async function deleteNotification(id) {
  return request(`/notifications/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

/**
 * Notifications are now raised by the server whenever a complaint event
 * happens (submitted, assigned, status changed, resolved, escalated), so the
 * client no longer creates them.
 *
 * Kept as a no-op because `newComplaint.js` still calls it after submitting;
 * the real notification has already been created by `POST /api/complaints`.
 */
export async function pushNotification() {
  return null
}
