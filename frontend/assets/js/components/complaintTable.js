/**
 * The complaint table used by the student, officer and admin screens.
 *
 * Which columns appear is decided by the `columns` option, so one component
 * serves all three roles instead of three near-identical tables.
 *
 * Below 1024px the table is replaced by a stack of complaint cards, so nothing
 * has to be scrolled sideways on a phone.
 */

import { esc, html, icon } from './dom.js'
import { complaintCard, emptyState, priorityBadge, skeletonTable, statusBadge } from './ui.js'
import { formatDate, getDeadlineState, truncate } from '../utils/helpers.js'

/** Every column the table knows how to render. */
const COLUMNS = {
  id: {
    label: 'Complaint ID',
    sortKey: 'id',
    cell: (complaint, { detailsHref }) =>
      `<a class="cell-id" href="${esc(detailsHref)}?id=${encodeURIComponent(complaint.id)}">${esc(complaint.id)}</a>`,
  },

  title: {
    label: 'Title',
    sortKey: 'title',
    cell: (complaint, { detailsHref }) => html(
      `<a href="${esc(detailsHref)}?id=${encodeURIComponent(complaint.id)}">`,
      `<span class="strong">${esc(truncate(complaint.title, 60))}</span>`,
      `<span class="cell-sub">${esc(complaint.category)}</span>`,
      '</a>',
    ),
  },

  user: {
    // Not sortable: the value is an object and sorting complainants is not
    // something the screens need.
    label: 'Raised By',
    cell: (complaint) => html(
      `<span class="strong">${esc(complaint.submittedBy?.name ?? '—')}</span>`,
      `<span class="cell-sub">${esc(complaint.submittedBy?.userId ?? '')}</span>`,
    ),
  },

  department: {
    label: 'Department',
    sortKey: 'department',
    cell: (complaint) => `<span class="nowrap">${esc(complaint.department)}</span>`,
  },

  category: {
    label: 'Category',
    sortKey: 'category',
    cell: (complaint) => esc(complaint.category),
  },

  officer: {
    label: 'Assigned Officer',
    cell: (complaint) =>
      complaint.assignedOfficer
        ? html(
            `<span class="strong">${esc(complaint.assignedOfficer.name)}</span>`,
            `<span class="cell-sub">${esc(complaint.assignedOfficer.designation)}</span>`,
          )
        : '<span class="faint" style="font-style:italic">Not assigned</span>',
  },

  priority: {
    label: 'Priority',
    sortKey: 'priority',
    cell: (complaint) => priorityBadge(complaint.priority),
  },

  status: {
    label: 'Status',
    sortKey: 'status',
    cell: (complaint) => statusBadge(complaint.status),
  },

  submittedAt: {
    label: 'Submitted',
    sortKey: 'submittedAt',
    cell: (complaint) => `<span class="nowrap">${esc(formatDate(complaint.submittedAt))}</span>`,
  },

  updatedAt: {
    label: 'Last Updated',
    sortKey: 'updatedAt',
    cell: (complaint) => `<span class="nowrap">${esc(formatDate(complaint.updatedAt))}</span>`,
  },

  deadline: {
    label: 'Deadline',
    sortKey: 'deadline',
    cell: (complaint) => {
      const state = getDeadlineState(complaint)
      const tone =
        state.state === 'overdue' ? 'is-overdue' : state.state === 'due-soon' ? 'is-soon' : ''
      return `<span class="nowrap ${tone ? `deadline-note ${tone}` : ''}" style="display:inline-block;margin:0">
                ${esc(formatDate(complaint.deadline))}${state.state === 'overdue' ? ` (+${state.days}d)` : ''}
              </span>`
    },
  },

  location: {
    label: 'Location',
    cell: (complaint) => `<span class="muted">${esc(truncate(complaint.location?.address, 40))}</span>`,
  },
}

/** Column header, with a sort button where the column supports it. */
function headerCell(key, { sortBy, sortDir, sortable }) {
  const column = COLUMNS[key]
  if (!column.sortKey || !sortable) return `<th scope="col">${esc(column.label)}</th>`

  const active = sortBy === column.sortKey
  const ariaSort = active ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'
  const glyph = active ? (sortDir === 'asc' ? 'arrow-up' : 'arrow-down') : 'sort'

  return `<th scope="col" aria-sort="${ariaSort}">
            <button type="button" class="th-sort" data-sort="${esc(column.sortKey)}" aria-sort="${ariaSort}">
              ${esc(column.label)}${icon(glyph, 'icon-sm')}
            </button>
          </th>`
}

/**
 * Render the table.
 *
 * @param {object} options
 * @param {Array}  options.complaints
 * @param {string[]} [options.columns]
 * @param {string} options.detailsHref     page that shows one complaint
 * @param {boolean} [options.loading]
 * @param {string} [options.sortBy]
 * @param {'asc'|'desc'} [options.sortDir]
 * @param {Function} [options.actions]     complaint => HTML for the action cell
 * @param {string} [options.emptyTitle]
 * @param {string} [options.emptyMessage]
 * @param {string} [options.emptyAction]   HTML for a button in the empty state
 * @param {boolean} [options.showUserOnCard]
 */
export function complaintTable({
  complaints = [],
  columns = ['id', 'title', 'department', 'priority', 'status', 'submittedAt', 'updatedAt'],
  detailsHref,
  loading = false,
  sortBy = 'submittedAt',
  sortDir = 'desc',
  sortable = true,
  actions = null,
  emptyTitle = 'No complaints found',
  emptyMessage = 'Try changing the filters, or register a new complaint.',
  emptyAction = '',
  showUserOnCard = false,
}) {
  if (loading) return skeletonTable(6, columns.length)

  if (!complaints.length) {
    return emptyState({
      icon: 'file-search',
      title: emptyTitle,
      message: emptyMessage,
      action: emptyAction,
    })
  }

  const head = html(
    columns.map((key) => headerCell(key, { sortBy, sortDir, sortable })).join(''),
    actions ? '<th scope="col" class="right">Action</th>' : '',
  )

  const body = complaints
    .map((complaint) => html(
      '<tr>',
      columns.map((key) => `<td>${COLUMNS[key].cell(complaint, { detailsHref })}</td>`).join(''),
      actions ? `<td><div class="cell-actions">${actions(complaint)}</div></td>` : '',
      '</tr>',
    ))
    .join('')

  const cards = complaints
    .map((complaint) =>
      complaintCard(complaint, {
        linkBase: detailsHref,
        showUser: showUserOnCard,
        footer: actions
          ? actions(complaint)
          : `<a class="btn btn--ghost btn--sm" href="${esc(detailsHref)}?id=${encodeURIComponent(complaint.id)}">
               ${icon('eye', 'icon-sm')}View details
             </a>`,
      }),
    )
    .join('')

  return html(
    '<div class="desktop-table table-wrap scroll-slim">',
    `<table class="table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`,
    '</div>',
    `<div class="mobile-cards">${cards}</div>`,
  )
}

export { COLUMNS }
