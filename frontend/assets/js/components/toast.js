/**
 * Toast notifications.
 *
 * Any script can call `toast.success('Complaint submitted')`. The region is
 * created on first use, so no page has to include markup for it.
 */

import { esc, icon, on, qs } from './dom.js'

const ICONS = {
  success: 'check-circle',
  error: 'x-circle',
  warning: 'alert-triangle',
  info: 'info',
}

const DEFAULT_TITLES = {
  success: 'Success',
  error: 'Something went wrong',
  warning: 'Please note',
  info: 'Information',
}

let region = null

function getRegion() {
  if (region && document.body.contains(region)) return region
  region = qs('.toast-region')
  if (!region) {
    region = document.createElement('div')
    region.className = 'toast-region'
    region.setAttribute('role', 'status')
    region.setAttribute('aria-live', 'polite')
    document.body.appendChild(region)
  }
  return region
}

function show(variant, message, title) {
  const node = document.createElement('div')
  node.className = `toast toast--${variant}`
  node.innerHTML = `
    <span class="toast__icon">${icon(ICONS[variant], 'icon-lg')}</span>
    <div class="grow">
      <p class="toast__title">${esc(title ?? DEFAULT_TITLES[variant])}</p>
      <p class="toast__msg">${esc(message)}</p>
    </div>
    <button type="button" class="btn-icon" data-dismiss aria-label="Dismiss notification">
      ${icon('x', 'icon-sm')}
    </button>`

  getRegion().appendChild(node)

  const timer = setTimeout(() => dismiss(node), variant === 'error' ? 6000 : 4000)

  on(node, 'click', '[data-dismiss]', () => {
    clearTimeout(timer)
    dismiss(node)
  })

  return node
}

function dismiss(node) {
  if (!node?.parentNode) return
  node.style.opacity = '0'
  node.style.transform = 'translateX(16px)'
  node.style.transition = 'opacity .2s, transform .2s'
  setTimeout(() => node.remove(), 200)
}

export const toast = {
  success: (message, title) => show('success', message, title),
  error: (message, title) => show('error', message, title),
  warning: (message, title) => show('warning', message, title),
  info: (message, title) => show('info', message, title),
}

export default toast
