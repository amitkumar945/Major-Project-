/**
 * Geo-tagging step of the complaint form.
 *
 * "Use my current location" tries the browser Geolocation API first. Browsers
 * block it on plain http and it is often denied during a demonstration, so if
 * it is unavailable we fall back to a simulated point near the campus centre -
 * the prototype must always be demonstrable.
 *
 * A real fix from outside the campus is not usable either: this is a campus
 * grievance system, so the student is told to retry from on campus instead of
 * silently filing a complaint against their home address.
 *
 * The latitude and longitude are deliberately NOT shown as editable number
 * fields. Students filing a complaint do not think in decimal degrees, and
 * asking them to type coordinates was the most confusing part of this step.
 * The values are still captured, validated against the campus outline and
 * submitted exactly as before - they are held in `location` below and simply
 * presented as a plain-language status line plus the map preview.
 */

import { esc, icon, mount, on, qs, setLoading } from './dom.js'
import { hydrateMaps, mapPreview } from './complaintParts.js'
import { CAMPUS_CENTER, CAMPUS_ZOOM } from '../utils/constants.js'
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

  /**
   * The line that replaces the old latitude / longitude inputs.
   *
   * It says, in ordinary words, whether we have a location yet and how good it
   * is. The exact coordinates are still shown by the map preview underneath
   * (`.map__coords`), so nothing is hidden from a user who wants to check -
   * they simply are not something to be typed in any more.
   */
  function statusPanel(captured) {
    if (offCampus) {
      return `
        <div class="locpick__state locpick__state--warn">
          <span class="locpick__state-icon">${icon('alert-circle', 'icon-md')}</span>
          <div>
            <p class="locpick__state-title">You seem to be outside the campus</p>
            <p class="locpick__state-text">
              Complaints can only be filed for places inside DSVV. Please try again when you are at
              the spot on campus, and describe the building below in the meantime.
            </p>
          </div>
        </div>`
    }

    if (!captured) {
      return `
        <div class="locpick__state">
          <span class="locpick__state-icon">${icon('crosshair', 'icon-md')}</span>
          <div>
            <p class="locpick__state-title">No location added yet</p>
            <p class="locpick__state-text">
              Use the button above, or just describe the building below - that alone is enough to
              file the complaint.
            </p>
          </div>
        </div>`
    }

    const accuracyNote = location.accuracy
      ? `Accurate to about ${location.accuracy} m.`
      : 'Pinned on the campus map.'

    return `
      <div class="locpick__state locpick__state--ok">
        <span class="locpick__state-icon">${icon('check-circle', 'icon-md')}</span>
        <div>
          <p class="locpick__state-title">Location added</p>
          <p class="locpick__state-text">
            ${
              source === 'device'
                ? `Picked up from your device. ${accuracyNote}`
                : `Your device location was not available, so a campus location has been used. ${accuracyNote}`
            }
          </p>
        </div>
      </div>`
  }

  function render() {
    const captured = location.latitude != null && location.longitude != null

    node.innerHTML = `
      <div class="locpick">
        <!-- Step 1: capture. One button, and a plain sentence saying why. -->
        <div class="locpick__capture">
          <span class="locpick__capture-icon">${icon('map-pin', 'icon-lg')}</span>
          <div class="locpick__capture-copy">
            <p class="locpick__capture-title">Where is the problem?</p>
            <p class="locpick__capture-text">
              Tap the button and we will pick up the spot automatically, so the officer can find it
              without calling you.
            </p>
          </div>
          <button type="button" class="btn ${captured ? 'btn--outline' : 'btn--primary'} locpick__btn"
                  data-detect>
            ${icon('crosshair', 'icon-sm')}${captured ? 'Update my location' : 'Use my current location'}
          </button>
        </div>

        <!-- Step 2: what we found, in words rather than coordinates. -->
        <div class="locpick__status" data-field="location">
          ${statusPanel(captured)}
        </div>

        <!-- Step 3: the map, and the landmark the officer actually reads. -->
        <div class="locpick__map">
          ${mapPreview({ ...location, tall: true })}
        </div>

        <div class="field" data-field="address">
          <label class="field__label" for="loc-address">Location / landmark<span class="field__req">*</span></label>
          <input type="text" class="field__control" id="loc-address" data-address
                 value="${esc(location.address)}"
                 placeholder="e.g. Gayatri Bhavan, Room 214, Second Floor">
          <p class="field__hint">Mention the building, floor and room number so the officer can find the spot quickly.</p>
        </div>

        <div class="field" data-field="block">
          <label class="field__label" for="loc-block">Campus zone (optional)</label>
          <input type="text" class="field__control" id="loc-block" data-block
                 value="${esc(location.block)}" placeholder="e.g. Hostel Zone A">
        </div>
      </div>`

    applyErrors()
    // render() replaces the map node outright, so re-hydrate every time the
    // coordinates change.
    hydrateMaps(node, { centerOnPoint: false, zoom: CAMPUS_ZOOM.default })
  }

  function applyErrors() {
    Object.entries(errors).forEach(([field, message]) => {
      // The `location` error used to be pinned to the latitude input. That
      // input is gone, so it now lands on the status panel, which is the block
      // that actually represents the captured point.
      const wrap = qs(`[data-field="${field}"]`, node)
      if (!wrap || !message) return
      qs('.field__control', wrap)?.classList.add('field__control--error')
      if (field === 'location') wrap.classList.add('locpick__status--error')
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

        // Keep the real fix intact; validateLocation() blocks moving forward
        // and the warning explains why it cannot be submitted.
        if (!isInsideCampus(latitude, longitude)) {
          source = 'device'
          offCampus = true
          update({
            latitude,
            longitude,
            accuracy: Math.round(position.coords.accuracy),
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
