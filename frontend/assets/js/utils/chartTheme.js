/**
 * Chart colours and shared Recharts settings.
 *
 * The palettes below were checked with a colour-vision-deficiency validator
 * (protanopia / deuteranopia / tritanopia separation, chroma, and contrast
 * against the white card surface) rather than picked by eye:
 *
 *  - STATUS_SERIES   categorical - six distinct hues, ordered so that
 *                    neighbouring slices of the donut stay separable.
 *  - PRIORITY_RAMP   ordinal - priority is an *ordered* scale (Low → Urgent),
 *                    so it uses one hue getting darker instead of four
 *                    unrelated colours. Hotter and darker = more urgent.
 *  - RATING_RAMP     ordinal - one blue hue, light (1 star) to dark (5 stars).
 *
 * Because two of the status hues fall below 3:1 contrast on white, every chart
 * in this folder also ships a legend with labels and a "view as table" toggle,
 * so no information is carried by colour alone.
 */

import { PRIORITY, STATUS } from './constants.js'

/* ----------------------------------------------------------------- chrome */

export const CHART_INK = {
  grid: '#e2e8f0',
  axis: '#cbd5e1',
  tick: '#64748b',
  label: '#334155',
  surface: '#ffffff',
}

/** Props shared by every axis so the charts look like one family. */
export const AXIS_PROPS = {
  tick: { fill: CHART_INK.tick, fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: CHART_INK.axis },
}

/* ------------------------------------------------------- categorical: status */

/**
 * The nine complaint statuses are folded into six reporting buckets.
 * Nine slices cannot be told apart in a donut; six can, and the exact status is
 * always available in the table below the chart.
 */
export const STATUS_GROUPS = [
  { key: 'Submitted', color: '#2a78d6', members: [STATUS.SUBMITTED, STATUS.UNDER_REVIEW] },
  { key: 'Assigned', color: '#1baf7a', members: [STATUS.ASSIGNED, STATUS.ACCEPTED] },
  { key: 'In Progress', color: '#eda100', members: [STATUS.IN_PROGRESS, STATUS.PENDING] },
  { key: 'Reopened', color: '#4a3aa7', members: [STATUS.REOPENED] },
  { key: 'Resolved', color: '#008300', members: [STATUS.RESOLVED, STATUS.CLOSED] },
  { key: 'Escalated', color: '#e34948', members: [STATUS.ESCALATED] },
]

/** Which reporting bucket a raw status belongs to. */
export function statusGroupOf(status) {
  return STATUS_GROUPS.find((group) => group.members.includes(status))?.key ?? 'Submitted'
}

export const STATUS_GROUP_COLORS = STATUS_GROUPS.reduce((acc, group) => {
  acc[group.key] = group.color
  return acc
}, {})

/* ---------------------------------------------------------- ordinal: priority */

export const PRIORITY_RAMP = {
  [PRIORITY.LOW]: '#f2a273',
  [PRIORITY.MEDIUM]: '#e8703a',
  [PRIORITY.HIGH]: '#c2451d',
  [PRIORITY.URGENT]: '#8a2c11',
}

/* ------------------------------------------------------------ ordinal: rating */

/** 1 star → 5 stars. */
export const RATING_RAMP = ['#86b6ef', '#5598e7', '#2a78d6', '#1c5cab', '#0d366b']

/* -------------------------------------------------------------- two-series */

/** Slots for charts that plot two measures together. */
export const SERIES = {
  primary: '#2a78d6', // registered / assigned / total
  positive: '#008300', // resolved
  accent: '#eb6834', // active workload / secondary measure
  neutral: '#94a3b8', // target lines and reference marks
}
