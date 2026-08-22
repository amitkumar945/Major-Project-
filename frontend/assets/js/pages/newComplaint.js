/**
 * Submit a complaint - a five-step form.
 *
 *   1. Details      title, description, category, department
 *   2. Evidence     photographs and documents
 *   3. Location     geo-tagging with a map preview
 *   4. AI analysis  department, priority, duplicates, suggested officer
 *   5. Review       summary, then submit
 *
 * The whole form lives in one object (`draft`). Moving between steps only
 * redraws the panel, so nothing typed is lost.
 */

import {
  clearErrors,
  esc,
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
import { infoRow, priorityBadge } from '../components/ui.js'
import { toast } from '../components/toast.js'
import { createFileUpload } from '../components/fileUpload.js'
import { createLocationPicker } from '../components/locationPicker.js'
import { aiAnalysisCard, duplicateAlert } from '../components/aiCard.js'
import { hydrateMaps, mapPreview } from '../components/complaintParts.js'
import { analyseComplaint, createComplaint } from '../services/complaintService.js'
import { pushNotification } from '../services/notificationService.js'
import {
  CATEGORIES,
  CATEGORY_DEPARTMENT_MAP,
  DEPARTMENT_NAMES,
  NOTIFICATION_TYPES,
  ROLES,
} from '../utils/constants.js'
import { formatDate, formatFileSize } from '../utils/helpers.js'
import { isValid, validateComplaintDetails, validateLocation } from '../utils/validators.js'

const DETAILS = '/student/complaint-details.html'

const STEPS = [
  { key: 'details', label: 'Complaint Details' },
  { key: 'evidence', label: 'Upload Evidence' },
  { key: 'location', label: 'Location' },
  { key: 'ai', label: 'AI Analysis' },
  { key: 'review', label: 'Review & Submit' },
]

/* ------------------------------------------------------------- the draft */

const draft = {
  title: '',
  description: '',
  category: '',
  department: '',
  evidence: [],
  location: { latitude: null, longitude: null, address: '', block: '', accuracy: 0 },
  ai: null,
  duplicates: [],
  duplicatesAcknowledged: false,
}

let step = 0
let uploader = null
let picker = null
let analysing = false
let aiError = ''
let user = null

/* --------------------------------------------------------------- stepper */

function stepper() {
  const items = STEPS.map(
    (item, index) => `
      <li class="stepper__item ${index === step ? 'is-current' : index < step ? 'is-done' : ''}">
        <span class="stepper__num">${index < step ? icon('check', 'icon-sm') : index + 1}</span>
        <span class="stepper__label">${esc(item.label)}</span>
      </li>`,
  ).join('')

  const percent = (step / (STEPS.length - 1)) * 100

  return `
    <ol class="stepper scroll-slim" aria-label="Complaint submission steps">${items}</ol>
    <div class="stepper-rail"><div class="stepper-rail__fill" style="width:${percent}%"></div></div>`
}

/* ----------------------------------------------------------------- steps */

function detailsStep() {
  return `
    <form id="details-form" novalidate class="stack">
      <div class="field" data-field="title">
        <label class="field__label" for="title">Complaint title<span class="field__req">*</span></label>
        <input type="text" class="field__control" id="title" name="title" maxlength="120"
               value="${esc(draft.title)}" placeholder="e.g. Water leakage near Gayatri Bhavan entrance" required>
        <p class="field__hint">A short line that describes the problem.</p>
      </div>

      <div class="field" data-field="description">
        <label class="field__label" for="description">Description<span class="field__req">*</span></label>
        <textarea class="field__control" id="description" name="description" rows="6" maxlength="1200"
                  placeholder="Describe what is wrong, since when, and how it is affecting you." required>${esc(draft.description)}</textarea>
        <p class="field__hint">
          At least 25 characters. The more detail you give, the more accurately the system can route
          your complaint.
        </p>
      </div>

      <div class="grid grid-2">
        <div class="field" data-field="category">
          <label class="field__label" for="category">Category<span class="field__req">*</span></label>
          <select class="field__control" id="category" name="category" required>
            <option value="">Select a category</option>
            ${CATEGORIES.map(
              (category) =>
                `<option value="${esc(category)}" ${draft.category === category ? 'selected' : ''}>${esc(category)}</option>`,
            ).join('')}
          </select>
        </div>

        <div class="field" data-field="department">
          <label class="field__label" for="department">Department<span class="field__req">*</span></label>
          <select class="field__control" id="department" name="department" required>
            <option value="">Select a department</option>
            ${DEPARTMENT_NAMES.map(
              (name) =>
                `<option value="${esc(name)}" ${draft.department === name ? 'selected' : ''}>${esc(name)}</option>`,
            ).join('')}
          </select>
          <p class="field__hint">Not sure? Pick the closest one — the AI step can correct it.</p>
        </div>
      </div>
    </form>`
}

function evidenceStep() {
  return `
    <div class="stack">
      <div class="alert alert--muted">
        <span class="alert__icon">${icon('info', 'icon-lg')}</span>
        <div class="grow">
          <p class="alert__title">Photographs help a lot</p>
          <p class="alert__text">
            A clear picture of the problem lets the officer bring the right tools on the first visit.
            This step is optional, but recommended.
          </p>
        </div>
      </div>
      <div id="uploader"></div>
    </div>`
}

function locationStep() {
  return '<div id="picker"></div>'
}

function aiStep() {
  return `
    <div class="stack">
      ${aiAnalysisCard({ analysis: draft.ai, loading: analysing, error: aiError })}
      <div id="dupes">${duplicateAlert(draft.duplicates, { detailsHref: DETAILS })}</div>
    </div>`
}

function reviewStep() {
  const files = draft.evidence.length
    ? draft.evidence
        .map(
          (file) =>
            `<li class="row" style="gap:.5rem">${icon('paperclip', 'icon-sm')}<span class="truncate">${esc(file.name)}</span><span class="muted">${esc(formatFileSize(file.size))}</span></li>`,
        )
        .join('')
    : '<li class="muted">No files attached</li>'

  return `
    <div class="stack">
      <div class="alert alert--info">
        <span class="alert__icon">${icon('info', 'icon-lg')}</span>
        <div class="grow">
          <p class="alert__title">Please check the details before submitting</p>
          <p class="alert__text">
            Once submitted, the complaint is sent to the department immediately and a reference
            number is generated.
          </p>
        </div>
      </div>

      <section class="card">
        <header class="card__head"><h2 class="card__title">Complaint summary</h2></header>
        <div class="card__body">
          <div class="info-list">
            ${infoRow('Title', esc(draft.title))}
            ${infoRow('Description', esc(draft.description))}
            ${infoRow('Category', esc(draft.category))}
            ${infoRow('Department', esc(draft.ai?.department ?? draft.department))}
            ${infoRow('Priority', draft.ai ? priorityBadge(draft.ai.priority) : '<span class="muted">Will be set on submission</span>')}
            ${infoRow('Location', esc(draft.location.address || '—'))}
            ${infoRow('Evidence', `<ul class="stack-sm" style="gap:.25rem">${files}</ul>`)}
          </div>
        </div>
      </section>

      <div class="split">
        <div>${draft.ai ? aiAnalysisCard({ analysis: draft.ai, readOnly: true }) : ''}</div>
        <section class="card">
          <header class="card__head"><h2 class="card__title">Location</h2></header>
          <div class="card__body">${mapPreview({ ...draft.location })}</div>
        </section>
      </div>
    </div>`
}

const RENDERERS = [detailsStep, evidenceStep, locationStep, aiStep, reviewStep]

/* ---------------------------------------------------------------- render */

function render() {
  qs('#form-card').innerHTML = `
    ${stepper()}
    <div class="card__body" id="step-body">${RENDERERS[step]()}</div>
    <footer class="card__foot" style="display:flex;justify-content:space-between;gap:var(--sp-3);flex-wrap:wrap">
      <button type="button" class="btn btn--secondary" data-back ${step === 0 ? 'disabled' : ''}>
        ${icon('arrow-left', 'icon-sm')}Back
      </button>
      ${
        step === STEPS.length - 1
          ? `<button type="button" class="btn btn--success btn--lg" data-submit>${icon('send', 'icon-md')}Submit complaint</button>`
          : `<button type="button" class="btn btn--primary" data-next>Continue${icon('arrow-right', 'icon-sm')}</button>`
      }
    </footer>`

  // Steps 2 and 3 own live widgets, so they are built after the markup exists.
  if (step === 1) {
    uploader = createFileUpload('#uploader', {
      onChange: (files) => {
        draft.evidence = files
      },
    })
    // Restore anything already chosen.
    if (draft.evidence.length && !uploader.files().length) {
      // createFileUpload starts empty; the draft keeps the previous selection
      // so re-entering the step shows it again.
      qs('#uploader [data-list]').innerHTML = draft.evidence
        .map(
          (file) => `<div class="file-row">
            <span class="file-row__icon">${icon('paperclip', 'icon-lg')}</span>
            <div class="grow"><p class="file-row__name truncate">${esc(file.name)}</p>
            <p class="file-row__meta">${esc(formatFileSize(file.size))}</p></div></div>`,
        )
        .join('')
    }
  }

  if (step === 2) {
    picker = createLocationPicker('#picker', {
      onChange: (value) => {
        draft.location = value
      },
    })
  }

  // The review step shows a read-only map of the captured point.
  if (step === 4) hydrateMaps(qs('#step-body'))

  // Category picks a sensible default department.
  if (step === 0) {
    on('#details-form', 'change', '#category', (event) => {
      const departmentSelect = qs('#department')
      if (!departmentSelect.value) {
        departmentSelect.value = CATEGORY_DEPARTMENT_MAP[event.target.value] ?? ''
      }
    })
  }
}

/* ------------------------------------------------------------ navigation */

/** Copy whatever is on screen into the draft before leaving a step. */
function captureStep() {
  if (step === 0) {
    const form = qs('#details-form')
    if (form) {
      draft.title = qs('#title', form).value.trim()
      draft.description = qs('#description', form).value.trim()
      draft.category = qs('#category', form).value
      draft.department = qs('#department', form).value
    }
  }
  if (step === 1 && uploader) draft.evidence = uploader.files()
  if (step === 2 && picker) draft.location = picker.value()
}

/** Returns true when the current step may be left. */
function validateStep() {
  if (step === 0) {
    const form = qs('#details-form')
    clearErrors(form)
    const errors = validateComplaintDetails(draft)
    if (!isValid(errors)) {
      showErrors(form, errors)
      return false
    }
  }

  if (step === 2) {
    const errors = validateLocation(draft.location)
    if (!isValid(errors)) {
      picker.setErrors(errors)
      toast.warning('Please capture the location and add a landmark.', 'Location required')
      return false
    }
  }

  if (step === 3 && !draft.ai) {
    toast.warning('Run the AI analysis so your complaint reaches the right department.', 'One step left')
    return false
  }

  return true
}

async function runAnalysis() {
  analysing = true
  aiError = ''
  render()

  try {
    const analysis = await analyseComplaint({
      title: draft.title,
      description: draft.description,
      category: draft.category,
    })
    draft.ai = analysis
    draft.duplicates = analysis.duplicates ?? []
    draft.department = analysis.department

    if (draft.duplicates.length) {
      toast.warning(
        `${draft.duplicates.length} similar complaint${draft.duplicates.length > 1 ? 's' : ''} found. Please review before submitting.`,
        'Possible duplicate',
      )
    } else {
      toast.success(`Routed to ${analysis.department} with ${analysis.priority} priority.`, 'Analysis complete')
    }
  } catch (error) {
    aiError = error.message
  } finally {
    analysing = false
    render()
  }
}

/* ---------------------------------------------------------------- submit */

function successView(complaint) {
  return `
    <div class="card anim-up" style="max-width:36rem;margin-inline:auto;text-align:center;padding:var(--sp-10) var(--sp-6)">
      <span class="success-mark">${icon('check-circle', 'icon-xl')}</span>

      <h1 style="font-size:var(--fs-xl);margin-top:var(--sp-5)">Complaint submitted successfully</h1>
      <p class="muted" style="margin-top:.5rem">
        Your complaint has been registered and sent to the department. Please note the reference
        number below.
      </p>

      <p class="reference" style="margin-top:var(--sp-6)">
        ${icon('clipboard-list', 'icon-md')}${esc(complaint.id)}
      </p>

      <div class="info-list" style="margin-top:var(--sp-6);text-align:left">
        ${infoRow('Department', esc(complaint.department))}
        ${infoRow('Priority', priorityBadge(complaint.priority))}
        ${infoRow('Expected resolution', esc(formatDate(complaint.deadline)))}
        ${infoRow(
          'Assigned officer',
          complaint.assignedOfficer
            ? esc(complaint.assignedOfficer.name)
            : '<span class="muted">Will be assigned shortly</span>',
        )}
      </div>

      <div class="row-wrap" style="justify-content:center;margin-top:var(--sp-8)">
        <a class="btn btn--primary btn--lg" href="${DETAILS}?id=${encodeURIComponent(complaint.id)}">
          ${icon('file-search', 'icon-md')}Track this complaint
        </a>
        <a class="btn btn--secondary btn--lg" href="/student/dashboard.html">Back to dashboard</a>
      </div>
    </div>`
}

async function submit(button) {
  setLoading(button, true, 'Submitting…')

  try {
    const complaint = await createComplaint(draft, user)

    await pushNotification({
      recipientId: user.id,
      type: NOTIFICATION_TYPES.SUBMITTED,
      title: 'Complaint registered successfully',
      message: `Your complaint "${complaint.title}" has been registered with reference ${complaint.id}.`,
      complaintId: complaint.id,
    })

    toast.success(`Reference number ${complaint.id}`, 'Complaint submitted')
    mount('#root', successView(complaint))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (error) {
    setLoading(button, false)
    toast.error(error.message, 'Could not submit the complaint')
  }
}

/* ------------------------------------------------------------------ boot */

ready(() => {
  user = requireRole(ROLES.STUDENT)
  if (!user) return

  renderShell(user, { title: 'Submit Complaint' })

  qs('#root').innerHTML = `
    ${pageHeader({
      title: 'Submit a complaint',
      lead: 'Five short steps. Your complaint reaches the right department automatically.',
      crumbs: [
        { label: 'Dashboard', href: '/student/dashboard.html' },
        { label: 'Submit Complaint' },
      ],
    })}
    <section class="card" id="form-card"></section>`

  render()

  const root = qs('#root')

  on(root, 'click', '[data-next]', () => {
    captureStep()
    if (!validateStep()) return
    step = Math.min(step + 1, STEPS.length - 1)
    render()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  })

  on(root, 'click', '[data-back]', () => {
    captureStep()
    step = Math.max(step - 1, 0)
    render()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  })

  on(root, 'click', '[data-run-ai]', () => {
    captureStep()
    if (!draft.title || draft.description.length < 25) {
      toast.warning('Go back to step 1 and complete the title and description first.', 'Not enough detail')
      return
    }
    runAnalysis()
  })

  on(root, 'click', '[data-continue-anyway]', () => {
    draft.duplicatesAcknowledged = true
    draft.duplicates = []
    render()
    toast.info('You can continue with your own complaint.', 'Duplicate check dismissed')
  })

  on(root, 'click', '[data-submit]', (event, button) => submit(button))
})
