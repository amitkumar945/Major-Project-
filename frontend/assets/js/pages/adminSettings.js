/**
 * System settings - resolution targets, notification preferences, automation
 * rules and the demo reset.
 *
 * These values are held in the browser for the prototype. The Flask API will
 * store them and apply them server-side.
 */

import { esc, icon, on, qs, ready, setLoading } from '../components/dom.js'
import { pageHeader, renderShell } from '../components/shell.js'
import { requireRole } from '../components/session.js'
import { alertBox } from '../components/ui.js'
import { confirmDialog } from '../components/modal.js'
import { toast } from '../components/toast.js'
import { resetDemoData } from '../services/complaintService.js'
import { ESCALATION_LEVELS, PRIORITY_SLA_DAYS, ROLES } from '../utils/constants.js'
import { readStorage, writeStorage } from '../utils/helpers.js'

const KEY = 'dsvv_settings'

const DEFAULTS = {
  sla: { ...PRIORITY_SLA_DAYS },
  notifyEmail: true,
  notifyInApp: true,
  autoAssign: true,
  autoEscalate: true,
  duplicateCheck: true,
  aiClassification: true,
}

let settings = { ...DEFAULTS, ...readStorage(KEY, {}) }

function slaCard() {
  return `
    <section class="card">
      <header class="card__head">
        <div>
          <h2 class="card__title">Resolution targets</h2>
          <p class="card__subtitle">Days allowed before a complaint is overdue</p>
        </div>
      </header>
      <div class="card__body">
        <div class="grid grid-4">
          ${Object.entries(settings.sla)
            .map(
              ([priority, days]) => `
            <div class="field">
              <label class="field__label" for="sla-${esc(priority)}">${esc(priority)}</label>
              <input type="number" min="1" max="90" class="field__control" id="sla-${esc(priority)}"
                     data-sla="${esc(priority)}" value="${days}">
              <p class="field__hint">days</p>
            </div>`,
            )
            .join('')}
        </div>
      </div>
    </section>`
}

function toggleRow(name, label, description) {
  return `
    <label class="check" style="padding:var(--sp-3) 0;border-bottom:1px solid var(--border-soft)">
      <input type="checkbox" data-setting="${esc(name)}" ${settings[name] ? 'checked' : ''}>
      <span class="check__text">${esc(label)}<span class="check__desc">${esc(description)}</span></span>
    </label>`
}

function view() {
  return `
    <div class="stack">
      ${slaCard()}

      <div class="split split--even">
        <section class="card">
          <header class="card__head">
            <div>
              <h2 class="card__title">Notifications</h2>
              <p class="card__subtitle">How complainants and officers are informed</p>
            </div>
          </header>
          <div class="card__body">
            ${toggleRow('notifyInApp', 'In-app notifications', 'Shown in the notification centre and on the bell icon.')}
            ${toggleRow('notifyEmail', 'Email notifications', 'Status updates delivered by email. Requires the email service to be configured in the backend.')}
          </div>
        </section>

        <section class="card">
          <header class="card__head">
            <div>
              <h2 class="card__title">Automation</h2>
              <p class="card__subtitle">What the system does without a human step</p>
            </div>
          </header>
          <div class="card__body">
            ${toggleRow('aiClassification', 'AI classification', 'Predict the department and priority from the complaint text.')}
            ${toggleRow('duplicateCheck', 'Duplicate detection', 'Warn the complainant when a similar complaint already exists.')}
            ${toggleRow('autoAssign', 'Workload-based assignment', 'Give the complaint to the officer with the lightest active load.')}
            ${toggleRow('autoEscalate', 'Automatic escalation', 'Raise a complaint up the ladder as soon as its deadline passes.')}
          </div>
        </section>
      </div>

      <section class="card">
        <header class="card__head">
          <div>
            <h2 class="card__title">Escalation ladder</h2>
            <p class="card__subtitle">Fixed in this build; configurable once the backend stores it</p>
          </div>
        </header>
        <div class="card__body">
          <div class="grid grid-3">
            ${ESCALATION_LEVELS.map(
              (rule) => `
              <div class="card" style="padding:var(--sp-4);box-shadow:none">
                <p class="strong">Level ${rule.level}</p>
                <p class="muted" style="font-size:var(--fs-xs);margin-top:.25rem">${esc(rule.authority)}</p>
                <p class="muted" style="font-size:var(--fs-xs);margin-top:.5rem">
                  ${rule.afterDays === 0 ? 'Immediately after the deadline' : `${rule.afterDays}+ days overdue`}
                </p>
              </div>`,
            ).join('')}
          </div>
        </div>
      </section>

      <div class="row-wrap" style="justify-content:flex-end">
        <button type="button" class="btn btn--primary" data-save>${icon('check', 'icon-sm')}Save settings</button>
      </div>

      <section class="card" style="border-color:var(--red-100)">
        <header class="card__head">
          <div>
            <h2 class="card__title">Demo data</h2>
            <p class="card__subtitle">Reset everything created during this demonstration</p>
          </div>
        </header>
        <div class="card__body">
          <p class="muted">
            Complaints you submitted, status changes, remarks, resolutions and feedback are stored in
            this browser. Resetting removes them and restores the original sample data.
          </p>
          <button type="button" class="btn btn--danger" style="margin-top:var(--sp-4)" data-reset>
            ${icon('rotate-ccw', 'icon-sm')}Reset demo data
          </button>
        </div>
      </section>

      ${alertBox({
        tone: 'warning',
        icon: 'alert-triangle',
        title: 'Prototype build',
        text: 'This build has no server. Authentication and AI classification are simulated in the browser and must be replaced by the Flask API before any real use.',
      })}
    </div>`
}

ready(() => {
  const user = requireRole(ROLES.ADMIN)
  if (!user) return

  renderShell(user, { title: 'Settings' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'System settings',
      lead: 'Resolution targets, notifications and the automation rules.',
      crumbs: [{ label: 'Dashboard', href: '/admin/dashboard.html' }, { label: 'Settings' }],
    })}
    <div id="area">${view()}</div>`

  const area = qs('#area')

  on(area, 'change', '[data-setting]', (event) => {
    settings[event.target.dataset.setting] = event.target.checked
  })

  on(area, 'change', '[data-sla]', (event) => {
    const days = Number(event.target.value)
    if (days > 0) settings.sla[event.target.dataset.sla] = days
  })

  on(area, 'click', '[data-save]', (event, button) => {
    setLoading(button, true, 'Saving…')
    writeStorage(KEY, settings)
    setTimeout(() => {
      setLoading(button, false)
      toast.success('Settings saved for this browser.', 'Settings updated')
    }, 500)
  })

  on(area, 'click', '[data-reset]', async () => {
    const confirmed = await confirmDialog({
      title: 'Reset all demo data?',
      message: 'Every complaint, status change and rating created during this demonstration will be removed. The original sample data is restored.',
      confirmLabel: 'Reset demo data',
      tone: 'danger',
    })
    if (!confirmed) return

    await resetDemoData()
    toast.success('The demo data has been restored.', 'Reset complete')
    setTimeout(() => location.reload(), 800)
  })
})
