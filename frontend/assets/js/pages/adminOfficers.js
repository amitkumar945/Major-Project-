/**
 * Officer management - directory, workload, performance, and the add/edit and
 * activate/deactivate actions.
 */

import {
  clearErrors,
  esc,
  formValues,
  icon,
  mount,
  on,
  qs,
  ready,
  setLoading,
  showErrors,
} from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { avatar, errorState, loadingState, progressBar, statCard } from '../components/ui.js'
import { confirmDialog, openModal } from '../components/modal.js'
import { toast } from '../components/toast.js'
import { activateFilters, filterPanel } from '../components/filters.js'
import {
  createOfficer,
  getOfficers,
  toggleOfficerStatus,
  updateOfficer,
} from '../services/officerService.js'
import { DEPARTMENT_NAMES, ROLES } from '../utils/constants.js'
import { isValid, validateOfficer } from '../utils/validators.js'

let officers = []
let filters = { search: '', department: '' }

function card(officer, busiest) {
  const load = officer.workload.active

  return `
    <article class="card" data-id="${esc(officer.id)}">
      <div class="card__body">
        <div class="row" style="gap:.875rem;align-items:flex-start">
          ${avatar(officer.name, officer.avatarColor, 'md')}
          <div class="grow" style="min-width:0">
            <p class="strong truncate">${esc(officer.name)}</p>
            <p class="muted truncate" style="font-size:var(--fs-xs)">${esc(officer.designation)}</p>
          </div>
          <span class="badge ${officer.isActive ? 'badge--resolved' : 'badge--closed'}">
            ${officer.isActive ? 'Active' : 'Inactive'}
          </span>
        </div>

        <dl class="stack-sm" style="margin-top:var(--sp-4);gap:.5rem">
          <div class="row"><dt class="sr-only">Department</dt>${icon('building', 'icon-sm')}
            <dd class="truncate">${esc(officer.department)}</dd></div>
          <div class="row"><dt class="sr-only">Email</dt>${icon('mail', 'icon-sm')}
            <dd class="truncate"><a href="mailto:${esc(officer.email)}">${esc(officer.email)}</a></dd></div>
          <div class="row"><dt class="sr-only">Employee ID</dt>${icon('id-card', 'icon-sm')}
            <dd>${esc(officer.employeeId)}</dd></div>
        </dl>

        <div style="margin-top:var(--sp-4)">
          ${progressBar({
            value: load,
            max: busiest || 1,
            label: 'Active workload',
            valueLabel: `${load} complaint${load === 1 ? '' : 's'}`,
            tone: load > busiest * 0.7 ? 'danger' : load > busiest * 0.4 ? 'warning' : 'success',
            small: true,
          })}
        </div>

        <div class="grid grid-3" style="margin-top:var(--sp-4);gap:var(--sp-3)">
          <div><p class="muted" style="font-size:var(--fs-xs)">Resolved</p>
            <p class="strong tnum">${officer.workload.resolvedTotal}</p></div>
          <div><p class="muted" style="font-size:var(--fs-xs)">Avg. days</p>
            <p class="strong tnum">${officer.workload.avgResolutionDays}</p></div>
          <div><p class="muted" style="font-size:var(--fs-xs)">Rating</p>
            <p class="strong tnum">${officer.workload.rating}</p></div>
        </div>
      </div>

      <footer class="card__foot" style="display:flex;gap:var(--sp-2);justify-content:flex-end">
        <button type="button" class="btn btn--secondary btn--sm" data-edit="${esc(officer.id)}">
          ${icon('pencil', 'icon-sm')}Edit
        </button>
        <button type="button" class="btn ${officer.isActive ? 'btn--danger' : 'btn--success'} btn--sm"
                data-toggle="${esc(officer.id)}">
          ${icon(officer.isActive ? 'x-circle' : 'check-circle', 'icon-sm')}
          ${officer.isActive ? 'Deactivate' : 'Activate'}
        </button>
      </footer>
    </article>`
}

function formFields(officer = {}) {
  return `
    <form id="officer-form" novalidate class="stack-sm">
      <div class="grid grid-2">
        <div class="field" data-field="name">
          <label class="field__label" for="off-name">Full name<span class="field__req">*</span></label>
          <input type="text" class="field__control" id="off-name" name="name"
                 value="${esc(officer.name ?? '')}" required>
        </div>
        <div class="field" data-field="employeeId">
          <label class="field__label" for="off-id">Employee ID<span class="field__req">*</span></label>
          <input type="text" class="field__control" id="off-id" name="employeeId"
                 value="${esc(officer.employeeId ?? '')}" placeholder="DSVV/NIR/114" required>
        </div>
      </div>

      <div class="field" data-field="email">
        <label class="field__label" for="off-email">Email address<span class="field__req">*</span></label>
        <input type="email" class="field__control" id="off-email" name="email"
               value="${esc(officer.email ?? '')}" placeholder="name@dsvv.ac.in" required>
      </div>

      <div class="grid grid-2">
        <div class="field" data-field="department">
          <label class="field__label" for="off-dep">Department<span class="field__req">*</span></label>
          <select class="field__control" id="off-dep" name="department" required>
            <option value="">Select a department</option>
            ${DEPARTMENT_NAMES.map(
              (name) =>
                `<option value="${esc(name)}" ${officer.department === name ? 'selected' : ''}>${esc(name)}</option>`,
            ).join('')}
          </select>
        </div>
        <div class="field" data-field="designation">
          <label class="field__label" for="off-desig">Designation<span class="field__req">*</span></label>
          <input type="text" class="field__control" id="off-desig" name="designation"
                 value="${esc(officer.designation ?? '')}" placeholder="e.g. Electrical Maintenance Officer" required>
        </div>
      </div>
    </form>`
}

function openForm(officer = null) {
  const editing = Boolean(officer)

  const modal = openModal({
    title: editing ? `Edit ${officer.name}` : 'Add an officer',
    description: editing
      ? 'Update this officer’s details or move them to another department.'
      : 'New officers can be assigned complaints as soon as they are added.',
    size: 'lg',
    body: formFields(officer ?? {}),
    footer: `
      <button type="button" class="btn btn--secondary" data-close>Cancel</button>
      <button type="button" class="btn btn--primary" data-save>
        ${icon('check', 'icon-sm')}${editing ? 'Save changes' : 'Add officer'}
      </button>`,
  })

  on(modal.element, 'click', '[data-save]', async (event, button) => {
    const form = qs('#officer-form', modal.element)
    const values = formValues(form)

    clearErrors(form)
    const errors = validateOfficer(values)
    if (!isValid(errors)) {
      showErrors(form, errors)
      return
    }

    setLoading(button, true, 'Saving…')
    try {
      if (editing) {
        await updateOfficer(officer.id, values)
        toast.success(`${values.name} has been updated.`)
      } else {
        await createOfficer(values)
        toast.success(`${values.name} has been added.`)
      }
      modal.close()
      load()
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message)
    }
  })
}

function render() {
  const busiest = Math.max(...officers.map((officer) => officer.workload.active), 1)
  const active = officers.filter((officer) => officer.isActive)
  const totalActive = active.reduce((sum, officer) => sum + officer.workload.active, 0)

  const searchInput = qs('[data-filter="search"]')
  const hadFocus = document.activeElement === searchInput
  const caret = searchInput?.selectionStart ?? 0

  qs('#area').innerHTML = `
    <div class="stack">
      <div class="grid grid-4">
        ${statCard({ label: 'Officers', value: officers.length, icon: 'user-cog' })}
        ${statCard({ label: 'Active', value: active.length, icon: 'user-check', tone: 'success' })}
        ${statCard({ label: 'Active complaints', value: totalActive, icon: 'clipboard-list', tone: 'warning' })}
        ${statCard({
          label: 'Busiest officer',
          value: busiest,
          icon: 'trending-up',
          tone: 'danger',
          hint: officers.find((officer) => officer.workload.active === busiest)?.name ?? '',
        })}
      </div>

      <section class="card">
        ${filterPanel({
          filters,
          fields: [{ name: 'department', label: 'Department', options: DEPARTMENT_NAMES }],
          showDates: false,
          placeholder: 'Search by name, ID, email or designation…',
        })}
        <div class="card__body">
          ${
            officers.length
              ? `<div class="grid grid-2">${officers.map((officer) => card(officer, busiest)).join('')}</div>`
              : `<div class="state"><span class="state__icon">${icon('user-cog', 'icon-xl')}</span>
                   <p class="state__title">No officers found</p>
                   <p class="state__text">Try clearing the filters, or add a new officer.</p></div>`
          }
        </div>
      </section>
    </div>`

  activateFilters(qs('#area'), filters, (next) => {
    filters = next
    load()
  })

  if (hadFocus) {
    const input = qs('[data-filter="search"]')
    input?.focus()
    input?.setSelectionRange(caret, caret)
  }
}

async function load() {
  if (!qs('#area').innerHTML) mount('#area', loadingState('Loading officers…'))

  try {
    officers = await getOfficers(filters)
    render()
  } catch (error) {
    mount('#area', errorState({ message: error.message, retryId: 'retry' }))
    qs('#retry')?.addEventListener('click', load)
  }
}

ready(() => {
  const user = requireRole(ROLES.ADMIN)
  if (!user) return

  renderShell(user, { title: 'Officers' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'Officer management',
      lead: 'Workload, performance and account status for every department officer.',
      crumbs: [{ label: 'Dashboard', href: '/admin/dashboard.html' }, { label: 'Officers' }],
      actions: `<button type="button" class="btn btn--primary" data-add>${icon('user-plus', 'icon-sm')}Add officer</button>`,
    })}
    <div id="area"></div>`

  load()

  on('#root', 'click', '[data-add]', () => openForm())

  on('#area', 'click', '[data-edit]', (event, button) => {
    const officer = officers.find((item) => item.id === button.dataset.edit)
    if (officer) openForm(officer)
  })

  on('#area', 'click', '[data-toggle]', async (event, button) => {
    const officer = officers.find((item) => item.id === button.dataset.toggle)
    if (!officer) return

    const confirmed = await confirmDialog({
      title: officer.isActive ? `Deactivate ${officer.name}?` : `Activate ${officer.name}?`,
      message: officer.isActive
        ? 'A deactivated officer cannot be assigned new complaints. Officers with active complaints must be reassigned first.'
        : 'This officer will be able to receive complaints again.',
      confirmLabel: officer.isActive ? 'Deactivate' : 'Activate',
      tone: officer.isActive ? 'danger' : 'success',
    })
    if (!confirmed) return

    try {
      await toggleOfficerStatus(officer.id)
      toast.success(`${officer.name} is now ${officer.isActive ? 'inactive' : 'active'}.`)
      load()
    } catch (error) {
      toast.error(error.message, 'Cannot change this account')
    }
  })
})
