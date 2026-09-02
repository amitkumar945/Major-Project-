/**
 * Password reset.
 *
 * Two steps against the existing API, no new endpoints:
 *
 *   1. POST /auth/forgot-password  - emails a 6-digit code
 *   2. POST /auth/reset-password   - verifies the code and saves the password
 *
 * The request step always reports the same thing whether or not the address is
 * registered, because the backend deliberately answers identically: telling the
 * two apart here would turn the screen into a way of discovering which email
 * addresses have accounts.
 *
 * DEVELOPMENT: when the server has OTP_DEV_MODE=true and no SMTP configured, it
 * returns the code in the response instead of emailing it. That code is shown
 * on screen so the flow is usable before mail is set up. Once real MAIL_*
 * credentials are in backend/.env and OTP_DEV_MODE=false, the server stops
 * returning it and the notice disappears on its own - nothing here changes.
 */

import { clearErrors, formValues, icon, mount, on, qs, ready, setLoading, showErrors } from '../components/dom.js'
import { authAside } from '../components/authAside.js'
import { toast } from '../components/toast.js'
import { requestPasswordReset, resetPassword } from '../services/authService.js'
import { isEmail, passwordStrength } from '../utils/validators.js'

/* Carried from step 1 to step 2. */
let requestedEmail = ''
let devCode = ''

/* ------------------------------------------------------- step 1: request */

function formView(prefill = '') {
  return `
    <a class="auth__back" href="/login.html">${icon('arrow-left', 'icon-sm')}Back to sign in</a>

    <h1 class="auth__title">Reset your password</h1>
    <p class="auth__lead">
      Enter the email address you registered with. We will send you a 6-digit code to set a
      new password.
    </p>

    <form novalidate id="reset-form" style="margin-top:var(--sp-6)">
      <div class="field" data-field="email">
        <label class="field__label" for="email">Email address<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('mail', 'icon-sm')}</span>
          <input type="email" class="field__control" id="email" name="email"
                 autocomplete="email" placeholder="name@dsvv.ac.in"
                 value="${prefill}" required>
        </div>
      </div>

      <button type="submit" class="btn btn--primary btn--block btn--lg" style="margin-top:var(--sp-5)">
        ${icon('send', 'icon-md')}Send code
      </button>
    </form>`
}

/* -------------------------------------------- step 2: code + new password */

function codeView(email) {
  // Shown only when the server itself handed back the code (dev mode).
  const devNotice = devCode
    ? `<div class="alert alert--warning" style="margin-bottom:var(--sp-5);text-align:left">
         <span class="alert__icon">${icon('info', 'icon-lg')}</span>
         <div class="grow">
           <p class="alert__title">Development mode</p>
           <p class="alert__text">
             No email service is configured yet, so the code is shown here instead of being
             emailed: <span class="strong mono" style="font-size:var(--fs-md)">${devCode}</span>
           </p>
         </div>
       </div>`
    : ''

  return `
    <button type="button" class="auth__back" data-again>
      ${icon('arrow-left', 'icon-sm')}Use a different email address
    </button>

    <h1 class="auth__title">Enter the code</h1>
    <p class="auth__lead">
      If <span class="strong">${email}</span> is registered, a 6-digit code is on its way.
      Enter it below along with your new password.
    </p>

    ${devNotice}

    <form novalidate id="code-form" style="margin-top:var(--sp-6)">
      <div class="field" data-field="otp">
        <label class="field__label" for="otp">6-digit code<span class="field__req">*</span></label>
        <input type="text" class="field__control mono" id="otp" name="otp"
               inputmode="numeric" autocomplete="one-time-code" maxlength="6"
               placeholder="- - - - - -" required
               style="letter-spacing:.5em;text-align:center;font-size:var(--fs-lg)">
        <p class="field__hint">
          The code expires a few minutes after it is sent. Check the spam folder if it
          does not arrive, then use “Send it again”.
        </p>
      </div>

      <div class="field" data-field="newPassword">
        <label class="field__label" for="newPassword">New password<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('lock', 'icon-sm')}</span>
          <input type="password" class="field__control" id="newPassword" name="newPassword"
                 autocomplete="new-password" placeholder="At least 8 characters" required>
          <button type="button" class="btn-icon btn-reveal" data-reveal="newPassword"
                  aria-label="Show password">${icon('eye', 'icon-sm')}</button>
        </div>
        <div class="meter" data-meter aria-hidden="true">
          <span class="meter__bar"></span><span class="meter__bar"></span>
          <span class="meter__bar"></span><span class="meter__bar"></span>
        </div>
      </div>

      <div class="field" data-field="confirmPassword">
        <label class="field__label" for="confirmPassword">Confirm new password<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('lock', 'icon-sm')}</span>
          <input type="password" class="field__control" id="confirmPassword" name="confirmPassword"
                 autocomplete="new-password" placeholder="Re-enter the password" required>
        </div>
      </div>

      <button type="submit" class="btn btn--primary btn--block btn--lg" style="margin-top:var(--sp-5)">
        ${icon('check', 'icon-md')}Save new password
      </button>
    </form>

    <button type="button" class="btn btn--link" data-resend style="margin-top:var(--sp-4)">
      Did not get the code? Send it again
    </button>`
}

/* ------------------------------------------------------------- step 3: done */

function doneView() {
  return `
    <div class="center">
      <span class="success-mark">${icon('check-circle', 'icon-xl')}</span>
      <h1 class="auth__title" style="margin-top:var(--sp-5)">Password updated</h1>
      <p class="auth__lead">
        Your password has been changed. You can now sign in with your new password.
      </p>
      <a class="btn btn--primary btn--block btn--lg" href="/login.html" style="margin-top:var(--sp-6)">
        ${icon('log-in', 'icon-md')}Go to sign in
      </a>
    </div>`
}

/* ------------------------------------------------------------------ wiring */

/** Ask the server for a code. Shared by step 1 and the "send again" button. */
async function sendCode(email, button, loadingLabel) {
  setLoading(button, true, loadingLabel)
  try {
    const result = await requestPasswordReset(email)
    requestedEmail = email
    // Present only while the server is in dev mode with no SMTP configured.
    devCode = result?.otp ?? ''
    return true
  } catch (error) {
    toast.error(error.message, 'Could not send the code')
    return false
  } finally {
    setLoading(button, false)
  }
}

function attachRequest() {
  const form = qs('#reset-form')
  if (!form) return

  form.addEventListener('submit', async (event) => {
    event.preventDefault()
    const values = formValues(form)
    const button = qs('button[type="submit"]', form)

    clearErrors(form)
    if (!values.email) {
      showErrors(form, { email: 'Email address is required' })
      return
    }
    if (!isEmail(values.email)) {
      showErrors(form, { email: 'Enter a valid email address' })
      return
    }

    if (await sendCode(values.email, button, 'Sending…')) {
      mount('#root', codeView(requestedEmail))
      attachCode()
    }
  })
}

function attachCode() {
  const form = qs('#code-form')
  if (!form) return

  // Live strength meter, matching the register screen.
  const password = qs('#newPassword', form)
  password?.addEventListener('input', () => {
    const { score } = passwordStrength(password.value)
    const tone = ['weak', 'weak', 'fair', 'good', 'strong'][score] ?? 'weak'
    qs('[data-meter]', form)?.querySelectorAll('.meter__bar').forEach((bar, index) => {
      bar.className = `meter__bar ${index < score ? `is-on-${tone}` : ''}`
    })
  })

  form.addEventListener('submit', async (event) => {
    event.preventDefault()
    const values = formValues(form)
    const button = qs('button[type="submit"]', form)

    clearErrors(form)
    const errors = {}
    if (!/^\d{6}$/.test((values.otp ?? '').trim())) {
      errors.otp = 'Enter the 6-digit code from the email'
    }
    if (!values.newPassword) {
      errors.newPassword = 'Enter a new password'
    } else if (values.newPassword.length < 8) {
      errors.newPassword = 'Password must be at least 8 characters'
    }
    if (values.confirmPassword !== values.newPassword) {
      errors.confirmPassword = 'The two passwords do not match'
    }
    if (Object.keys(errors).length) {
      showErrors(form, errors)
      return
    }

    setLoading(button, true, 'Saving…')
    try {
      await resetPassword({
        email: requestedEmail,
        otp: values.otp.trim(),
        newPassword: values.newPassword,
      })
      devCode = ''
      toast.success('You can now sign in with your new password.', 'Password updated')
      mount('#root', doneView())
    } catch (error) {
      setLoading(button, false)
      // A wrong or expired code comes back as a field error from the API.
      showErrors(form, { otp: error.message })
      toast.error(error.message, 'Could not reset the password')
    }
  })
}

/* -------------------------------------------------------------------- boot */

ready(() => {
  qs('#auth-aside').innerHTML = authAside()
  mount('#root', formView())
  attachRequest()

  on('#root', 'click', '[data-again]', () => {
    const previous = requestedEmail
    requestedEmail = ''
    devCode = ''
    mount('#root', formView(previous))
    attachRequest()
  })

  on('#root', 'click', '[data-resend]', async (event, button) => {
    if (!requestedEmail) return
    if (await sendCode(requestedEmail, button, 'Sending…')) {
      toast.success('A new code has been sent.', 'Code sent')
      mount('#root', codeView(requestedEmail))
      attachCode()
    }
  })

  // Show/hide the new password.
  on('#root', 'click', '[data-reveal]', (event, button) => {
    const input = qs(`#${button.dataset.reveal}`)
    if (!input) return
    const shown = input.type === 'text'
    input.type = shown ? 'password' : 'text'
    button.setAttribute('aria-label', shown ? 'Show password' : 'Hide password')
    button.innerHTML = icon(shown ? 'eye' : 'eye-off', 'icon-sm')
  })
})
