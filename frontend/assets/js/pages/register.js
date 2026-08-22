/**
 * Registration page.
 *
 * DEMO ONLY: the account is created in the browser and the user is signed in
 * immediately. There is no OTP or email-verification step.
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
import { register } from '../services/authService.js'
import { currentUser } from '../components/session.js'
import { HOME_PAGE } from '../components/navigation.js'
import { isValid, passwordStrength, validateRegistration } from '../utils/validators.js'

const COURSES = [
  'MCA - Department of Computer Science',
  'BCA - Department of Computer Science',
  'M.Sc. Yogic Science',
  'M.A. Clinical Psychology',
  'B.A. Journalism & Mass Communication',
  'Department of Computer Science',
  'Library & Information Centre',
  'Other Department',
]

function view() {
  return `
    <a class="auth__back" href="/index.html">${icon('arrow-left', 'icon-sm')}Back to website</a>

    <h1 class="auth__title">Create your account</h1>
    <p class="auth__lead">
      Register once and you are signed in straight away — then raise and track any number of
      complaints.
    </p>

    <form novalidate id="register-form" style="margin-top:var(--sp-6)">
      <div class="field" data-field="fullName">
        <label class="field__label" for="fullName">Full name<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('user', 'icon-sm')}</span>
          <input type="text" class="field__control" id="fullName" name="fullName"
                 autocomplete="name" placeholder="As printed on your ID card" required>
        </div>
      </div>

      <div class="field" data-field="userId">
        <label class="field__label" for="userId">Student / Employee ID<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('id-card', 'icon-sm')}</span>
          <input type="text" class="field__control" id="userId" name="userId"
                 placeholder="e.g. MCA/2026/018" required>
        </div>
      </div>

      <div class="field" data-field="email">
        <label class="field__label" for="email">Email address<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('mail', 'icon-sm')}</span>
          <input type="email" class="field__control" id="email" name="email"
                 autocomplete="email" placeholder="name@dsvv.ac.in" required>
        </div>
        <p class="field__hint">You will use this email address to sign in.</p>
      </div>

      <div class="field" data-field="userType">
        <label class="field__label" for="userType">I am a<span class="field__req">*</span></label>
        <select class="field__control" id="userType" name="userType">
          <option value="Student" selected>Student</option>
          <option value="Staff">Staff member</option>
        </select>
      </div>

      <div class="field" data-field="department">
        <label class="field__label" for="department">Department / Course<span class="field__req">*</span></label>
        <select class="field__control" id="department" name="department" required>
          <option value="">Select your department or course</option>
          ${COURSES.map((course) => `<option value="${esc(course)}">${esc(course)}</option>`).join('')}
        </select>
      </div>

      <div class="field" data-field="password">
        <label class="field__label" for="password">Password<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('lock', 'icon-sm')}</span>
          <input type="password" class="field__control" id="password" name="password"
                 autocomplete="new-password" placeholder="At least 8 characters" required>
          <button type="button" class="btn-icon btn-reveal" data-reveal aria-label="Show password">
            ${icon('eye', 'icon-sm')}
          </button>
        </div>
        <div class="meter" aria-hidden="true">
          <span class="meter__bar"></span><span class="meter__bar"></span>
          <span class="meter__bar"></span><span class="meter__bar"></span>
        </div>
        <p class="field__hint" data-strength>Use a mix of letters, numbers and symbols.</p>
      </div>

      <div class="field" data-field="confirmPassword">
        <label class="field__label" for="confirmPassword">Confirm password<span class="field__req">*</span></label>
        <div class="field__wrap">
          <span class="icon-left">${icon('lock', 'icon-sm')}</span>
          <input type="password" class="field__control" id="confirmPassword" name="confirmPassword"
                 autocomplete="new-password" placeholder="Re-enter your password" required>
        </div>
      </div>

      <div class="field" data-field="acceptTerms" style="margin-top:var(--sp-5)">
        <label class="check">
          <input type="checkbox" name="acceptTerms" id="acceptTerms">
          <span class="check__text">
            I confirm that the details above are correct
            <span class="check__desc">Your account will be created immediately and you will be signed in.</span>
          </span>
        </label>
      </div>

      <button type="submit" class="btn btn--primary btn--block btn--lg" style="margin-top:var(--sp-6)">
        ${icon('user-plus', 'icon-md')}Create account
      </button>
    </form>

    <p class="center muted" style="margin-top:var(--sp-5)">
      Already registered? <a href="/login.html" class="strong">Sign in instead</a>
    </p>`
}

ready(() => {
  const user = currentUser()
  if (user) {
    location.replace(HOME_PAGE[user.role])
    return
  }

  qs('#auth-aside').innerHTML = authAside()
  mount('#root', view())

  const form = qs('#register-form')

  // Live password strength meter.
  on(form, 'input', '#password', (event) => {
    const { score, label } = passwordStrength(event.target.value)
    const tones = ['', 'weak', 'fair', 'good', 'strong']
    qs('.meter', form).querySelectorAll('.meter__bar').forEach((bar, index) => {
      bar.className = `meter__bar ${index < score ? `is-on-${tones[score]}` : ''}`
    })
    qs('[data-strength]', form).textContent = event.target.value
      ? `Password strength: ${label}`
      : 'Use a mix of letters, numbers and symbols.'
  })

  on(form, 'click', '[data-reveal]', (event, button) => {
    const input = qs('#password')
    const shown = input.type === 'text'
    input.type = shown ? 'password' : 'text'
    button.setAttribute('aria-label', shown ? 'Show password' : 'Hide password')
    button.innerHTML = icon(shown ? 'eye' : 'eye-off', 'icon-sm')
  })

  form.addEventListener('submit', async (event) => {
    event.preventDefault()
    const values = formValues(form)
    const button = qs('button[type="submit"]', form)

    clearErrors(form)
    const errors = validateRegistration(values)
    if (!isValid(errors)) {
      showErrors(form, errors)
      return
    }

    setLoading(button, true, 'Creating account…')
    try {
      // Registration signs the user in immediately - there is no OTP step.
      const session = await register(values)
      toast.success(
        `Welcome, ${session.user.name.split(' ')[0]}! Your account is ready.`,
        'Registration successful',
      )
      location.href = HOME_PAGE[session.user.role]
    } catch (error) {
      setLoading(button, false)
      toast.error(error.message, 'Registration failed')
    }
  })
})
