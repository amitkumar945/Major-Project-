/**
 * Login page.
 *
 * DEMO ONLY: the password is checked in the browser against the list in
 * `utils/constants.js`. Replace `authService.login` with a call to
 * `POST /api/auth/login` and this page keeps working unchanged.
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
import { authAside } from '../components/authAside.js'
import { toast } from '../components/toast.js'
import { login } from '../services/authService.js'
import { currentUser } from '../components/session.js'
import { HOME_PAGE } from '../components/navigation.js'
import { DEMO_ACCOUNTS, ROLES, ROLE_LABELS } from '../utils/constants.js'
import { validateLogin, isValid } from '../utils/validators.js'

/** Where to go after signing in - honours ?next= from the guard. */
function destination(role) {
  const next = new URLSearchParams(location.search).get('next')
  if (next && next.startsWith('/')) return next
  return HOME_PAGE[role] ?? '/index.html'
}

function view() {
  const roleOptions = [ROLES.STUDENT, ROLES.OFFICER, ROLES.ADMIN]
    .map(
      (role, index) => `
      <label class="radio-card">
        <input type="radio" name="role" value="${esc(role)}" ${index === 0 ? 'checked' : ''}>
        <span class="grow">
          <span class="radio-card__title">${esc(ROLE_LABELS[role])}</span>
        </span>
      </label>`,
    )
    .join('')

  const demoButtons = DEMO_ACCOUNTS.map(
    (account) => `
      <button type="button" class="btn btn--secondary btn--sm" data-demo="${esc(account.email)}"
              data-role="${esc(account.role)}" data-password="${esc(account.password)}">
        ${icon('log-in', 'icon-sm')}${esc(ROLE_LABELS[account.role])}
      </button>`,
  ).join('')

  return `
    <a class="auth__back" href="/index.html">${icon('arrow-left', 'icon-sm')}Back to website</a>

    <h1 class="auth__title">Sign in to your account</h1>
    <p class="auth__lead">Use your registered university email address to continue.</p>

    <form novalidate id="login-form" style="margin-top:var(--sp-6)">
      <fieldset style="margin-bottom:var(--sp-5)">
        <legend class="field__label">Sign in as</legend>
        <div class="radio-cards">${roleOptions}</div>
      </fieldset>

      <div class="field" data-field="identifier">
        <label class="field__label" for="identifier">Email address<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('mail', 'icon-sm')}</span>
          <input type="email" class="field__control" id="identifier" name="identifier"
                 autocomplete="email" placeholder="name@dsvv.ac.in" required>
        </div>
      </div>

      <div class="field" data-field="password">
        <label class="field__label" for="password">Password<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('lock', 'icon-sm')}</span>
          <input type="password" class="field__control" id="password" name="password"
                 autocomplete="current-password" placeholder="Enter your password" required>
          <button type="button" class="btn-icon btn-reveal" data-reveal aria-label="Show password">
            ${icon('eye', 'icon-sm')}
          </button>
        </div>
      </div>

      <div class="between" style="margin-top:var(--sp-4)">
        <label class="check">
          <input type="checkbox" name="remember" checked>
          <span class="check__text">Remember me</span>
        </label>
        <a href="/forgot-password.html" style="font-size:var(--fs-base)">Forgot password?</a>
      </div>

      <button type="submit" class="btn btn--primary btn--block btn--lg" style="margin-top:var(--sp-6)">
        ${icon('log-in', 'icon-md')}Sign in
      </button>
    </form>

    <p class="center muted" style="margin-top:var(--sp-5)">
      Do not have an account? <a href="/register.html" class="strong">Register now</a>
    </p>

    <div class="auth__divider">Demo accounts</div>

    <p class="center muted" style="margin-bottom:var(--sp-3)">
      One click fills the form and signs you in.
    </p>
    <div class="row-wrap" style="justify-content:center">${demoButtons}</div>

    <p class="note-dashed" style="margin-top:var(--sp-6)">
      These demo accounts exist only in the browser. Real authentication arrives with the Flask API.
    </p>`
}

async function submit(form, values) {
  const button = qs('button[type="submit"]', form)
  clearErrors(form)

  const errors = validateLogin(values)
  if (!isValid(errors)) {
    showErrors(form, errors)
    return
  }

  setLoading(button, true, 'Signing in…')
  try {
    const session = await login({
      identifier: values.identifier,
      password: values.password,
      role: values.role,
    })
    toast.success(`Welcome back, ${session.user.name.split(' ')[0]}.`, 'Signed in')
    location.href = destination(session.user.role)
  } catch (error) {
    setLoading(button, false)
    toast.error(error.message, 'Could not sign in')
  }
}

ready(() => {
  // Already signed in? Go straight to the dashboard.
  const user = currentUser()
  if (user) {
    location.replace(destination(user.role))
    return
  }

  qs('#auth-aside').innerHTML = authAside()
  mount('#root', view())

  const form = qs('#login-form')

  form.addEventListener('submit', (event) => {
    event.preventDefault()
    submit(form, formValues(form))
  })

  on(form, 'click', '[data-reveal]', (event, button) => {
    const input = qs('#password')
    const shown = input.type === 'text'
    input.type = shown ? 'password' : 'text'
    button.setAttribute('aria-label', shown ? 'Show password' : 'Hide password')
    button.innerHTML = icon(shown ? 'eye' : 'eye-off', 'icon-sm')
  })

  // Demo buttons fill the form and submit it, so a demonstration needs no typing.
  on('#root', 'click', '[data-demo]', (event, button) => {
    qs('#identifier').value = button.dataset.demo
    qs('#password').value = button.dataset.password
    qs(`input[name="role"][value="${button.dataset.role}"]`).checked = true
    submit(form, formValues(form))
  })
})
