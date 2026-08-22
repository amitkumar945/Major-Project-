/**
 * Department management - add, edit and remove departments, and see how much
 * work each one is carrying.
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
import { errorState, loadingState, progressBar, statCard } from '../components/ui.js'
import { confirmDialog, openModal } from '../components/modal.js'
import { toast } from '../components/toast.js'
import {
  createDepartment,
  deleteDepartment,
  getDepartments,
  updateDepartment,
} from '../services/departmentService.js'
import { ROLES } from '../utils/constants.js'
import { isValid, validateDepartment } from '../utils/validators.js'

let departments = []

function card(department) {
  return `
    <article class="card" data-code="${esc(department.code)}">
      <header class="card__head">
        <div class="grow" style="min-width:0">
          <h3 class="card__title truncate">${esc(department.name)}</h3>
          <p class="card__subtitle">${esc(department.english)}</p>
        </div>
        <span class="badge ${department.isActive ? 'badge--resolved' : 'badge--closed'}">
          ${department.isActive ? 'Active' : 'Inactive'}
        </span>
      </header>

      <div class="card__body">
        <p class="muted">${esc(department.description)}</p>

        <dl class="stack-sm" style="margin-top:var(--sp-4);gap:.625rem">
          <div class="row"><dt class="sr-only">Head</dt>${icon('user', 'icon-sm')}
            <dd class="truncate">${esc(department.head)}</dd></div>
          <div class="row"><dt class="sr-only">Email</dt>${icon('mail', 'icon-sm')}
            <dd class="truncate"><a href="mailto:${esc(department.email)}">${esc(department.email)}</a></dd></div>
          <div class="row" style="align-items:flex-start"><dt class="sr-only">Office</dt>${icon('map-pin', 'icon-sm')}
            <dd>${esc(department.office)}</dd></div>
        </dl>

        <div class="grid grid-4" style="margin-top:var(--sp-5);gap:var(--sp-3)">
          <div><p class="muted" style="font-size:var(--fs-xs)">Officers</p>
            <p class="strong tnum">${department.officerCount}</p></div>
          <div><p class="muted" style="font-size:var(--fs-xs)">Total</p>
            <p class="strong tnum">${department.totalComplaints}</p></div>
          <div><p class="muted" style="font-size:var(--fs-xs)">Pending</p>
            <p class="strong tnum" style="color:var(--amber-700)">${department.pendingComplaints}</p></div>
          <div><p class="muted" style="font-size:var(--fs-xs)">Resolved</p>
            <p class="strong tnum" style="color:var(--green-700)">${department.resolvedComplaints}</p></div>
        </div>

        <div style="margin-top:var(--sp-4)">
          ${progressBar({
            value: department.resolutionRate,
            label: 'Resolution rate',
            valueLabel: `${department.resolutionRate}%`,
            tone: department.resolutionRate >= 90 ? 'success' : department.resolutionRate >= 70 ? 'warning' : 'danger',
            small: true,
          })}
        </div>
      </div>

      <footer class="card__foot" style="display:flex;gap:var(--sp-2);justify-content:flex-end">
        <button type="button" class="btn btn--secondary btn--sm" data-edit="${esc(department.code)}">
          ${icon('pencil', 'icon-sm')}Edit
        </button>
        <button type="button" class="btn btn--danger btn--sm" data-delete="${esc(department.code)}">
          ${icon('trash', 'icon-sm')}Delete
        </button>
      </footer>
    </article>`
}

function formFields(department = {}) {
  return `
    <form id="department-form" novalidate class="stack-sm">
      <div class="grid grid-2">
        <div class="field" data-field="name">
          <label class="field__label" for="dep-name">Department name<span class="field__req">*</span></label>
          <input type="text" class="field__control" id="dep-name" name="name"
                 value="${esc(department.name ?? '')}" placeholder="e.g. Nirman Vibhag" required>
        </div>
        <div class="field" data-field="code">
          <label class="field__label" for="dep-code">Short code<span class="field__req">*</span></label>
          <input type="text" class="field__control mono" id="dep-code" name="code"
                 value="${esc(department.code ?? '')}" placeholder="e.g. NIRMAN"
                 ${department.code ? 'readonly' : ''} required>
        </div>
      </div>

      <div class="field" data-field="english">
        <label class="field__label" for="dep-english">English name</label>
        <input type="text" class="field__control" id="dep-english" name="english"
               value="${esc(department.english ?? '')}" placeholder="e.g. Construction & Maintenance">
      </div>

      <div class="field" data-field="description">
        <label class="field__label" for="dep-desc">Scope of work</label>
        <textarea class="field__control" id="dep-desc" name="description" rows="3"
                  placeholder="What kinds of complaint does this department handle?">${esc(department.description ?? '')}</textarea>
      </div>

      <div class="grid grid-2">
        <div class="field" data-field="head">
          <label class="field__label" for="dep-head">Department head<span class="field__req">*</span></label>
          <input type="text" class="field__control" id="dep-head" name="head"
                 value="${esc(department.head ?? '')}" required>
        </div>
        <div class="field" data-field="email">
          <label class="field__label" for="dep-email">Contact email<span class="field__req">*</span></label>
          <input type="email" class="field__control" id="dep-email" name="email"
                 value="${esc(department.email ?? '')}" placeholder="department@dsvv.ac.in" required>
        </div>
      </div>

      <div class="field" data-field="office">
        <label class="field__label" for="dep-office">Office location</label>
        <input type="text" class="field__control" id="dep-office" name="office"
               value="${esc(department.office ?? '')}" placeholder="Building, floor, room">
      </div>
    </form>`
}

function openForm(department = null) {
  const editing = Boolean(department)

  const modal = openModal({
    title: editing ? `Edit ${department.name}` : 'Add a department',
    description: editing
      ? 'Update the department details.'
      : 'Departments receive complaints routed by category and by the AI classifier.',
    size: 'lg',
    body: formFields(department ?? {}),
    footer: `
      <button type="button" class="btn btn--secondary" data-close>Cancel</button>
      <button type="button" class="btn btn--primary" data-save>
        ${icon('check', 'icon-sm')}${editing ? 'Save changes' : 'Add department'}
      </button>`,
  })

  on(modal.element, 'click', '[data-save]', async (event, button) => {
    const form = qs('#department-form', modal.element)
    const values = formValues(form)

    clearErrors(form)
    const errors = validateDepartment(values)
    if (!isValid(errors)) {
      showErrors(form, errors)
      return
    }

    setLoading(button, true, 'Saving…')
    try {
      if (editing) {
        await updateDepartment(department.code, values)
        toast.success(`${values.name} has been updated.`)
      } else {
        await createDepartment(values)
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

async function load() {
  mount('#area', loadingState('Loading departments…'))

  try {
    departments = await getDepartments()

    const totals = departments.reduce(
      (acc, department) => ({
        complaints: acc.complaints + department.totalComplaints,
        officers: acc.officers + department.officerCount,
        pending: acc.pending + department.pendingComplaints,
      }),
      { complaints: 0, officers: 0, pending: 0 },
    )

    qs('#area').innerHTML = `
      <div class="stack">
        <div class="grid grid-4">
          ${statCard({ label: 'Departments', value: departments.length, icon: 'building' })}
          ${statCard({ label: 'Officers', value: totals.officers, icon: 'user-cog', tone: 'info' })}
          ${statCard({ label: 'Total complaints', value: totals.complaints, icon: 'clipboard-list', tone: 'purple' })}
          ${statCard({ label: 'Currently pending', value: totals.pending, icon: 'clock', tone: 'warning' })}
        </div>
        <div class="grid grid-2">${departments.map(card).join('')}</div>
      </div>`
  } catch (error) {
    mount('#area', errorState({ message: error.message, retryId: 'retry' }))
    qs('#retry')?.addEventListener('click', load)
  }
}

ready(() => {
  const user = requireRole(ROLES.ADMIN)
  if (!user) return

  renderShell(user, { title: 'Departments' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'Department management',
      lead: 'The four departments that receive and resolve campus grievances.',
      crumbs: [{ label: 'Dashboard', href: '/admin/dashboard.html' }, { label: 'Departments' }],
      actions: `<button type="button" class="btn btn--primary" data-add>${icon('plus', 'icon-sm')}Add department</button>`,
    })}
    <div id="area"></div>`

  load()

  on('#root', 'click', '[data-add]', () => openForm())

  on('#area', 'click', '[data-edit]', (event, button) => {
    const department = departments.find((item) => item.code === button.dataset.edit)
    if (department) openForm(department)
  })

  on('#area', 'click', '[data-delete]', async (event, button) => {
    const department = departments.find((item) => item.code === button.dataset.delete)
    if (!department) return

    const confirmed = await confirmDialog({
      title: `Delete ${department.name}?`,
      message: 'This cannot be undone. Departments that still have complaints cannot be deleted.',
      confirmLabel: 'Delete department',
      tone: 'danger',
    })
    if (!confirmed) return

    try {
      await deleteDepartment(department.code)
      toast.success(`${department.name} has been deleted.`)
      load()
    } catch (error) {
      toast.error(error.message, 'Cannot delete this department')
    }
  })
})
