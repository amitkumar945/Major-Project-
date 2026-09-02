/**
 * Analytics service - feeds every chart on the dashboards.
 *
 *   GET /api/analytics/charts     the three dashboard charts
 *   GET /api/analytics/summary    headline metrics
 *   GET /api/analytics/overview   everything the admin analytics page renders
 *   GET /api/feedback             the ratings table
 *
 * Data arrives in the `[{ name, value }]` shape `components/charts.js` already
 * draws, so no chart code changed. Unlike the prototype, the monthly trend,
 * weekly load, resolution times and satisfaction figures are now computed from
 * real complaints rather than fixed sample arrays.
 */

import { download, request } from './mockApi.js'

/**
 * Chart data for a dashboard.
 * @param {object} scope - { userId } | { officerId } | { department } | {}
 */
export async function getDashboardCharts(scope = {}) {
  return request('/analytics/charts', { query: scope })
}

/** Everything the admin analytics page renders. */
export async function getAnalyticsOverview() {
  return request('/analytics/overview')
}

/** Headline numbers for the dashboard cards. */
export async function getKeyMetrics(scope = {}) {
  return request('/analytics/summary', { query: scope })
}

/** Feedback list for the analytics page. */
export async function getFeedbackEntries() {
  return request('/feedback')
}

/** Ratings the signed-in student has given, plus the ones still pending. */
export async function getMyFeedback() {
  return request('/feedback/my')
}

/** SLA compliance report (admin). */
export async function getSlaReport() {
  return request('/analytics/sla')
}

/** Per-officer performance scorecard. */
export async function getOfficerPerformance() {
  return request('/analytics/officers')
}


/** Download the headline analytics figures as a CSV file. */
export async function exportAnalytics(scope = {}) {
  return download('/analytics/export', scope, 'analytics.csv')
}
