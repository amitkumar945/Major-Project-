/**
 * Help & Support - FAQs, a support form and the grievance cell's details.
 */

import { esc, formValues, icon, on, qs, ready, setLoading } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { toast } from '../components/toast.js'
import { ROLES, UNIVERSITY_NAME } from '../utils/constants.js'

const FAQS = [
  {
    q: 'How do I register a complaint?',
    a: 'Open “Submit Complaint” from the sidebar and follow the five steps: describe the problem, attach photographs, tag the location, run the AI analysis, then review and submit. You will receive a reference number immediately.',
  },
  {
    q: 'How long will my complaint take?',
    a: 'The deadline depends on the priority the system assigns — one day for urgent, three days for high, seven for medium and fourteen for low. You can see the exact date on the complaint details page.',
  },
  {
    q: 'What happens if the deadline is missed?',
    a: 'The complaint is escalated automatically. Level 1 is the department officer, level 2 the department head, and level 3 the administration. You are notified at every escalation.',
  },
  {
    q: 'Can I attach more photographs later?',
    a: 'Evidence is attached at the time of submission. If you have more to add, post it as a remark on the complaint or mention it when the officer contacts you.',
  },
  {
    q: 'The problem came back after it was marked resolved. What now?',
    a: 'Open the complaint and choose “Reopen complaint”. It goes back to the same department with its full history attached, which is faster than filing a fresh complaint.',
  },
  {
    q: 'Why was my complaint sent to a different department?',
    a: 'The system reads the complaint text and routes it to the department that handles that kind of problem. If it looks wrong, add a remark and the grievance cell can reassign it.',
  },
]

function view() {
  return `
    <div class="split">
      <div class="stack">
        <section class="card">
          <header class="card__head"><h2 class="card__title">Frequently asked questions</h2></header>
          <div class="card__body">
            <div class="faq" id="faq-list">
              ${FAQS.map(
                (item, index) => `
                <article class="card faq__item" style="box-shadow:none">
                  <h3>
                    <button type="button" class="faq__q" aria-expanded="false" aria-controls="faq-${index}">
                      ${esc(item.q)}${icon('chevron-down', 'icon-md')}
                    </button>
                  </h3>
                  <div class="faq__a" id="faq-${index}" hidden>${esc(item.a)}</div>
                </article>`,
              ).join('')}
            </div>
          </div>
        </section>

        <section class="card">
          <header class="card__head">
            <div>
              <h2 class="card__title">Still need help?</h2>
              <p class="card__subtitle">Send a message to the grievance cell</p>
            </div>
          </header>

          <form id="support-form" novalidate>
            <div class="card__body stack-sm">
              <div class="field" data-field="subject">
                <label class="field__label" for="subject">Subject<span class="field__req">*</span></label>
                <input type="text" class="field__control" id="subject" name="subject"
                       placeholder="What do you need help with?" required>
              </div>
              <div class="field" data-field="message">
                <label class="field__label" for="message">Message<span class="field__req">*</span></label>
                <textarea class="field__control" id="message" name="message" rows="5"
                          placeholder="Describe your question in detail." required></textarea>
              </div>
            </div>
            <footer class="card__foot" style="display:flex;justify-content:flex-end">
              <button type="submit" class="btn btn--primary">${icon('send', 'icon-sm')}Send message</button>
            </footer>
          </form>
        </section>
      </div>

      <div class="stack split__aside">
        <section class="card">
          <header class="card__head"><h2 class="card__title">Grievance Redressal Cell</h2></header>
          <div class="card__body">
            <ul class="stack-sm">
              <li class="row" style="align-items:flex-start">
                ${icon('map-pin', 'icon-sm')}
                <span>Administrative Block, ${esc(UNIVERSITY_NAME)}, Haridwar, Uttarakhand</span>
              </li>
              <li class="row">
                ${icon('mail', 'icon-sm')}
                <a href="mailto:grievance@dsvv.ac.in">grievance@dsvv.ac.in</a>
              </li>
              <li class="row">
                ${icon('clock', 'icon-sm')}
                <span>Monday to Saturday, 9:00 AM – 5:00 PM</span>
              </li>
            </ul>
          </div>
        </section>

        <section class="card">
          <header class="card__head"><h2 class="card__title">Quick links</h2></header>
          <div class="card__body stack-sm">
            <a class="btn btn--secondary btn--block" href="/student/new-complaint.html">
              ${icon('file-plus', 'icon-sm')}Submit a complaint
            </a>
            <a class="btn btn--secondary btn--block" href="/student/complaints.html">
              ${icon('clipboard-list', 'icon-sm')}My complaints
            </a>
            <a class="btn btn--secondary btn--block" href="/track.html">
              ${icon('file-search', 'icon-sm')}Track by reference number
            </a>
          </div>
        </section>
      </div>
    </div>`
}

ready(() => {
  const user = requireRole(ROLES.STUDENT)
  if (!user) return

  renderShell(user, { title: 'Help & Support' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'Help & Support',
      lead: 'Answers to common questions, and a way to reach the grievance cell.',
      crumbs: [{ label: 'Dashboard', href: '/student/dashboard.html' }, { label: 'Help & Support' }],
    })}
    ${view()}`

  // FAQ accordion
  on('#faq-list', 'click', '.faq__q', (event, button) => {
    const panel = document.getElementById(button.getAttribute('aria-controls'))
    const open = button.getAttribute('aria-expanded') === 'true'
    button.setAttribute('aria-expanded', String(!open))
    panel.hidden = open
  })

  qs('#support-form').addEventListener('submit', async (event) => {
    event.preventDefault()
    const form = event.target
    const values = formValues(form)
    const button = qs('button[type="submit"]', form)

    if (!values.subject || !values.message) {
      toast.warning('Please fill in both the subject and the message.')
      return
    }

    setLoading(button, true, 'Sending…')
    // No mail service in the prototype - the Flask API will handle this later.
    setTimeout(() => {
      setLoading(button, false)
      form.reset()
      toast.success('Your message has been sent to the grievance cell.', 'Message sent')
    }, 700)
  })
})
