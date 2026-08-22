/**
 * Password reset request.
 *
 * DEMO ONLY: no email is sent. The screen confirms the address exists and
 * shows the success state the real flow will show.
 */

import { clearErrors, formValues, icon, mount, on, qs, ready, setLoading, showErrors } from '../components/dom.js'
import { authAside } from '../components/authAside.js'
import { toast } from '../components/toast.js'
import { requestPasswordReset } from '../services/authService.js'
import { isEmail } from '../utils/validators.js'

function formView() {
  return `
    <a class="auth__back" href="/login.html">${icon('arrow-left', 'icon-sm')}Back to sign in</a>

    <h1 class="auth__title">Reset your password</h1>
    <p class="auth__lead">
      Enter the email address you registered with and we will send you a link to set a new password.
    </p>

    <form novalidate id="reset-form" style="margin-top:var(--sp-6)">
      <div class="field" data-field="email">
        <label class="field__label" for="email">Email address<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('mail', 'icon-sm')}</span>
          <input type="email" class="field__control" id="email" name="email"
                 autocomplete="email" placeholder="name@dsvv.ac.in" required>
        </div>
      </div>

      <button type="submit" class="btn btn--primary btn--block btn--lg" style="margin-top:var(--sp-5)">
        ${icon('send', 'icon-md')}Send reset link
      </button>
    </form>

    <p class="note-dashed" style="margin-top:var(--sp-6)">
      No email service is connected in this prototype, so no real mail is sent.
    </p>`
}

function sentView(email) {
  return `
    <div class="center">
      <span class="success-mark">${icon('mail-check', 'icon-xl')}</span>
      <h1 class="auth__title" style="margin-top:var(--sp-5)">Check your inbox</h1>
      <p class="auth__lead">
        If an account exists for <span class="strong">${email}</span>, a password reset link is on
        its way. The link expires in 30 minutes.
      </p>
      <a class="btn btn--primary btn--block btn--lg" href="/login.html" style="margin-top:var(--sp-6)">
        ${icon('arrow-left', 'icon-md')}Back to sign in
      </a>
      <button type="button" class="btn btn--link" data-again style="margin-top:var(--sp-4)">
        Use a different email address
      </button>
    </div>`
}

function attach() {
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

    setLoading(button, true, 'Sending…')
    try {
      await requestPasswordReset(values.email)
      mount('#root', sentView(values.email))
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message, 'Could not send the link')
    }
  })
}

ready(() => {
  qs('#auth-aside').innerHTML = authAside()
  mount('#root', formView())
  attach()

  on('#root', 'click', '[data-again]', () => {
    mount('#root', formView())
    attach()
  })
})
