/**
 * Geo-tagging step of the complaint form.
 *
 * "Use my current location" tries the browser Geolocation API first. Browsers
 * block it on plain http and it is often denied during a demonstration, so if
 * it is unavailable we fall back to a simulated point near the campus centre -
 * the prototype must always be demonstrable.
 *
 * A real fix from outside the campus is not usable either: this is a campus
 * grievance system, so the student is told to place the pin on campus instead
 * of silently filing a complaint against their home address.
 */

import { esc, icon, mount, on, qs, setLoading } from './dom.js'
import { hydrateMaps, mapPreview } from './complaintParts.js'
import { CAMPUS_CENTER } from '../utils/constants.js'
import { isInsideCampus } from '../utils/validators.js'

/** Known campus landmarks, so the simulated fix gets a sensible address. */
const LANDMARKS = [
  { address: 'Gayatri Bhavan, Hostel Zone A', block: 'Hostel Zone A' },
  { address: 'Academic Block C, Second Floor', block: 'Academic Zone' },
  { address: 'Shantikunj Bhavan, Computer Lab Wing', block: 'Computer Science Zone' },
  { address: 'Central Library, Ground Floor', block: 'Central Campus' },
  { address: 'Annapurna Bhavan, Dining Hall', block: 'Dining Zone' },
]

/**
 * @returns {{ value: Function, setErrors: Function }}
 */
export function createLocationPicker(container, { onChange = () => {} } = {}) {
  const node = typeof container === 'string' ? qs(container) : container

  let location = { latitude: null, longitude: null, address: '', block: '', accuracy: 0 }
  let source = null
  let errors = {}
  // Set when the device reported a real fix that fell outside the campus.
  let offCampus = false

  function render() {
    node.innerHTML = `
      <div class="alert alert--info" style="align-items:center;flex-wrap:wrap;gap:var(--sp-4)">
        <span class="alert__icon">${icon('map-pin', 'icon-lg')}</span>
        <div class="grow">
          <p class="alert__title">Tag the exact location</p>
          <p class="alert__text">Geo-tagging helps the department reach the right spot without asking you again.</p>
        </div>
        <button type="button" class="btn btn--primary" data-detect>
          ${icon('crosshair', 'icon-sm')}Use my current location
        </button>
      </div>

      ${
        offCampus
          ? `<div class="alert alert--warning" style="margin-top:var(--sp-3)">
              <span class="alert__icon">${icon('alert-circle', 'icon-lg')}</span>
              <div class="grow">
                <p class="alert__title">You are outside the DSVV campus</p>
                <p class="alert__text">Complaints can only be filed for locations inside the campus. Move the map pin to the spot you are reporting, or type the coordinates below.</p>
              </div>
            </div>`
          : ''
      }

      ${
        source && !offCampus
          ? `<p class="muted" style="margin-top:var(--sp-3)">${
              source === 'device'
                ? 'Location captured from your device GPS.'
                : 'Device location was not available, so a simulated campus location has been used for this prototype.'
            }</p>`
          : ''
      }

      <div class="grid grid-2" style="margin-top:var(--sp-5)">
        <div class="field" data-field="latitude">
          <label class="field__label" for="loc-lat">Latitude</label>
          <input type="number" step="0.000001" class="field__control" id="loc-lat" data-lat
                 value="${location.latitude ?? ''}" placeholder="29.999650">
        </div>
        <div class="field" data-field="longitude">
          <label class="field__label" for="loc-lng">Longitude</label>
          <input type="number" step="0.000001" class="field__control" id="loc-lng" data-lng
                 value="${location.longitude ?? ''}" placeholder="78.194600">
        </div>
      </div>

      <div class="field" data-field="address" style="margin-top:var(--sp-4)">
        <label class="field__label" for="loc-address">Location / landmark<span class="field__req">*</span></label>
        <input type="text" class="field__control" id="loc-address" data-address
               value="${esc(location.address)}"
               placeholder="e.g. Gayatri Bhavan, Room 214, Second Floor">
        <p class="field__hint">Mention the building, floor and room number so the officer can find the spot quickly.</p>
      </div>

      <div class="field" data-field="block" style="margin-top:var(--sp-4)">
        <label class="field__label" for="loc-block">Campus zone (optional)</label>
        <input type="text" class="field__control" id="loc-block" data-block
               value="${esc(location.block)}" placeholder="e.g. Hostel Zone A">
      </div>

      <div style="margin-top:var(--sp-5)">
        ${mapPreview({ ...location, tall: true })}
      </div>`

    applyErrors()
    // render() replaces the map node outright, so re-hydrate every time the
    // coordinates change.
    hydrateMaps(node)
  }

  function applyErrors() {
    Object.entries(errors).forEach(([field, message]) => {
      const wrap = qs(`[data-field="${field === 'location' ? 'latitude' : field}"]`, node)
      if (!wrap || !message) return
      qs('.field__control', wrap)?.classList.add('field__control--error')
      if (!qs('.field__error', wrap)) {
        wrap.insertAdjacentHTML(
          'beforeend',
          `<p class="field__error" role="alert">${icon('alert-circle', 'icon-sm')}${esc(message)}</p>`,
        )
      }
    })
  }

  function update(changes, redraw = true) {
    location = { ...location, ...changes }
    errors = {}
    if (redraw) render()
    onChange(location)
  }

  /**
   * Simulated fix used when the browser cannot give us a real one.
   *
   * The jitter is +/- 0.0015 deg (~165 m) around the campus centre, which keeps
   * every simulated point inside the campus outline - a demo point that failed
   * its own validation would be worse than no demo at all.
   */
  function simulate() {
    const landmark = LANDMARKS[Math.floor(Math.random() * LANDMARKS.length)]
    source = 'simulated'
    offCampus = false
    update({
      latitude: Number((CAMPUS_CENTER.latitude + (Math.random() - 0.5) * 0.003).toFixed(6)),
      longitude: Number((CAMPUS_CENTER.longitude + (Math.random() - 0.5) * 0.003).toFixed(6)),
      accuracy: Math.floor(6 + Math.random() * 14),
      address: location.address || landmark.address,
      block: location.block || landmark.block,
    })
  }

  function detect(button) {
    setLoading(button, true, 'Detecting…')

    if (!('geolocation' in navigator)) {
      simulate()
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const latitude = Number(position.coords.latitude.toFixed(6))
        const longitude = Number(position.coords.longitude.toFixed(6))

        // A genuine fix from off campus cannot be used as a complaint location.
        // Drop the pin on the campus centre instead and explain why, so the
        // student can drag it to the right spot rather than hitting a bare
        // validation error at submit time.
        if (!isInsideCampus(latitude, longitude)) {
          source = 'device'
          offCampus = true
          update({
            latitude: CAMPUS_CENTER.latitude,
            longitude: CAMPUS_CENTER.longitude,
            accuracy: 0,
          })
          return
        }

        source = 'device'
        offCampus = false
        update({ latitude, longitude, accuracy: Math.round(position.coords.accuracy) })
      },
      () => simulate(), // permission denied or unavailable - keep the demo working
      { enableHighAccuracy: true, timeout: 6000 },
    )
  }

  on(node, 'click', '[data-detect]', (event, button) => detect(button))

  // Typing should not redraw the panel, or the caret would jump on every key.
  on(node, 'input', '[data-address]', (event) => update({ address: event.target.value }, false))
  on(node, 'input', '[data-block]', (event) => update({ block: event.target.value }, false))
  // Typing coordinates by hand replaces whatever the GPS said, so the
  // off-campus notice from that fix no longer applies.
  on(node, 'change', '[data-lat]', (event) => {
    offCampus = false
    update({ latitude: event.target.value === '' ? null : Number(event.target.value) })
  })
  on(node, 'change', '[data-lng]', (event) => {
    offCampus = false
    update({ longitude: event.target.value === '' ? null : Number(event.target.value) })
  })

  render()

  return {
    value: () => location,
    setErrors: (next) => {
      errors = next
      render()
    },
  }
}

export default createLocationPicker
