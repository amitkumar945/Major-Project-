/**
 * Students & staff directory.
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
import { avatar, errorState, loadingState, statCard } from '../components/ui.js'
import { activateFilters, filterPanel } from '../components/filters.js'
import { confirmDialog, openModal } from '../components/modal.js'
import { toast } from '../components/toast.js'
import { createUser, getUsers, getUserSummary, toggleUserStatus } from '../services/userService.js'
import { ROLES } from '../utils/constants.js'
import { isEmail } from '../utils/validators.js'
import { formatDate } from '../utils/helpers.js'

let users = []
let summary = null
let filters = { search: '', userType: '' }

function row(user) {
  return `
    <tr>
      <td>
        <div class="row" style="gap:.625rem">
          ${avatar(user.name, user.avatarColor, 'sm')}
          <div style="min-width:0">
            <span class="strong">${esc(user.name)}</span>
            <span class="cell-sub">${esc(user.userId)}</span>
          </div>
        </div>
      </td>
      <td><span class="badge ${user.userType === 'Student' ? 'badge--review' : 'badge--accepted'}">${esc(user.userType)}</span></td>
      <td>${esc(user.department)}</td>
      <td><span class="truncate" style="display:inline-block;max-width:18rem;word-break:break-all">${esc(user.email)}</span></td>
      <td class="tnum">${user.complaintCount}</td>
      <td class="tnum">${user.activeComplaints}</td>
      <td class="nowrap">${user.lastComplaintAt ? esc(formatDate(user.lastComplaintAt)) : '<span class="faint">—</span>'}</td>
      <td><span class="badge ${user.isActive ? 'badge--resolved' : 'badge--closed'}">${user.isActive ? 'Active' : 'Blocked'}</span></td>
      <td>
        <div class="cell-actions">
          <button type="button" class="btn-icon ${user.isActive ? 'btn-icon--danger' : ''}"
                  data-toggle="${esc(user.id)}"
                  aria-label="${user.isActive ? 'Block' : 'Unblock'} ${esc(user.name)}"
                  title="${user.isActive ? 'Block account' : 'Unblock account'}">
            ${icon(user.isActive ? 'x-circle' : 'check-circle', 'icon-md')}
          </button>
        </div>
      </td>
    </tr>`
}

function mobileCard(user) {
  return `
    <article class="card" style="padding:var(--sp-4)">
      <div class="row" style="gap:.75rem">
        ${avatar(user.name, user.avatarColor, 'sm')}
        <div class="grow" style="min-width:0">
          <p class="strong truncate">${esc(user.name)}</p>
          <p class="muted truncate" style="font-size:var(--fs-xs)">${esc(user.userId)} · ${esc(user.userType)}</p>
        </div>
        <span class="badge ${user.isActive ? 'badge--resolved' : 'badge--closed'}">${user.isActive ? 'Active' : 'Blocked'}</span>
      </div>
      <p class="muted" style="font-size:var(--fs-xs);margin-top:var(--sp-3)">${esc(user.department)}</p>
      <p class="muted" style="font-size:var(--fs-xs);word-break:break-all">${esc(user.email)}</p>
      <p style="font-size:var(--fs-xs);margin-top:var(--sp-2)">
        <span class="strong tnum">${user.complaintCount}</span> complaints ·
        <span class="strong tnum">${user.activeComplaints}</span> active
      </p>
    </article>`
}

function render() {
  const searchInput = qs('[data-filter="search"]')
  const hadFocus = document.activeElement === searchInput
  const caret = searchInput?.selectionStart ?? 0

  qs('#area').innerHTML = `
    <div class="stack">
      <div class="grid grid-4">
        ${statCard({ label: 'Total accounts', value: summary.total, icon: 'users' })}
        ${statCard({ label: 'Students', value: summary.students, icon: 'graduation-cap', tone: 'info' })}
        ${statCard({ label: 'Staff', value: summary.staff, icon: 'briefcase', tone: 'purple' })}
        ${statCard({ label: 'Officers', value: summary.officers, icon: 'user-cog', tone: 'warning', href: '/admin/officers.html' })}
      </div>

      <section class="card">
        ${filterPanel({
          filters,
          fields: [{ name: 'userType', label: 'Account type', options: ['Student', 'Staff'] }],
          showDates: false,
          placeholder: 'Search by name, ID, email or department…',
        })}

        <div class="card__body card__body--flush">
          ${
            users.length
              ? `<div class="desktop-table table-wrap scroll-slim">
                   <table class="table" style="min-width:1000px">
                     <thead>
                       <tr>
                         <th scope="col">Name</th>
                         <th scope="col">Type</th>
                         <th scope="col">Department / Course</th>
                         <th scope="col">Email</th>
                         <th scope="col">Complaints</th>
                         <th scope="col">Active</th>
                         <th scope="col">Last complaint</th>
                         <th scope="col">Status</th>
                         <th scope="col" class="right">Action</th>
                       </tr>
                     </thead>
                     <tbody>${users.map(row).join('')}</tbody>
                   </table>
                 </div>
                 <div class="mobile-cards">${users.map(mobileCard).join('')}</div>`
              : `<div class="state"><span class="state__icon">${icon('users', 'icon-xl')}</span>
                   <p class="state__title">No accounts found</p>
                   <p class="state__text">Try clearing the search or the account type filter.</p></div>`
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
  if (!qs('#area').innerHTML) mount('#area', loadingState('Loading accounts…'))

  try {
    ;[users, summary] = await Promise.all([getUsers(filters), getUserSummary()])
    render()
  } catch (error) {
    mount('#area', errorState({ message: error.message, retryId: 'retry' }))
    qs('#retry')?.addEventListener('click', load)
  }
}

/** Create a second administrator. Admin-only, and never publicly reachable. */
function openAdminForm() {
  const modal = openModal({
    title: 'Add an administrator',
    description:
      'Administrators can see every complaint, manage officers and reassign work. '
      + 'Create these accounts sparingly.',
    size: 'lg',
    body: `
      <form id="admin-form" novalidate class="stack-sm">
        <div class="grid grid-2">
          <div class="field" data-field="fullName">
            <label class="field__label" for="adm-name">Full name<span class="field__req">*</span></label>
            <input type="text" class="field__control" id="adm-name" name="fullName" required>
          </div>
          <div class="field" data-field="userId">
            <label class="field__label" for="adm-id">Employee ID<span class="field__req">*</span></label>
            <input type="text" class="field__control" id="adm-id" name="userId"
                   placeholder="DSVV/ADM/002" required>
          </div>
        </div>

        <div class="field" data-field="email">
          <label class="field__label" for="adm-email">Email address<span class="field__req">*</span></label>
          <input type="email" class="field__control" id="adm-email" name="email"
                 placeholder="name@dsvv.ac.in" required>
        </div>

        <div class="field" data-field="department">
          <label class="field__label" for="adm-dep">Office / department<span class="field__req">*</span></label>
          <input type="text" class="field__control" id="adm-dep" name="department"
                 value="Office of the Registrar" required>
        </div>

        <div class="field" data-field="password">
          <label class="field__label" for="adm-pass">Initial password<span class="field__req">*</span></label>
          <input type="password" class="field__control" id="adm-pass" name="password"
                 autocomplete="new-password" placeholder="At least 8 characters" required>
          <p class="field__hint">
            Share this securely. They can change it from their profile after signing in.
          </p>
        </div>
      </form>`,
    footer: `
      <button type="button" class="btn btn--secondary" data-close>Cancel</button>
      <button type="button" class="btn btn--primary" data-save>
        ${icon('check', 'icon-sm')}Create administrator
      </button>`,
  })

  on(modal.element, 'click', '[data-save]', async (event, button) => {
    const form = qs('#admin-form', modal.element)
    const values = formValues(form)

    clearErrors(form)
    const errors = {}
    if (!values.fullName?.trim()) errors.fullName = 'Full name is required'
    if (!values.userId?.trim()) errors.userId = 'Employee ID is required'
    if (!values.email?.trim()) errors.email = 'Email is required'
    else if (!isEmail(values.email)) errors.email = 'Enter a valid email address'
    if (!values.department?.trim()) errors.department = 'Office or department is required'
    if (!values.password) errors.password = 'Set an initial password'
    else if (values.password.length < 8) {
      errors.password = 'Password must be at least 8 characters'
    }
    if (Object.keys(errors).length) {
      showErrors(form, errors)
      return
    }

    setLoading(button, true, 'Creating…')
    try {
      await createUser({ ...values, role: ROLES.ADMIN })
      toast.success(`${values.fullName} can now sign in as an administrator.`, 'Administrator added')
      modal.close()
      load()
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message, 'Could not create the account')
    }
  })
}


ready(() => {
  const user = requireRole(ROLES.ADMIN)
  if (!user) return

  renderShell(user, { title: 'Students & Staff' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'Students & staff',
      lead: 'Every account that can register a complaint on the portal.',
      crumbs: [{ label: 'Dashboard', href: '/admin/dashboard.html' }, { label: 'Students & Staff' }],
      actions: `<button type="button" class="btn btn--primary" data-add-admin>
        ${icon('shield-check', 'icon-sm')}Add administrator
      </button>`,
    })}
    <div id="area"></div>`

  load()

  // An administrator account cannot be self-registered, so this is the only
  // place one is created. The server re-checks the caller is an admin.
  on('#root', 'click', '[data-add-admin]', () => openAdminForm())

  on('#area', 'click', '[data-toggle]', async (event, button) => {
    const target = users.find((item) => item.id === button.dataset.toggle)
    if (!target) return

    const confirmed = await confirmDialog({
      title: target.isActive ? `Block ${target.name}?` : `Unblock ${target.name}?`,
      message: target.isActive
        ? 'A blocked account cannot sign in or register new complaints. Existing complaints are not affected.'
        : 'This account will be able to sign in and register complaints again.',
      confirmLabel: target.isActive ? 'Block account' : 'Unblock account',
      tone: target.isActive ? 'danger' : 'success',
    })
    if (!confirmed) return

    try {
      await toggleUserStatus(target.id)
      toast.success(`${target.name} is now ${target.isActive ? 'blocked' : 'active'}.`)
      load()
    } catch (error) {
      toast.error(error.message)
    }
  })
})
