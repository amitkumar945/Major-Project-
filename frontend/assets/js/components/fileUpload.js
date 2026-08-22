/**
 * Evidence upload with drag & drop, validation and image previews.
 *
 * Files never leave the browser in this prototype. Image previews use
 * `URL.createObjectURL`, and those URLs are released when a file is removed so
 * the page does not leak memory.
 *
 * When the Flask API is connected, the collected `File` objects are what a
 * `FormData` upload to `POST /api/complaints/:id/evidence` would send.
 */

import { esc, icon, on, qs } from './dom.js'
import { UPLOAD_LIMITS } from '../utils/constants.js'
import { formatFileSize, uid } from '../utils/helpers.js'

const KIND_ICONS = { image: 'image', pdf: 'file-text', doc: 'paperclip' }

/** Group a MIME type into the three kinds the interface cares about. */
function kindOf(file) {
  if (file.type.startsWith('image/')) return 'image'
  if (file.type === 'application/pdf') return 'pdf'
  return 'doc'
}

/**
 * Create an uploader inside `container`.
 *
 * @returns {{ files: Function, clear: Function }} `files()` returns the current list
 */
export function createFileUpload(container, {
  maxFiles = UPLOAD_LIMITS.maxFiles,
  maxSizeMB = UPLOAD_LIMITS.maxSizeMB,
  accept = UPLOAD_LIMITS.accept,
  label = 'Upload photographs or documents',
  onChange = () => {},
} = {}) {
  const node = typeof container === 'string' ? qs(container) : container
  let files = []
  let problems = []

  node.innerHTML = `
    <label class="field__label" for="evidence-input">${esc(label)}</label>

    <div class="dropzone" data-dropzone>
      <input type="file" id="evidence-input" class="sr-only" multiple accept="${esc(accept)}">
      <span class="dropzone__icon">${icon('upload-cloud', 'icon-xl')}</span>
      <p style="margin-top:var(--sp-3)">
        <button type="button" class="btn--link" data-browse style="font-weight:600">Click to browse</button>
        or drag and drop your files here
      </p>
      <p class="muted" style="font-size:var(--fs-xs);margin-top:.25rem" data-hint>
        JPG, PNG, WEBP, PDF or DOC · up to ${maxSizeMB} MB each · maximum ${maxFiles} files
      </p>
    </div>

    <ul data-errors role="alert" style="margin-top:var(--sp-2)"></ul>
    <div class="file-list" data-list></div>`

  const input = qs('#evidence-input', node)
  const dropzone = qs('[data-dropzone]', node)
  const list = qs('[data-list]', node)
  const errorBox = qs('[data-errors]', node)

  function renderErrors() {
    errorBox.innerHTML = problems
      .map((problem) => `<li class="field__error">${icon('alert-circle', 'icon-sm')}${esc(problem)}</li>`)
      .join('')
  }

  function renderList() {
    dropzone.classList.toggle('is-full', files.length >= maxFiles)
    input.disabled = files.length >= maxFiles

    list.innerHTML = files
      .map((item) => `
        <div class="file-row" data-file="${esc(item.id)}">
          ${
            item.url
              ? `<img class="file-row__thumb" src="${esc(item.url)}" alt="Preview of ${esc(item.name)}">`
              : `<span class="file-row__icon">${icon(KIND_ICONS[item.kind] ?? 'paperclip', 'icon-lg')}</span>`
          }
          <div class="grow" style="min-width:0">
            <p class="file-row__name truncate">${esc(item.name)}</p>
            <p class="file-row__meta">${esc(item.kind.toUpperCase())} · ${esc(formatFileSize(item.size))}</p>
          </div>
          <button type="button" class="btn-icon btn-icon--danger" data-remove="${esc(item.id)}"
                  aria-label="Remove ${esc(item.name)}">${icon('trash', 'icon-md')}</button>
        </div>`)
      .join('')
  }

  function addFiles(fileList) {
    problems = []
    const accepted = []

    ;[...fileList].forEach((file) => {
      if (files.length + accepted.length >= maxFiles) {
        problems.push(`Only ${maxFiles} files can be attached to one complaint.`)
        return
      }
      if (file.size > maxSizeMB * 1024 * 1024) {
        problems.push(`"${file.name}" is larger than ${maxSizeMB} MB.`)
        return
      }
      if (files.some((existing) => existing.name === file.name && existing.size === file.size)) {
        problems.push(`"${file.name}" has already been attached.`)
        return
      }

      const kind = kindOf(file)
      accepted.push({
        id: uid('file'),
        name: file.name,
        size: file.size,
        type: file.type,
        kind,
        url: kind === 'image' ? URL.createObjectURL(file) : null,
        file, // kept so a real upload can send it later
      })
    })

    if (accepted.length) files = [...files, ...accepted]

    renderErrors()
    renderList()
    onChange(files)
  }

  function removeFile(id) {
    const target = files.find((item) => item.id === id)
    if (target?.url) URL.revokeObjectURL(target.url)
    files = files.filter((item) => item.id !== id)
    problems = []
    renderErrors()
    renderList()
    onChange(files)
  }

  on(node, 'click', '[data-browse]', () => input.click())
  on(node, 'click', '[data-remove]', (event, button) => removeFile(button.dataset.remove))

  input.addEventListener('change', () => {
    addFiles(input.files)
    input.value = '' // allow re-selecting the same file
  })

  dropzone.addEventListener('dragover', (event) => {
    event.preventDefault()
    dropzone.classList.add('is-dragging')
  })
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('is-dragging'))
  dropzone.addEventListener('drop', (event) => {
    event.preventDefault()
    dropzone.classList.remove('is-dragging')
    if (event.dataTransfer.files?.length) addFiles(event.dataTransfer.files)
  })

  renderList()

  return {
    files: () => files,
    clear: () => {
      files.forEach((item) => item.url && URL.revokeObjectURL(item.url))
      files = []
      renderList()
      onChange(files)
    },
  }
}

export default createFileUpload
