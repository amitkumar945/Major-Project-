/**
 * Leaflet + OpenStreetMap rendering for geo-tagged complaints.
 *
 * The rest of the app must keep working with no internet connection, so Leaflet
 * is loaded lazily from the CDN and every entry point degrades to the inline-SVG
 * `mapPreview()` placeholder when the library cannot be fetched. Nothing here
 * throws: a failed map is a cosmetic downgrade, never a broken page.
 */

import { esc } from './dom.js'
import { CAMPUS_BOUNDS, CAMPUS_CENTER, CAMPUS_POLYGON, CAMPUS_ZOOM } from '../utils/constants.js'

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
 * Options every map on the site shares, so none of them can wander off campus.
 *
 * `maxBounds` keeps panning inside the padded campus box and
 * `maxBoundsViscosity: 1.0` makes that edge solid rather than elastic, while
 * `minZoom` stops the user from zooming out to the district, the state or the
 * whole of India. This is a campus grievance system: nothing outside the fence
 * is ever a valid view.
 */
function campusMapOptions(L) {
  return {
    maxBounds: L.latLngBounds(
      [CAMPUS_BOUNDS.minLatitude, CAMPUS_BOUNDS.minLongitude],
      [CAMPUS_BOUNDS.maxLatitude, CAMPUS_BOUNDS.maxLongitude],
    ),
    maxBoundsViscosity: 1.0,
    minZoom: CAMPUS_ZOOM.min,
    maxZoom: CAMPUS_ZOOM.max,
  }
}

/**
 * Draw the real campus outline (OSM way/1152422760) so the viewer can see what
 * counts as "on campus". Purely decorative - a failure here must not take the
 * map down with it.
 */
function addCampusBoundary(L, map) {
  try {
    return L.polygon(CAMPUS_POLYGON, {
      color: '#4f46e5',
      weight: 2,
      opacity: 0.65,
      fillColor: '#4f46e5',
      fillOpacity: 0.05,
      interactive: false,
    }).addTo(map)
  } catch {
    return null
  }
}

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
 * Is this point actually on campus?
 *
 * `maxBounds` constrains panning, but `fitBounds()` ignores it entirely - it
 * frames whatever markers it is given. Older complaints stored before the
 * campus check existed can sit anywhere on earth, and a single such pin drags
 * the view out to the country or the globe. Framing is therefore restricted to
 * points that fall inside the padded campus box.
 *
 * The pin itself is still drawn: this decides what the map zooms to, never
 * what it shows.
 */
function isOnCampus(location) {
  if (!hasPoint(location)) return false
  const latitude = Number(location.latitude)
  const longitude = Number(location.longitude)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return false

  return (
    latitude >= CAMPUS_BOUNDS.minLatitude &&
    latitude <= CAMPUS_BOUNDS.maxLatitude &&
    longitude >= CAMPUS_BOUNDS.minLongitude &&
    longitude <= CAMPUS_BOUNDS.maxLongitude
  )
}

/**
 * Render a single complaint location.
 *
 * @param {HTMLElement} node        container to render into
 * @param {object}      location    { latitude, longitude, address, accuracy }
 * @param {object}      options     { zoom, interactive, onFail }
 * @returns {Promise<object|null>}  the Leaflet map, or null when unavailable
 */
export async function renderLocationMap(node, location, { zoom = CAMPUS_ZOOM.point, interactive = true, onFail } = {}) {
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
    // Centre on the complaint only when it is on campus. A point stored before
    // the campus check existed would otherwise open the map outside `maxBounds`
    // - the map immediately fights back to the boundary, which is the "wrong
    // place / zoomed out" view. The DSVV centre is the safe fallback.
    const onCampus = isOnCampus(location)
    const centre = onCampus ? point : [CAMPUS_CENTER.latitude, CAMPUS_CENTER.longitude]
    const map = L.map(node, {
      ...campusMapOptions(L),
      center: centre,
      zoom,
      scrollWheelZoom: false, // page scrolling wins until the user clicks in
      dragging: interactive,
      zoomControl: interactive,
      attributionControl: true,
    })

    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: CAMPUS_ZOOM.max }).addTo(map)
    addCampusBoundary(L, map)

    // The pin and its accuracy ring are drawn only for a point that is really
    // on campus. An older complaint stored before the campus check existed can
    // sit hundreds or thousands of kilometres away; drawing it there would put
    // the marker outside every view `maxBounds` allows, leaving what looks like
    // an empty map. The complaint itself is untouched and still shows its
    // stored coordinates in the details panel beside this map.
    if (onCampus) {
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
    }

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

  // Only complaints that are actually on campus get a pin. Leaflet's
  // `maxBounds` limits panning, not rendering, so a marker stored thousands of
  // kilometres away is still drawn - it just sits outside every reachable view,
  // which is what made the map look wrong. Filtering here means such a marker
  // is never created in the first place.
  //
  // This changes DISPLAY ONLY: the complaint keeps its stored coordinates and
  // stays fully visible in the lists, tables and its own details page.
  const tagged = complaints.filter((complaint) => isOnCampus(complaint.location))

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
      ...campusMapOptions(L),
      center: [CAMPUS_CENTER.latitude, CAMPUS_CENTER.longitude],
      zoom: CAMPUS_ZOOM.default,
      scrollWheelZoom: false,
    })

    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: CAMPUS_ZOOM.max }).addTo(map)
    addCampusBoundary(L, map)

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
      // Re-checked rather than assumed, so the framing guard below stays a
      // genuine second check instead of trusting the filter above.
      marker._campusPoint = isOnCampus(complaint.location)
      return marker
    })

    // Frame the pins. `markers` only ever holds on-campus points now, because
    // `tagged` was filtered above - but the guard is kept anyway: `fitBounds`
    // overrides `maxBounds`, so a single stray point reaching this line would
    // pull the view out to the country or the globe. Two independent checks
    // are cheap; one silent regression here is not.
    //
    // `maxZoom` keeps a tight cluster from zooming past the campus, and with
    // no valid pins at all nothing is called, so the map simply keeps the DSVV
    // centre and campus zoom it opened with.
    const framing = markers.filter((marker) => marker._campusPoint)

    if (framing.length > 1) {
      map.fitBounds(L.featureGroup(framing).getBounds().pad(0.2), { maxZoom: CAMPUS_ZOOM.point })
    } else if (framing.length === 1) {
      map.setView(framing[0].getLatLng(), CAMPUS_ZOOM.point)
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

export default { loadLeaflet, renderLocationMap, renderComplaintsMap, addCampusBoundary }
