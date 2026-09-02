/**
 * Search and filter strip shown above every complaint table.
 *
 * The page owns the filter state; this module only draws the controls and
 * reports changes back through one callback.
 */

import { esc, icon, on, qs, qsa } from './dom.js'

/**
 * @param {object} options
 * @param {object} options.filters   current values, e.g. { search, status, … }
 * @param {Array}  options.fields    [{ name, label, options: string[] }]
 * @param {boolean} [options.showDates]
 * @param {string} [options.placeholder]
 */
export function filterPanel({
  filters = {},
  fields = [],
  showDates = true,
  placeholder = 'Search by ID, title or description…',
}) {
  // Only the controls this panel actually draws can count as an applied
  // filter. Deriving the list from `fields`/`showDates` keeps sorting, paging
  // and any other state the page happens to carry in `filters` out of the
  // tally -- an allow-list, so new bookkeeping keys can never inflate it.
  const countedKeys = [
    ...fields.map((field) => field.name),
    ...(showDates ? ['dateFrom', 'dateTo'] : []),
  ]

  // A dropdown left on its "All ..." option has an empty value, and an
  // untouched date input is an empty string, so both fall out here.
  const active = countedKeys.filter((key) => {
    const value = filters[key]
    return typeof value === 'string' ? value.trim() !== '' : Boolean(value)
  }).length

  const selects = fields
    .map(
      (field) => `
        <div>
          <label class="field__label" for="filter-${esc(field.name)}">${esc(field.label)}</label>
          <select class="field__control" id="filter-${esc(field.name)}" data-filter="${esc(field.name)}">
            <option value="">All ${esc(field.label.toLowerCase())}</option>
            ${field.options
              .map(
                (option) =>
                  `<option value="${esc(option)}" ${filters[field.name] === option ? 'selected' : ''}>${esc(option)}</option>`,
              )
              .join('')}
          </select>
        </div>`,
    )
    .join('')

  const dates = showDates
    ? `
      <div>
        <label class="field__label" for="filter-dateFrom">From date</label>
        <input type="date" class="field__control" id="filter-dateFrom" data-filter="dateFrom"
               value="${esc(filters.dateFrom ?? '')}" ${filters.dateTo ? `max="${esc(filters.dateTo)}"` : ''}>
      </div>
      <div>
        <label class="field__label" for="filter-dateTo">To date</label>
        <input type="date" class="field__control" id="filter-dateTo" data-filter="dateTo"
               value="${esc(filters.dateTo ?? '')}" ${filters.dateFrom ? `min="${esc(filters.dateFrom)}"` : ''}>
      </div>`
    : ''

  return `
    <div class="filters" data-filter-panel>
      <div class="filters__top">
        <div class="search">
          <label class="sr-only" for="filter-search">Search complaints</label>
          <span class="icon-left">${icon('search', 'icon-sm')}</span>
          <input type="search" class="field__control" id="filter-search" data-filter="search"
                 value="${esc(filters.search ?? '')}" placeholder="${esc(placeholder)}">
          ${
            filters.search
              ? `<button type="button" class="btn-icon search__clear" data-clear-search aria-label="Clear search">${icon('x', 'icon-sm')}</button>`
              : ''
          }
        </div>

        ${
          active
            ? `<button type="button" class="btn btn--ghost btn--sm" data-reset-filters>${icon('x', 'icon-sm')}Clear filters</button>`
            : ''
        }
      </div>

      <div class="filters__grid">${selects}${dates}</div>

      ${
        active
          ? `<p class="muted" style="margin-top:var(--sp-3);display:flex;align-items:center;gap:.375rem">
               ${icon('filter', 'icon-sm')}${active} filter${active > 1 ? 's' : ''} applied
             </p>`
          : ''
      }
    </div>`
}

/**
 * Wire the controls up.
 * `onChange` receives the complete new filter object.
 *
 * The search box is debounced so the list is not re-filtered on every keystroke.
 */
export function activateFilters(scope, filters, onChange) {
  const panel = typeof scope === 'string' ? qs(scope) : scope
  if (!panel) return

  let timer = null

  qsa('[data-filter]', panel).forEach((control) => {
    const name = control.dataset.filter
    const event = control.type === 'search' || control.type === 'text' ? 'input' : 'change'

    control.addEventListener(event, () => {
      const value = control.value
      if (event === 'input') {
        clearTimeout(timer)
        timer = setTimeout(() => onChange({ ...filters, [name]: value, page: 1 }), 350)
      } else {
        onChange({ ...filters, [name]: value, page: 1 })
      }
    })
  })

  on(panel, 'click', '[data-clear-search]', () => onChange({ ...filters, search: '', page: 1 }))

  /* Reset every filter control back to its empty default while leaving the
     search box, sorting and page size alone. Blanking the keys in place --
     rather than dropping them -- keeps the filter object the same shape it
     started with, so later spreads and the query-string sync still see every
     field. */
  on(panel, 'click', '[data-reset-filters]', () => {
    const cleared = { ...filters }
    qsa('[data-filter]', panel).forEach((control) => {
      if (control.dataset.filter !== 'search') cleared[control.dataset.filter] = ''
    })
    onChange({ ...cleared, page: 1 })
  })
}

/**
 * Keep the caret where it was after a re-render.
 * Without this the search box would lose focus on every keystroke.
 */
export function restoreSearchFocus(panel, hadFocus, caret) {
  if (!hadFocus) return
  const input = qs('[data-filter="search"]', panel)
  if (!input) return
  input.focus()
  input.setSelectionRange(caret, caret)
}
