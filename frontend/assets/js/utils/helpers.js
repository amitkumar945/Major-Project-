/**
 * Small pure helper functions shared across the application.
 * Keeping them here avoids re-writing the same date/format logic on every page.
 */

import {
  ESCALATION_LEVELS,
  PRIORITY_SLA_DAYS,
  STATUS,
  UNIVERSITY_SHORT,
} from './constants.js'

/* --------------------------------------------------------------- classes */

/**
 * Join conditional Tailwind class names.
 * cn('p-2', isActive && 'bg-blue-50', null) -> 'p-2 bg-blue-50'
 */
export function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

/* ----------------------------------------------------------------- dates */

const MS_PER_DAY = 24 * 60 * 60 * 1000

/** '2026-02-14T09:30:00Z' -> '14 Feb 2026' */
export function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

/** '2026-02-14T09:30:00Z' -> '14 Feb 2026, 03:00 PM' */
export function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return `${formatDate(date)}, ${date.toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
  })}`
}

/** Human friendly "time ago" label used by the notification list. */
export function timeAgo(value) {
  if (!value) return ''
  const diffMs = Date.now() - new Date(value).getTime()
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} day${days > 1 ? 's' : ''} ago`
  return formatDate(value)
}

/** Whole days between two dates (b - a). Negative means `b` is in the past. */
export function daysBetween(a, b) {
  const start = new Date(a).setHours(0, 0, 0, 0)
  const end = new Date(b).setHours(0, 0, 0, 0)
  return Math.round((end - start) / MS_PER_DAY)
}

/** Days remaining until a deadline. Negative when the deadline has passed. */
export function daysUntil(deadline) {
  return daysBetween(new Date(), deadline)
}

/** Add `days` to a date and return an ISO string. */
export function addDays(date, days) {
  const result = new Date(date)
  result.setDate(result.getDate() + days)
  return result.toISOString()
}

/** Deadline derived from the submission date and the priority SLA. */
export function calculateDeadline(submittedAt, priority) {
  return addDays(submittedAt, PRIORITY_SLA_DAYS[priority] ?? 7)
}

/**
 * Deadline state used by badges and warning banners on the details screen.
 * Returns one of: 'met' | 'overdue' | 'due-soon' | 'on-track'.
 */
export function getDeadlineState(complaint) {
  if (!complaint?.deadline) return { state: 'on-track', days: 0 }
  const closed = [STATUS.RESOLVED, STATUS.CLOSED].includes(complaint.status)
  const days = daysUntil(complaint.deadline)
  if (closed) return { state: 'met', days }
  if (days < 0) return { state: 'overdue', days: Math.abs(days) }
  if (days <= 1) return { state: 'due-soon', days }
  return { state: 'on-track', days }
}

/** Escalation level implied by how many days a complaint is overdue. */
export function escalationLevelForOverdue(daysOverdue) {
  let level = 1
  ESCALATION_LEVELS.forEach((rule) => {
    if (daysOverdue >= rule.afterDays) level = rule.level
  })
  return level
}

export function escalationAuthority(level) {
  return (
    ESCALATION_LEVELS.find((rule) => rule.level === level)?.authority ??
    'Department Officer'
  )
}

/* ------------------------------------------------------------------- ids */

/**
 * Build the next complaint reference, e.g. DSVV-GRV-2026-00125.
 * The backend will own this sequence later; here we simply continue from the
 * highest number currently present in the list.
 */
export function generateComplaintId(existingComplaints = []) {
  const year = new Date().getFullYear()
  const prefix = `${UNIVERSITY_SHORT}-GRV-${year}-`
  const highest = existingComplaints.reduce((max, complaint) => {
    if (!complaint.id?.startsWith(prefix)) return max
    const serial = Number.parseInt(complaint.id.slice(prefix.length), 10)
    return Number.isNaN(serial) ? max : Math.max(max, serial)
  }, 0)
  return `${prefix}${String(highest + 1).padStart(5, '0')}`
}

/** Short unique key for client-side list items (files, timeline rows, toasts). */
export function uid(prefix = 'id') {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
}

/* ---------------------------------------------------------------- format */

/** 245367 -> '239.6 KB' */
export function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

/** 'Ravi Sharma' -> 'RS' */
export function getInitials(name = '') {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

/** Trim long descriptions for table cells and cards. */
export function truncate(text = '', length = 90) {
  return text.length > length ? `${text.slice(0, length).trimEnd()}…` : text
}

/** 0.9412 -> '94%' */
export function toPercent(value, digits = 0) {
  return `${(value * 100).toFixed(digits)}%`
}

/** Coordinates formatted for the location panel. */
export function formatCoordinate(value) {
  return typeof value === 'number' ? value.toFixed(6) : '—'
}

/* ------------------------------------------------------------ collections */

/** Count how many times each value of `key` appears in `items`. */
export function countBy(items, key) {
  return items.reduce((acc, item) => {
    const value = typeof key === 'function' ? key(item) : item[key]
    acc[value] = (acc[value] || 0) + 1
    return acc
  }, {})
}

/**
 * Turn a countBy result into the [{ name, value }] shape Recharts expects.
 * `order` keeps categories in a stable, meaningful sequence.
 */
export function toChartData(counts, order) {
  const keys = order ?? Object.keys(counts)
  return keys.map((name) => ({ name, value: counts[name] || 0 }))
}

/** Generic comparator used by sortable tables. */
export function compareValues(a, b, key, direction = 'asc') {
  const first = a[key]
  const second = b[key]
  let result
  if (first == null && second == null) result = 0
  else if (first == null) result = 1
  else if (second == null) result = -1
  else if (typeof first === 'number' && typeof second === 'number')
    result = first - second
  else result = String(first).localeCompare(String(second))
  return direction === 'asc' ? result : -result
}

/** Slice an array for the current page (1-based page numbers). */
export function paginate(items, page, pageSize) {
  const start = (page - 1) * pageSize
  return items.slice(start, start + pageSize)
}

/* ------------------------------------------------------------ localStorage */

/** Read and parse a JSON value, returning `fallback` if anything goes wrong. */
export function readStorage(key, fallback = null) {
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

export function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* Storage can be full or blocked in private mode - ignore silently. */
  }
}

export function removeStorage(key) {
  try {
    window.localStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}
