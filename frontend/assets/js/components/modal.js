/**
 * Dialogs.
 *
 * `openModal` shows any content; `confirmDialog` is the yes/no prompt used
 * before anything that is hard to undo - resolving a complaint, escalating it,
 * deleting a department, signing out.
 *
 * Both close on Escape and on a backdrop click, lock page scrolling while open,
 * and return focus to whatever was focused before.
 */

import { esc, icon, on, qs, qsa } from './dom.js'

let openCount = 0

/**
 * @param {object} options
 * @param {string} [options.title]
 * @param {string} [options.description]
 * @param {string} options.body      HTML for the dialog body
 * @param {string} [options.footer]  HTML for the button row
 * @param {'sm'|'md'|'lg'|'xl'} [options.size]
 * @param {boolean} [options.closeOnBackdrop]
 * @returns {{ element: HTMLElement, close: Function }}
 */
export function openModal({
  title = '',
  description = '',
  body = '',
  footer = '',
  size = 'md',
  closeOnBackdrop = true,
  onClose,
} = {}) {
  const previouslyFocused = document.activeElement

  const backdrop = document.createElement('div')
  backdrop.className = 'modal-backdrop'
  backdrop.innerHTML = `
    <div class="modal modal--${esc(size)}" role="dialog" aria-modal="true"
         ${title ? 'aria-labelledby="modal-title"' : ''} tabindex="-1">
      ${
        title
          ? `<header class="modal__head">
               <div class="grow">
                 <h2 class="modal__title" id="modal-title">${esc(title)}</h2>
                 ${description ? `<p class="modal__desc">${esc(description)}</p>` : ''}
               </div>
               <button type="button" class="btn-icon" data-close aria-label="Close dialog">
                 ${icon('x', 'icon-md')}
               </button>
             </header>`
          : ''
      }
      <div class="modal__body">${body}</div>
      ${footer ? `<footer class="modal__foot">${footer}</footer>` : ''}
    </div>`

  document.body.appendChild(backdrop)
  openCount += 1
  document.body.style.overflow = 'hidden'

  const panel = qs('.modal', backdrop)
  panel.focus()

  function close() {
    if (!backdrop.parentNode) return
    backdrop.remove()
    openCount = Math.max(openCount - 1, 0)
    if (openCount === 0) document.body.style.overflow = ''
    document.removeEventListener('keydown', handleKey)
    previouslyFocused?.focus?.()
    onClose?.()
  }

  function handleKey(event) {
    if (event.key === 'Escape') {
      close()
      return
    }
    // Keep Tab inside the dialog.
    if (event.key !== 'Tab') return
    const focusable = qsa(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      panel,
    )
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  document.addEventListener('keydown', handleKey)
  on(backdrop, 'click', '[data-close]', close)

  if (closeOnBackdrop) {
    backdrop.addEventListener('click', (event) => {
      if (event.target === backdrop) close()
    })
  }

  return { element: backdrop, panel, close }
}

const TONE_ICONS = {
  danger: 'trash',
  warning: 'alert-triangle',
  success: 'check-circle',
  info: 'help-circle',
}

/**
 * Yes/no prompt. Resolves to true when confirmed, false when cancelled.
 *
 *   if (await confirmDialog({ title: 'Resolve this complaint?' })) { … }
 */
export function confirmDialog({
  title,
  message = '',
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  tone = 'info',
  extraBody = '',
} = {}) {
  return new Promise((resolve) => {
    let settled = false

    const modal = openModal({
      size: 'sm',
      closeOnBackdrop: true,
      body: `
        <div class="confirm">
          <span class="confirm__icon confirm__icon--${esc(tone)}">${icon(TONE_ICONS[tone] ?? 'help-circle', 'icon-lg')}</span>
          <div class="grow">
            <h3 style="font-size:var(--fs-md)">${esc(title)}</h3>
            ${message ? `<p class="muted" style="margin-top:.375rem">${esc(message)}</p>` : ''}
            ${extraBody ? `<div style="margin-top:var(--sp-4)">${extraBody}</div>` : ''}
          </div>
        </div>`,
      footer: `
        <button type="button" class="btn btn--secondary" data-cancel>${esc(cancelLabel)}</button>
        <button type="button" class="btn btn--${tone === 'info' ? 'primary' : esc(tone)}" data-confirm>${esc(confirmLabel)}</button>`,
      onClose: () => {
        if (!settled) {
          settled = true
          resolve(false)
        }
      },
    })

    on(modal.element, 'click', '[data-cancel]', () => modal.close())
    on(modal.element, 'click', '[data-confirm]', () => {
      settled = true
      modal.close()
      resolve(true)
    })
  })
}

export default openModal
