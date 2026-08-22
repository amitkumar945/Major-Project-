/**
 * Small DOM toolkit.
 *
 * These few helpers are what replaces React in this project. Components are
 * plain functions that return an HTML string (or an element), and pages put
 * that HTML into the page with `mount`.
 *
 * The rule that keeps this safe: any value that came from a user or from the
 * data files must go through `esc()` before being placed inside a template
 * string, otherwise a quotation mark in a complaint description could break
 * the markup.
 */

/* ------------------------------------------------------------ selecting */

/** First element matching `selector`. */
export function qs(selector, scope = document) {
  return scope.querySelector(selector)
}

/** All elements matching `selector`, as a real array. */
export function qsa(selector, scope = document) {
  return [...scope.querySelectorAll(selector)]
}

/* ------------------------------------------------------------- escaping */

const ESCAPES = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

/** Make a value safe to drop inside an HTML template string. */
export function esc(value) {
  if (value == null) return ''
  return String(value).replace(/[&<>"']/g, (character) => ESCAPES[character])
}

/** Join template pieces, dropping null/false so conditionals read cleanly. */
export function html(...parts) {
  return parts.filter(Boolean).join('')
}

/* ------------------------------------------------------------- creating */

/**
 * Build an element from an HTML string.
 * `el('<p class="muted">Hello</p>')` -> HTMLParagraphElement
 */
export function el(markup) {
  const template = document.createElement('template')
  template.innerHTML = markup.trim()
  return template.content.firstElementChild
}

/** Replace the contents of `target` with `markup`. */
export function mount(target, markup) {
  const node = typeof target === 'string' ? qs(target) : target
  if (!node) return null
  node.innerHTML = markup
  return node
}

/** Append `markup` to the end of `target`. */
export function append(target, markup) {
  const node = typeof target === 'string' ? qs(target) : target
  if (!node) return null
  node.insertAdjacentHTML('beforeend', markup)
  return node.lastElementChild
}

/** Remove an element from the page. */
export function remove(node) {
  node?.parentNode?.removeChild(node)
}

/* --------------------------------------------------------------- events */

/**
 * Listen for an event.
 * Pass a `selector` to use delegation, which is how tables and lists respond
 * to clicks on rows that are re-rendered many times.
 *
 *   on(table, 'click', '[data-view]', (event, row) => ...)
 */
export function on(target, type, selectorOrHandler, maybeHandler) {
  const node = typeof target === 'string' ? qs(target) : target
  if (!node) return () => {}

  const delegated = typeof selectorOrHandler === 'string'
  const selector = delegated ? selectorOrHandler : null
  const handler = delegated ? maybeHandler : selectorOrHandler

  function listener(event) {
    if (!selector) return handler(event, node)
    const match = event.target.closest(selector)
    if (match && node.contains(match)) handler(event, match)
  }

  node.addEventListener(type, listener)
  return () => node.removeEventListener(type, listener)
}

/** Run `callback` once the document is ready. */
export function ready(callback) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', callback, { once: true })
  } else {
    callback()
  }
}

/* ---------------------------------------------------------------- icons */

/**
 * Reference an icon from the sprite in `assets/icons.svg`.
 * `icon('bell', 'icon-lg')` -> <svg class="icon icon-lg">…</svg>
 */
export function icon(name, extraClass = 'icon-md') {
  return `<svg class="icon ${esc(extraClass)}" aria-hidden="true"><use href="/assets/icons.svg#${esc(name)}"></use></svg>`
}

/* ----------------------------------------------------------- form input */

/** Read a whole form into a plain object. */
export function formValues(form) {
  const values = {}
  new FormData(form).forEach((value, key) => {
    values[key] = typeof value === 'string' ? value.trim() : value
  })
  // FormData omits unchecked boxes, so read them back explicitly.
  qsa('input[type="checkbox"]', form).forEach((box) => {
    values[box.name] = box.checked
  })
  return values
}

/**
 * Show validation messages produced by `utils/validators.js`.
 * Each field is expected to be wrapped in `[data-field="name"]`.
 */
export function showErrors(form, errors) {
  qsa('[data-field]', form).forEach((wrap) => {
    const name = wrap.dataset.field
    const control = qs('.field__control', wrap)
    const message = errors[name]

    qs('.field__error', wrap)?.remove()
    control?.classList.toggle('field__control--error', Boolean(message))
    control?.setAttribute('aria-invalid', message ? 'true' : 'false')

    if (message) {
      wrap.insertAdjacentHTML(
        'beforeend',
        `<p class="field__error" role="alert">${icon('alert-circle', 'icon-sm')}${esc(message)}</p>`,
      )
    }
  })

  // Move focus to the first problem so keyboard users are not stranded.
  const firstBad = qs('.field__control--error', form)
  firstBad?.focus()
}

/** Clear every validation message in a form. */
export function clearErrors(form) {
  qsa('.field__error', form).forEach((node) => node.remove())
  qsa('.field__control--error', form).forEach((node) => {
    node.classList.remove('field__control--error')
    node.setAttribute('aria-invalid', 'false')
  })
}

/** Put a button into (or out of) its loading state. */
export function setLoading(button, loading, label) {
  if (!button) return
  if (loading) {
    button.dataset.label = button.innerHTML
    button.disabled = true
    button.setAttribute('aria-busy', 'true')
    button.innerHTML = `<span class="spinner"></span>${esc(label ?? 'Please wait…')}`
  } else {
    button.disabled = false
    button.removeAttribute('aria-busy')
    if (button.dataset.label) button.innerHTML = button.dataset.label
  }
}

/* ------------------------------------------------------------ query bits */

/** Read the query string as a plain object. */
export function queryParams() {
  return Object.fromEntries(new URLSearchParams(location.search))
}

/** Update the query string without reloading the page. */
export function setQueryParams(params) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value != null && value !== false) search.set(key, value)
  })
  const query = search.toString()
  history.replaceState(null, '', query ? `?${query}` : location.pathname)
}

/** Root-relative prefix, so pages in sub-folders can link to each other. */
export const ROOT = '/'
