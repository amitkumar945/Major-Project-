/**
 * Analytics datasets for the admin dashboard.
 *
 * Distributions (status / department / priority) are computed live from the
 * seeded complaints so the charts always agree with the tables. Historical
 * series - monthly trend, resolution time, satisfaction - cannot be derived
 * from 26 records, so those are realistic fixed datasets.
 */

import {
  DEPARTMENT_NAMES,
  PRIORITY_LIST,
  STATUS,
  STATUS_LIST,
} from '../utils/constants.js'
import { countBy, toChartData } from '../utils/helpers.js'
import { complaints } from './complaints.js'
import { officers } from './users.js'

/* ------------------------------------------------- live distributions */

/** Complaints grouped by status, ready for a pie or donut chart. */
export function statusDistribution(list = complaints) {
  return toChartData(countBy(list, 'status'), STATUS_LIST).filter((d) => d.value > 0)
}

/** Complaints grouped by department, ready for a bar chart. */
export function departmentDistribution(list = complaints) {
  return toChartData(countBy(list, 'department'), DEPARTMENT_NAMES)
}

/** Complaints grouped by priority. */
export function priorityDistribution(list = complaints) {
  return toChartData(countBy(list, 'priority'), PRIORITY_LIST)
}

/* --------------------------------------------------- historical series */

/** Registered vs resolved complaints over the last twelve months. */
export const monthlyTrend = [
  { month: 'Mar', registered: 38, resolved: 34 },
  { month: 'Apr', registered: 45, resolved: 41 },
  { month: 'May', registered: 29, resolved: 28 },
  { month: 'Jun', registered: 22, resolved: 21 },
  { month: 'Jul', registered: 61, resolved: 52 },
  { month: 'Aug', registered: 74, resolved: 66 },
  { month: 'Sep', registered: 58, resolved: 55 },
  { month: 'Oct', registered: 49, resolved: 47 },
  { month: 'Nov', registered: 42, resolved: 40 },
  { month: 'Dec', registered: 36, resolved: 35 },
  { month: 'Jan', registered: 55, resolved: 48 },
  { month: 'Feb', registered: 63, resolved: 51 },
]

/** Average days taken to resolve, per department. */
export const resolutionTimeByDepartment = [
  { name: 'Nirman Vibhag', avgDays: 4.2, targetDays: 5 },
  { name: 'Jal Kal Vibhag', avgDays: 2.4, targetDays: 3 },
  { name: 'Vidyut Vibhag', avgDays: 1.9, targetDays: 3 },
  { name: 'MCA Lab / Computer Lab', avgDays: 1.4, targetDays: 2 },
]

/** Officer scorecard used by the analytics page and officer management. */
export const officerPerformance = officers
  .filter((officer) => officer.isActive)
  .map((officer) => ({
    id: officer.id,
    name: officer.name,
    department: officer.department,
    assigned: officer.stats.activeComplaints + officer.stats.resolved,
    resolved: officer.stats.resolved,
    active: officer.stats.activeComplaints,
    avgDays: officer.stats.avgResolutionDays,
    rating: officer.stats.rating,
  }))
  .sort((a, b) => b.resolved - a.resolved)

/** Department scorecard: volume, resolution rate and satisfaction. */
export const departmentPerformance = [
  { name: 'Nirman Vibhag', total: 214, resolved: 186, pending: 28, resolutionRate: 87, satisfaction: 4.1 },
  { name: 'Jal Kal Vibhag', total: 178, resolved: 163, pending: 15, resolutionRate: 92, satisfaction: 4.4 },
  { name: 'Vidyut Vibhag', total: 241, resolved: 226, pending: 15, resolutionRate: 94, satisfaction: 4.5 },
  { name: 'MCA Lab / Computer Lab', total: 132, resolved: 125, pending: 7, resolutionRate: 95, satisfaction: 4.7 },
]

/** Count of feedback entries at each star rating. */
export const satisfactionDistribution = [
  { rating: '5 Star', count: 214 },
  { rating: '4 Star', count: 156 },
  { rating: '3 Star', count: 48 },
  { rating: '2 Star', count: 27 },
  { rating: '1 Star', count: 11 },
]

/** Complaints registered per weekday - used for the load pattern chart. */
export const weeklyLoad = [
  { day: 'Mon', complaints: 18 },
  { day: 'Tue', complaints: 14 },
  { day: 'Wed', complaints: 16 },
  { day: 'Thu', complaints: 12 },
  { day: 'Fri', complaints: 15 },
  { day: 'Sat', complaints: 9 },
  { day: 'Sun', complaints: 4 },
]

/* --------------------------------------------------------- key figures */

/** Headline numbers for the admin dashboard cards. */
export function keyMetrics(list = complaints) {
  const total = list.length
  const byStatus = countBy(list, 'status')
  const resolved = (byStatus[STATUS.RESOLVED] ?? 0) + (byStatus[STATUS.CLOSED] ?? 0)
  const todayISO = new Date().toDateString()
  const today = list.filter(
    (complaint) => new Date(complaint.submittedAt).toDateString() === todayISO,
  ).length

  const ratings = list.filter((c) => c.feedback).map((c) => c.feedback.rating)
  const avgRating = ratings.length
    ? ratings.reduce((sum, value) => sum + value, 0) / ratings.length
    : 0

  return {
    total,
    today,
    pending: (byStatus[STATUS.PENDING] ?? 0) + (byStatus[STATUS.SUBMITTED] ?? 0) + (byStatus[STATUS.UNDER_REVIEW] ?? 0),
    inProgress: (byStatus[STATUS.IN_PROGRESS] ?? 0) + (byStatus[STATUS.ACCEPTED] ?? 0) + (byStatus[STATUS.ASSIGNED] ?? 0),
    resolved,
    escalated: byStatus[STATUS.ESCALATED] ?? 0,
    reopened: byStatus[STATUS.REOPENED] ?? 0,
    avgResolutionDays: 2.6,
    satisfactionRate: Math.round((avgRating / 5) * 100),
    avgRating: Number(avgRating.toFixed(1)),
    resolutionRate: total ? Math.round((resolved / total) * 100) : 0,
  }
}

export default {
  monthlyTrend,
  resolutionTimeByDepartment,
  officerPerformance,
  departmentPerformance,
  satisfactionDistribution,
  weeklyLoad,
}
