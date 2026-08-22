/**
 * Leaflet + OpenStreetMap rendering for geo-tagged complaints.
 *
 * The rest of the app must keep working with no internet connection, so Leaflet
 * is loaded lazily from the CDN and every entry point degrades to the inline-SVG
 * `mapPreview()` placeholder when the library cannot be fetched. Nothing here
 * throws: a failed map is a cosmetic downgrade, never a broken page.
 */

import { esc } from './dom.js'
import { CAMPUS_CENTER } from '../utils/constants.js'

const LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
const LEAFLET_JS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'

const TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
const TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

/** Marker colours per priority, so the admin map reads at a glance. */
const PRIORITY_COLORS = {
  Critical: '#dc2626',
  High: '#ea580c',
  Medium: '#ca8a04',
  Low: '#16a34a',
}

let loader = null

/**
 * Load Leaflet once and share the promise. Resolves with `L`, or rejects when
 * the CDN is unreachable (offline demo, blocked network).
 */
export function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L)
  if (loader) return loader

  loader = new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
      const link = document.createElement('link')
      link.rel = 'stylesheet'
      link.href = LEAFLET_CSS
      document.head.appendChild(link)
    }

    const script = document.createElement('script')
    script.src = LEAFLET_JS
    script.async = true
    script.onload = () => (window.L ? resolve(window.L) : reject(new Error('Leaflet failed to initialise')))
    script.onerror = () => reject(new Error('Leaflet could not be loaded'))
    document.head.appendChild(script)
  })

  // A failed load must not poison later attempts.
  loader.catch(() => {
    loader = null
  })

  return loader
}

/** Teardown-safe: Leaflet complains if a container is initialised twice. */
function resetContainer(node) {
  if (node._leafletMap) {
    node._leafletMap.remove()
    node._leafletMap = null
  }
  node.innerHTML = ''
}

/** Coloured teardrop marker, built as a divIcon so no image assets are needed. */
function pinIcon(L, color = PRIORITY_COLORS.Medium) {
  return L.divIcon({
    className: 'leaflet-pin',
    html: `<span class="leaflet-pin__dot" style="background:${color}"></span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    popupAnchor: [0, -12],
  })
}

function hasPoint(location) {
  return location && location.latitude != null && location.longitude != null
}

/**
 * Render a single complaint location.
 *
 * @param {HTMLElement} node        container to render into
 * @param {object}      location    { latitude, longitude, address, accuracy }
 * @param {object}      options     { zoom, interactive, onFail }
 * @returns {Promise<object|null>}  the Leaflet map, or null when unavailable
 */
export async function renderLocationMap(node, location, { zoom = 17, interactive = true, onFail } = {}) {
  if (!node || !hasPoint(location)) return null

  let L
  try {
    L = await loadLeaflet()
  } catch {
    onFail?.()
    return null
  }

  // Keep the placeholder markup so it can be restored if Leaflet throws.
  const fallback = node.innerHTML
  resetContainer(node)

  try {
    const point = [Number(location.latitude), Number(location.longitude)]
    const map = L.map(node, {
      center: point,
      zoom,
      scrollWheelZoom: false, // page scrolling wins until the user clicks in
      dragging: interactive,
      zoomControl: interactive,
      attributionControl: true,
    })

    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map)

    // The GPS accuracy radius, drawn only when the device reported one.
    if (location.accuracy) {
      L.circle(point, {
        radius: Number(location.accuracy),
        color: '#4f46e5',
        weight: 1,
        fillColor: '#4f46e5',
        fillOpacity: 0.15,
      }).addTo(map)
    }

    const marker = L.marker(point, { icon: pinIcon(L, PRIORITY_COLORS.Critical) }).addTo(map)
    if (location.address) marker.bindPopup(`<strong>${esc(location.address)}</strong>`)

    // Leaflet mis-sizes tiles inside cards that animate or start hidden.
    setTimeout(() => map.invalidateSize(), 0)

    node._leafletMap = map
    return map
  } catch {
    node.innerHTML = fallback
    onFail?.()
    return null
  }
}

/**
 * Render many complaints as pins on one map - the admin "Map view".
 *
 * @param {HTMLElement} node        container to render into
 * @param {Array}       complaints  complaints carrying a `location`
 * @param {object}      options     { onSelect, onFail }
 * @returns {Promise<object|null>}
 */
export async function renderComplaintsMap(node, complaints = [], { onSelect, onFail } = {}) {
  if (!node) return null

  const tagged = complaints.filter((complaint) => hasPoint(complaint.location))

  let L
  try {
    L = await loadLeaflet()
  } catch {
    onFail?.()
    return null
  }

  const fallback = node.innerHTML
  resetContainer(node)

  try {
    const map = L.map(node, {
      center: [CAMPUS_CENTER.latitude, CAMPUS_CENTER.longitude],
      zoom: 16,
      scrollWheelZoom: false,
    })

    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(map)

    const markers = tagged.map((complaint) => {
      const { latitude, longitude, address } = complaint.location
      const marker = L.marker([Number(latitude), Number(longitude)], {
        icon: pinIcon(L, PRIORITY_COLORS[complaint.priority] || PRIORITY_COLORS.Medium),
      }).addTo(map)

      // Complaint text is user-written, so it is escaped before it reaches
      // the popup's innerHTML.
      marker.bindPopup(
        `<strong>${esc(complaint.referenceId || complaint.id)}</strong><br>` +
          `${esc(complaint.title || '')}<br>` +
          `<span style="color:#64748b">${esc(address || '')}</span>`,
      )

      if (onSelect) marker.on('click', () => onSelect(complaint))
      return marker
    })

    // Frame every pin; a lone pin would otherwise zoom to maximum.
    if (markers.length > 1) {
      map.fitBounds(L.featureGroup(markers).getBounds().pad(0.2))
    } else if (markers.length === 1) {
      map.setView(markers[0].getLatLng(), 17)
    }

    setTimeout(() => map.invalidateSize(), 0)

    node._leafletMap = map
    return map
  } catch {
    node.innerHTML = fallback
    onFail?.()
    return null
  }
}

export default { loadLeaflet, renderLocationMap, renderComplaintsMap }
