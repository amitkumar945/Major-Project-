/**
 * Charts, drawn as plain SVG.
 *
 * No charting library is used. Each function below works out the geometry and
 * returns an <svg> string, which keeps the project dependency-free and makes
 * the maths visible and explainable.
 *
 * Colours come from `utils/chartTheme.js`. They were checked for
 * colour-vision-deficiency separation, and every chart also ships a legend and
 * a table view, so no information is carried by colour alone.
 */

import { esc, html, icon, on, qs, qsa } from './dom.js'
import { AXIS_PROPS, CHART_INK, SERIES } from '../utils/chartTheme.js'

/* ------------------------------------------------------------- helpers --- */

/** Round to at most 2 decimals so the SVG source stays readable. */
const n = (value) => Math.round(value * 100) / 100

/** A "nice" upper bound for an axis: 7 -> 8, 23 -> 25, 260 -> 300. */
function niceMax(value) {
  if (value <= 5) return 5
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const scaled = value / magnitude
  const step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 2.5 ? 2.5 : scaled <= 5 ? 5 : 10
  return Math.ceil(value / (step * magnitude / 5)) * (step * magnitude / 5)
}

/** Evenly spaced tick values from 0 to max. */
function ticks(max, count = 4) {
  return Array.from({ length: count + 1 }, (_, index) => n((max / count) * index))
}

/** Shorten a long category label so it fits on an axis. */
function shorten(label, limit = 16) {
  return label.length > limit ? `${label.slice(0, limit - 1)}…` : label
}

/* ========================================================== DONUT CHART === */

/** Point on a circle, angle measured clockwise from 12 o'clock. */
function polar(cx, cy, radius, angle) {
  const radians = ((angle - 90) * Math.PI) / 180
  return [n(cx + radius * Math.cos(radians)), n(cy + radius * Math.sin(radians))]
}

/** SVG path for one ring segment. */
function arc(cx, cy, outer, inner, start, end) {
  const [ox1, oy1] = polar(cx, cy, outer, start)
  const [ox2, oy2] = polar(cx, cy, outer, end)
  const [ix1, iy1] = polar(cx, cy, inner, end)
  const [ix2, iy2] = polar(cx, cy, inner, start)
  const large = end - start > 180 ? 1 : 0

  return [
    `M ${ox1} ${oy1}`,
    `A ${outer} ${outer} 0 ${large} 1 ${ox2} ${oy2}`,
    `L ${ix1} ${iy1}`,
    `A ${inner} ${inner} 0 ${large} 0 ${ix2} ${iy2}`,
    'Z',
  ].join(' ')
}

/**
 * Ring chart with the total in the middle.
 * @param {{name: string, value: number, color: string}[]} data
 */
export function donutChart(data, { centerLabel = 'Complaints' } = {}) {
  const total = data.reduce((sum, entry) => sum + entry.value, 0)
  if (!total) return ''

  const size = 240
  const cx = size / 2
  const cy = size / 2
  const outer = 92
  const inner = 62
  const gap = 2 // degrees of surface showing between segments

  let angle = 0
  const segments = data
    .map((entry) => {
      const sweep = (entry.value / total) * 360
      const start = angle + (data.length > 1 ? gap / 2 : 0)
      const end = angle + sweep - (data.length > 1 ? gap / 2 : 0)
      angle += sweep

      if (end <= start) return ''
      const percent = Math.round((entry.value / total) * 100)

      return `<path class="chart__slice" d="${arc(cx, cy, outer, inner, start, end)}"
                fill="${esc(entry.color)}"
                data-tip="${esc(entry.name)}|${entry.value}|${percent}%"
                tabindex="0" role="img"
                aria-label="${esc(entry.name)}: ${entry.value} complaints, ${percent} percent"></path>`
    })
    .join('')

  return `
    <div class="chart">
      <svg viewBox="0 0 ${size} ${size}" style="max-height:240px" role="group">
        ${segments}
        <text class="chart__center-value" x="${cx}" y="${cy - 2}" text-anchor="middle">${total}</text>
        <text class="chart__center-label" x="${cx}" y="${cy + 16}" text-anchor="middle">${esc(centerLabel)}</text>
      </svg>
    </div>`
}

/* ==================================================== HORIZONTAL BARS ===== */

/**
 * Horizontal bar chart - used when category names are long.
 * @param {{name: string, value: number, color?: string}[]} data
 */
export function barChartH(data, { color = SERIES.primary, unit = '' } = {}) {
  if (!data.length) return ''

  const rowHeight = 38
  const barHeight = 18
  const labelWidth = 132
  const valueWidth = 44
  const width = 520
  const height = data.length * rowHeight + 24
  const plotWidth = width - labelWidth - valueWidth

  const max = niceMax(Math.max(...data.map((entry) => entry.value), 1))

  const gridLines = ticks(max, 4)
    .map((tick) => {
      const x = n(labelWidth + (tick / max) * plotWidth)
      return `<line class="chart__grid" x1="${x}" y1="8" x2="${x}" y2="${height - 20}"></line>
              <text class="chart__tick" x="${x}" y="${height - 6}" text-anchor="middle">${tick}</text>`
    })
    .join('')

  const bars = data
    .map((entry, index) => {
      const y = 16 + index * rowHeight
      const barWidth = Math.max(n((entry.value / max) * plotWidth), entry.value > 0 ? 3 : 0)
      return `
        <text class="chart__tick" x="${labelWidth - 10}" y="${y + barHeight / 2 + 4}" text-anchor="end">${esc(shorten(entry.name))}</text>
        <rect class="chart__bar" x="${labelWidth}" y="${y}" width="${barWidth}" height="${barHeight}"
              rx="4" fill="${esc(entry.color ?? color)}"
              data-tip="${esc(entry.name)}|${entry.value}${esc(unit)}"
              tabindex="0" role="img"
              aria-label="${esc(entry.name)}: ${entry.value}${esc(unit)}"></rect>
        <text class="chart__value" x="${labelWidth + barWidth + 8}" y="${y + barHeight / 2 + 4}">${entry.value}${esc(unit)}</text>`
    })
    .join('')

  return `
    <div class="chart">
      <svg viewBox="0 0 ${width} ${height}" role="group">
        ${gridLines}
        <line class="chart__axis" x1="${labelWidth}" y1="8" x2="${labelWidth}" y2="${height - 20}"></line>
        ${bars}
      </svg>
    </div>`
}

/* ====================================================== VERTICAL BARS ===== */

/**
 * Column chart - used for short labels such as priorities or weekdays.
 * @param {{name: string, value: number, color?: string}[]} data
 */
export function barChartV(data, { color = SERIES.primary, unit = '' } = {}) {
  if (!data.length) return ''

  const width = 520
  const height = 240
  const padLeft = 40
  const padBottom = 34
  const padTop = 16
  const plotWidth = width - padLeft - 16
  const plotHeight = height - padTop - padBottom

  const max = niceMax(Math.max(...data.map((entry) => entry.value), 1))
  const slot = plotWidth / data.length
  const barWidth = Math.min(slot * 0.55, 46)

  const gridLines = ticks(max, 4)
    .map((tick) => {
      const y = n(padTop + plotHeight - (tick / max) * plotHeight)
      return `<line class="chart__grid" x1="${padLeft}" y1="${y}" x2="${width - 16}" y2="${y}"></line>
              <text class="chart__tick" x="${padLeft - 8}" y="${y + 4}" text-anchor="end">${tick}</text>`
    })
    .join('')

  const bars = data
    .map((entry, index) => {
      const barHeight = n((entry.value / max) * plotHeight)
      const x = n(padLeft + slot * index + (slot - barWidth) / 2)
      const y = n(padTop + plotHeight - barHeight)
      return `
        <rect class="chart__bar" x="${x}" y="${y}" width="${n(barWidth)}" height="${Math.max(barHeight, entry.value > 0 ? 3 : 0)}"
              rx="4" fill="${esc(entry.color ?? color)}"
              data-tip="${esc(entry.name)}|${entry.value}${esc(unit)}"
              tabindex="0" role="img"
              aria-label="${esc(entry.name)}: ${entry.value}${esc(unit)}"></rect>
        <text class="chart__value" x="${n(x + barWidth / 2)}" y="${y - 6}" text-anchor="middle">${entry.value}</text>
        <text class="chart__tick" x="${n(x + barWidth / 2)}" y="${height - 12}" text-anchor="middle">${esc(shorten(entry.name, 10))}</text>`
    })
    .join('')

  return `
    <div class="chart">
      <svg viewBox="0 0 ${width} ${height}" role="group">
        ${gridLines}
        <line class="chart__axis" x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${padTop + plotHeight}"></line>
        <line class="chart__axis" x1="${padLeft}" y1="${padTop + plotHeight}" x2="${width - 16}" y2="${padTop + plotHeight}"></line>
        ${bars}
      </svg>
    </div>`
}

/* ============================================================ GROUPED ===== */

/**
 * Two bars side by side per category - "assigned vs resolved".
 * @param {string[]} labels
 * @param {{name: string, color: string, values: number[]}[]} series
 */
export function groupedBars(labels, series) {
  if (!labels.length) return ''

  const width = 560
  const height = 250
  const padLeft = 44
  const padBottom = 36
  const padTop = 16
  const plotWidth = width - padLeft - 16
  const plotHeight = height - padTop - padBottom

  const max = niceMax(Math.max(...series.flatMap((entry) => entry.values), 1))
  const slot = plotWidth / labels.length
  const barWidth = Math.min((slot * 0.7) / series.length, 24)

  const gridLines = ticks(max, 4)
    .map((tick) => {
      const y = n(padTop + plotHeight - (tick / max) * plotHeight)
      return `<line class="chart__grid" x1="${padLeft}" y1="${y}" x2="${width - 16}" y2="${y}"></line>
              <text class="chart__tick" x="${padLeft - 8}" y="${y + 4}" text-anchor="end">${tick}</text>`
    })
    .join('')

  const groups = labels
    .map((label, index) => {
      const groupWidth = barWidth * series.length + 2 * (series.length - 1)
      const startX = padLeft + slot * index + (slot - groupWidth) / 2

      const bars = series
        .map((entry, seriesIndex) => {
          const value = entry.values[index] ?? 0
          const barHeight = n((value / max) * plotHeight)
          const x = n(startX + seriesIndex * (barWidth + 2))
          const y = n(padTop + plotHeight - barHeight)
          return `<rect class="chart__bar" x="${x}" y="${y}" width="${n(barWidth)}"
                    height="${Math.max(barHeight, value > 0 ? 2 : 0)}" rx="3" fill="${esc(entry.color)}"
                    data-tip="${esc(label)}|${esc(entry.name)}: ${value}"
                    tabindex="0" role="img" aria-label="${esc(label)}, ${esc(entry.name)}: ${value}"></rect>`
        })
        .join('')

      return `${bars}
        <text class="chart__tick" x="${n(padLeft + slot * index + slot / 2)}" y="${height - 12}"
              text-anchor="middle">${esc(shorten(label, 11))}</text>`
    })
    .join('')

  return `
    <div class="chart">
      <svg viewBox="0 0 ${width} ${height}" role="group">
        ${gridLines}
        <line class="chart__axis" x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${padTop + plotHeight}"></line>
        <line class="chart__axis" x1="${padLeft}" y1="${padTop + plotHeight}" x2="${width - 16}" y2="${padTop + plotHeight}"></line>
        ${groups}
      </svg>
    </div>`
}

/* =============================================================== LINES ===== */

/**
 * Line chart with a soft area fill under the first series.
 * @param {string[]} labels
 * @param {{name: string, color: string, values: number[]}[]} series
 */
export function lineChart(labels, series) {
  if (!labels.length) return ''

  const width = 620
  const height = 250
  const padLeft = 40
  const padBottom = 34
  const padTop = 16
  const padRight = 14
  const plotWidth = width - padLeft - padRight
  const plotHeight = height - padTop - padBottom

  const max = niceMax(Math.max(...series.flatMap((entry) => entry.values), 1))
  const stepX = labels.length > 1 ? plotWidth / (labels.length - 1) : 0

  const pointAt = (index, value) => [
    n(padLeft + stepX * index),
    n(padTop + plotHeight - (value / max) * plotHeight),
  ]

  const gridLines = ticks(max, 4)
    .map((tick) => {
      const y = n(padTop + plotHeight - (tick / max) * plotHeight)
      return `<line class="chart__grid" x1="${padLeft}" y1="${y}" x2="${width - padRight}" y2="${y}"></line>
              <text class="chart__tick" x="${padLeft - 8}" y="${y + 4}" text-anchor="end">${tick}</text>`
    })
    .join('')

  const xLabels = labels
    .map((label, index) => {
      const [x] = pointAt(index, 0)
      return `<text class="chart__tick" x="${x}" y="${height - 12}" text-anchor="middle">${esc(label)}</text>`
    })
    .join('')

  const lines = series
    .map((entry, seriesIndex) => {
      const points = entry.values.map((value, index) => pointAt(index, value))
      const path = points.map(([x, y], index) => `${index === 0 ? 'M' : 'L'} ${x} ${y}`).join(' ')

      // Area fill only under the first series, so the chart does not turn muddy.
      const area =
        seriesIndex === 0
          ? `<path class="chart__area" fill="${esc(entry.color)}"
               d="${path} L ${points[points.length - 1][0]} ${padTop + plotHeight} L ${points[0][0]} ${padTop + plotHeight} Z"></path>`
          : ''

      const dots = points
        .map(
          ([x, y], index) =>
            `<circle class="chart__point" cx="${x}" cy="${y}" r="4" fill="${esc(entry.color)}"
               data-tip="${esc(labels[index])}|${esc(entry.name)}: ${entry.values[index]}"
               tabindex="0" role="img"
               aria-label="${esc(labels[index])}, ${esc(entry.name)}: ${entry.values[index]}"></circle>`,
        )
        .join('')

      return `${area}<path class="chart__line" stroke="${esc(entry.color)}" d="${path}"></path>${dots}`
    })
    .join('')

  return `
    <div class="chart">
      <svg viewBox="0 0 ${width} ${height}" role="group">
        ${gridLines}
        <line class="chart__axis" x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${padTop + plotHeight}"></line>
        <line class="chart__axis" x1="${padLeft}" y1="${padTop + plotHeight}" x2="${width - padRight}" y2="${padTop + plotHeight}"></line>
        ${xLabels}
        ${lines}
      </svg>
    </div>`
}

/* ============================================================== LEGEND ===== */

/** Swatch + label + optional value, so identity never depends on colour alone. */
export function chartLegend(items) {
  if (!items?.length) return ''
  return `
    <ul class="chart-legend">
      ${items
        .map(
          (item) => `<li class="chart-legend__item">
            <span class="chart-legend__swatch" style="background:${esc(item.color)}"></span>
            <span>${esc(item.label)}</span>
            ${item.value != null ? `<span class="chart-legend__value">${esc(item.value)}</span>` : ''}
          </li>`,
        )
        .join('')}
    </ul>`
}

/* ========================================================== CHART CARD ===== */

let cardSequence = 0

/**
 * Card wrapper around a chart, with a legend and a "view as table" switch.
 *
 * The table view is not decoration: two of the palette colours sit below the
 * 3:1 contrast threshold on white, so an alternative to reading the colours has
 * to exist. It is also the quickest way to read exact numbers.
 */
export function chartCard({
  title,
  subtitle = '',
  chart = '',
  legend = [],
  tableHead = [],
  tableRows = [],
  empty = false,
  emptyMessage = 'There is no data to plot yet.',
}) {
  cardSequence += 1
  const id = `chart-${cardSequence}`

  const body = empty
    ? `<div class="state"><span class="state__icon">${icon('bar-chart', 'icon-xl')}</span>
         <p class="state__title">Nothing to show yet</p>
         <p class="state__text">${esc(emptyMessage)}</p></div>`
    : html(
        `<div data-chart-view="chart">${chart}${chartLegend(legend)}</div>`,
        tableHead.length
          ? `<div data-chart-view="table" hidden>
               <div class="table-wrap scroll-slim">
                 <table class="table" style="min-width:0">
                   <thead><tr>${tableHead.map((head) => `<th scope="col">${esc(head)}</th>`).join('')}</tr></thead>
                   <tbody>
                     ${tableRows
                       .map(
                         (row) =>
                           `<tr>${row
                             .map((cell, index) => `<td class="${index ? 'tnum' : ''}">${esc(cell)}</td>`)
                             .join('')}</tr>`,
                       )
                       .join('')}
                   </tbody>
                 </table>
               </div>
             </div>`
          : '',
      )

  const toggle =
    !empty && tableHead.length
      ? `<div class="view-switch" role="group" aria-label="Change view">
           <button type="button" data-view="chart" aria-pressed="true">${icon('bar-chart', 'icon-sm')}Chart</button>
           <button type="button" data-view="table" aria-pressed="false">${icon('table', 'icon-sm')}Table</button>
         </div>`
      : ''

  return `
    <section class="card" id="${id}" data-chart-card>
      <header class="card__head">
        <div class="grow" style="min-width:0">
          <h2 class="card__title truncate">${esc(title)}</h2>
          ${subtitle ? `<p class="card__subtitle">${esc(subtitle)}</p>` : ''}
        </div>
        ${toggle}
      </header>
      <div class="card__body">${body}</div>
    </section>`
}

/* ======================================================== INTERACTIVITY ==== */

let tip = null

function showTip(target, event) {
  const raw = target.dataset.tip
  if (!raw) return

  const [name, ...rest] = raw.split('|')
  if (!tip) {
    tip = document.createElement('div')
    tip.className = 'chart-tip'
    document.body.appendChild(tip)
  }

  tip.innerHTML = `<p class="chart-tip__name">${esc(name)}</p>${rest
    .map((line) => `<p class="chart-tip__row">${esc(line)}</p>`)
    .join('')}`

  const box = target.getBoundingClientRect()
  const x = event?.clientX ?? box.left + box.width / 2
  const y = event?.clientY ?? box.top

  tip.style.left = `${Math.min(x + 12, window.innerWidth - tip.offsetWidth - 12)}px`
  tip.style.top = `${Math.max(y - tip.offsetHeight - 10, 8)}px`
  tip.hidden = false
}

function hideTip() {
  if (tip) tip.hidden = true
}

/**
 * Wire up hover tooltips and the chart/table switch.
 * Call once after chart markup has been inserted into the page.
 */
export function activateCharts(scope = document) {
  qsa('[data-chart-card]', scope).forEach((card) => {
    on(card, 'click', '[data-view]', (event, button) => {
      const view = button.dataset.view
      qsa('[data-view]', card).forEach((other) =>
        other.setAttribute('aria-pressed', String(other.dataset.view === view)),
      )
      qsa('[data-chart-view]', card).forEach((panel) => {
        panel.hidden = panel.dataset.chartView !== view
      })
    })
  })

  qsa('[data-tip]', scope).forEach((mark) => {
    mark.addEventListener('mousemove', (event) => showTip(mark, event))
    mark.addEventListener('mouseenter', (event) => showTip(mark, event))
    mark.addEventListener('mouseleave', hideTip)
    mark.addEventListener('focus', () => showTip(mark))
    mark.addEventListener('blur', hideTip)
  })
}

export { CHART_INK, AXIS_PROPS, SERIES }
