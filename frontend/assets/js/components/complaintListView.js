/**
 * The complaint list screen, shared by the student, officer and admin pages.
 *
 * It owns the filter/sort/pagination state, calls the service, and re-renders
 * the table. Each page supplies only what differs: which columns to show, which
 * filters to offer, and which action buttons belong in each row.
 */

import { mount, on, qs, queryParams, setQueryParams } from './dom.js'
import { errorState, pagination } from './ui.js'
import { activateFilters, filterPanel } from './filters.js'
import { complaintTable } from './complaintTable.js'
import { getComplaints } from '../services/complaintService.js'
import {
  CATEGORIES,
  DEPARTMENT_NAMES,
  PRIORITY_LIST,
  STATUS_LIST,
} from '../utils/constants.js'

/** Ready-made filter dropdowns. */
export const FILTER_FIELDS = {
  department: { name: 'department', label: 'Department', options: DEPARTMENT_NAMES },
  status: { name: 'status', label: 'Status', options: STATUS_LIST },
  priority: { name: 'priority', label: 'Priority', options: PRIORITY_LIST },
  category: { name: 'category', label: 'Category', options: CATEGORIES },
}

/**
 * @param {object} config
 * @param {string} config.container      selector for the card that holds the list
 * @param {object} config.scope          { userId } | { officerId } | { department } | {}
 * @param {string[]} config.columns
 * @param {Array} config.fields          filter dropdowns to show
 * @param {string} config.detailsHref
 * @param {Function} [config.actions]    complaint => HTML for the row actions
 * @param {object} [config.emptyState]   { title, message, action }
 * @param {boolean} [config.showUserOnCard]
 * @returns {{ reload: Function, filters: Function }}
 */
export function createComplaintList({
  container,
  scope = {},
  columns,
  fields = [],
  detailsHref,
  actions = null,
  emptyState = {},
  showUserOnCard = false,
  searchPlaceholder,
}) {
  const node = typeof container === 'string' ? qs(container) : container

  // Initial filters come from the query string, so links such as
  // "?status=Resolved" from the dashboard cards land pre-filtered.
  const params = queryParams()
  let filters = {
    search: params.search ?? '',
    department: params.department ?? '',
    status: params.status ?? '',
    priority: params.priority ?? '',
    category: params.category ?? '',
    dateFrom: params.dateFrom ?? '',
    dateTo: params.dateTo ?? '',
    sortBy: params.sortBy ?? 'submittedAt',
    sortDir: params.sortDir ?? 'desc',
    page: Number(params.page ?? 1),
    pageSize: Number(params.pageSize ?? 10),
  }

  let result = { items: [], total: 0, page: 1, totalPages: 1, pageSize: 10 }
  let loading = true
  let failure = null

  function render() {
    // Remember the caret so typing in the search box is not interrupted.
    const searchInput = qs('[data-filter="search"]', node)
    const hadFocus = document.activeElement === searchInput
    const caret = searchInput?.selectionStart ?? 0

    node.innerHTML = failure
      ? errorState({ message: failure, retryId: 'list-retry' })
      : `
        ${filterPanel({ filters, fields, placeholder: searchPlaceholder })}
        <div data-table-area>
          ${complaintTable({
            complaints: result.items,
            columns,
            detailsHref,
            loading,
            sortBy: filters.sortBy,
            sortDir: filters.sortDir,
            actions,
            showUserOnCard,
            emptyTitle: emptyState.title,
            emptyMessage: emptyState.message,
            emptyAction: emptyState.action,
          })}
        </div>
        ${loading ? '' : pagination(result)}`

    if (failure) {
      qs('#list-retry', node)?.addEventListener('click', load)
      return
    }

    activateFilters(node, filters, (next) => {
      filters = next
      load()
    })

    if (hadFocus) {
      const input = qs('[data-filter="search"]', node)
      input?.focus()
      input?.setSelectionRange(caret, caret)
    }
  }

  async function load() {
    loading = true
    failure = null
    render()

    try {
      result = await getComplaints({ ...scope, ...filters })
      filters.page = result.page
      setQueryParams({
        search: filters.search,
        department: filters.department,
        status: filters.status,
        priority: filters.priority,
        category: filters.category,
        dateFrom: filters.dateFrom,
        dateTo: filters.dateTo,
        page: filters.page > 1 ? filters.page : '',
        pageSize: filters.pageSize !== 10 ? filters.pageSize : '',
      })
    } catch (error) {
      failure = error.message
    } finally {
      loading = false
      render()
    }
  }

  /* Sorting, paging and page size are handled by delegation, so they keep
     working after every re-render. */
  on(node, 'click', '[data-sort]', (event, button) => {
    const key = button.dataset.sort
    filters = {
      ...filters,
      sortBy: key,
      sortDir: filters.sortBy === key && filters.sortDir === 'asc' ? 'desc' : 'asc',
      page: 1,
    }
    load()
  })

  on(node, 'click', '[data-page]', (event, button) => {
    const page = Number(button.dataset.page)
    if (page < 1 || page > result.totalPages || page === filters.page) return
    filters = { ...filters, page }
    load()
    node.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })

  on(node, 'change', '[data-page-size]', (event) => {
    filters = { ...filters, pageSize: Number(event.target.value), page: 1 }
    load()
  })

  load()

  return {
    reload: load,
    filters: () => filters,
  }
}
