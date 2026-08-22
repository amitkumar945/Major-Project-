/**
 * Profile page - shared by all three roles.
 * View and edit account details, and change the password.
 */

import {
  clearErrors,
  esc,
  formValues,
  html,
  icon,
  on,
  qs,
  ready,
  setLoading,
  showErrors,
} from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole, roleLabel } from '../components/session.js'
import { avatar, infoRow } from '../components/ui.js'
import { toast } from '../components/toast.js'
import { changePassword, updateProfile } from '../services/authService.js'
import { ROLES } from '../utils/constants.js'
import { formatDate } from '../utils/helpers.js'
import { isValid, validatePasswordChange, validateProfile } from '../utils/validators.js'

const ROLE = location.pathname.startsWith('/officer/')
  ? ROLES.OFFICER
  : location.pathname.startsWith('/admin/')
    ? ROLES.ADMIN
    : ROLES.STUDENT

let user = null
let editing = false

function summaryCard() {
  return html(
    '<section class="card">',
    '<div class="card__body center">',
    avatar(user.name, user.avatarColor, 'xl'),
    `<h2 style="font-size:var(--fs-lg);margin-top:var(--sp-4)">${esc(user.name)}</h2>`,
    `<p class="muted">${esc(user.designation ?? user.course ?? user.department ?? '')}</p>`,
    `<span class="badge badge--review" style="margin-top:var(--sp-3)">${esc(roleLabel(user.role))}</span>`,
    '</div>',

    '<div class="card__body" style="border-top:1px solid var(--border)">',
    '<div class="info-list">',
    infoRow(user.userId ? 'Student ID' : 'Employee ID', esc(user.userId ?? user.employeeId ?? '—')),
    infoRow('Email', `<a href="mailto:${esc(user.email)}" style="word-break:break-all">${esc(user.email)}</a>`),
    infoRow('Department', esc(user.department ?? '—')),
    user.hostel && user.hostel !== '—' ? infoRow('Residence', esc(user.hostel)) : '',
    infoRow('Member since', esc(formatDate(user.joinedAt))),
    '</div></div></section>',
  )
}

function detailsForm() {
  const disabled = editing ? '' : 'disabled'

  return html(
    '<section class="card">',
    '<header class="card__head">',
    '<div><h2 class="card__title">Account details</h2>',
    '<p class="card__subtitle">Keep your contact details up to date</p></div>',
    editing
      ? ''
      : `<button type="button" class="btn btn--secondary btn--sm" data-edit>${icon('pencil', 'icon-sm')}Edit</button>`,
    '</header>',

    '<form id="profile-form" novalidate>',
    '<div class="card__body">',
    '<div class="grid grid-2">',

    '<div class="field" data-field="name">',
    '<label class="field__label" for="name">Full name</label>',
    `<input type="text" class="field__control" id="name" name="name" value="${esc(user.name)}" ${disabled}>`,
    '</div>',

    '<div class="field" data-field="email">',
    '<label class="field__label" for="email">Email address</label>',
    `<input type="email" class="field__control" id="email" name="email" value="${esc(user.email)}" ${disabled}>`,
    '</div>',

    '<div class="field" data-field="userId">',
    `<label class="field__label" for="userId">${user.userId ? 'Student / Employee ID' : 'Employee ID'}</label>`,
    `<input type="text" class="field__control" id="userId" value="${esc(user.userId ?? user.employeeId ?? '')}" disabled>`,
    '<p class="field__hint">Issued by the university and cannot be changed here.</p>',
    '</div>',

    '<div class="field" data-field="department">',
    '<label class="field__label" for="department">Department / Course</label>',
    `<input type="text" class="field__control" id="department" name="department" value="${esc(user.department ?? '')}" ${disabled}>`,
    '</div>',

    '</div></div>',

    editing
      ? `<footer class="card__foot" style="display:flex;justify-content:flex-end;gap:var(--sp-3)">
           <button type="button" class="btn btn--secondary" data-cancel>Cancel</button>
           <button type="submit" class="btn btn--primary">${icon('check', 'icon-sm')}Save changes</button>
         </footer>`
      : '',
    '</form></section>',
  )
}

function passwordForm() {
  return html(
    '<section class="card">',
    '<header class="card__head">',
    '<div><h2 class="card__title">Change password</h2>',
    '<p class="card__subtitle">Use at least 8 characters</p></div>',
    '</header>',

    '<form id="password-form" novalidate>',
    '<div class="card__body stack-sm">',

    '<div class="field" data-field="currentPassword">',
    '<label class="field__label" for="currentPassword">Current password</label>',
    '<input type="password" class="field__control" id="currentPassword" name="currentPassword" autocomplete="current-password">',
    '</div>',

    '<div class="grid grid-2">',
    '<div class="field" data-field="newPassword">',
    '<label class="field__label" for="newPassword">New password</label>',
    '<input type="password" class="field__control" id="newPassword" name="newPassword" autocomplete="new-password">',
    '</div>',
    '<div class="field" data-field="confirmPassword">',
    '<label class="field__label" for="confirmPassword">Confirm new password</label>',
    '<input type="password" class="field__control" id="confirmPassword" name="confirmPassword" autocomplete="new-password">',
    '</div>',
    '</div></div>',

    `<footer class="card__foot" style="display:flex;justify-content:flex-end">
       <button type="submit" class="btn btn--primary">${icon('lock', 'icon-sm')}Update password</button>
     </footer>`,
    '</form></section>',
  )
}

function draw() {
  qs('#panels').innerHTML = `
    <div class="split">
      <div class="stack">${detailsForm()}${passwordForm()}</div>
      <div class="split__aside">${summaryCard()}</div>
    </div>`
  wire()
}

function wire() {
  on('#panels', 'click', '[data-edit]', () => {
    editing = true
    draw()
    qs('#name')?.focus()
  })

  on('#panels', 'click', '[data-cancel]', () => {
    editing = false
    draw()
  })

  qs('#profile-form')?.addEventListener('submit', async (event) => {
    event.preventDefault()
    const form = event.target
    const values = formValues(form)
    const button = qs('button[type="submit"]', form)

    clearErrors(form)
    const errors = validateProfile(values)
    if (!isValid(errors)) {
      showErrors(form, errors)
      return
    }

    setLoading(button, true, 'Saving…')
    try {
      user = await updateProfile(user.id, {
        name: values.name,
        email: values.email,
        department: values.department,
      })
      editing = false
      draw()
      toast.success('Your profile has been updated.')
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message)
    }
  })

  qs('#password-form')?.addEventListener('submit', async (event) => {
    event.preventDefault()
    const form = event.target
    const values = formValues(form)
    const button = qs('button[type="submit"]', form)

    clearErrors(form)
    const errors = validatePasswordChange(values)
    if (!isValid(errors)) {
      showErrors(form, errors)
      return
    }

    setLoading(button, true, 'Updating…')
    try {
      await changePassword(values)
      form.reset()
      toast.success('Your password has been changed.')
    } catch (error) {
      toast.error(error.message)
    } finally {
      setLoading(button, false)
    }
  })
}

ready(() => {
  user = requireRole(ROLE)
  if (!user) return

  renderShell(user, { title: 'Profile' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'My profile',
      lead: 'Your account details and password.',
      crumbs: [{ label: 'Dashboard', href: `/${ROLE}/dashboard.html` }, { label: 'Profile' }],
    })}
    <div id="panels"></div>`

  draw()
})
