/**
 * Sidebar menus for the three roles.
 *
 * Keeping the menus in one file means a new screen is added to the navigation
 * by editing this list, not by touching every HTML page.
 */

import { ROLES } from '../utils/constants.js'

export const MENUS = {
  [ROLES.STUDENT]: [
    { label: 'Dashboard', href: '/student/dashboard.html', icon: 'dashboard' },
    { label: 'Submit Complaint', href: '/student/new-complaint.html', icon: 'file-plus' },
    { label: 'My Complaints', href: '/student/complaints.html', icon: 'clipboard-list' },
    { label: 'Track Complaint', href: '/track.html', icon: 'file-search' },
    { label: 'Notifications', href: '/student/notifications.html', icon: 'bell', badge: 'unread' },
    { label: 'Feedback', href: '/student/feedback.html', icon: 'star' },
    { label: 'Profile', href: '/student/profile.html', icon: 'user' },
    { label: 'Help & Support', href: '/student/help.html', icon: 'life-buoy' },
  ],

  [ROLES.OFFICER]: [
    { label: 'Dashboard', href: '/officer/dashboard.html', icon: 'dashboard' },
    { label: 'Assigned Complaints', href: '/officer/complaints.html', icon: 'clipboard-list' },
    { label: 'Department Queue', href: '/officer/department.html', icon: 'layers' },
    { label: 'Notifications', href: '/officer/notifications.html', icon: 'bell', badge: 'unread' },
    { label: 'Profile', href: '/officer/profile.html', icon: 'user' },
  ],

  [ROLES.ADMIN]: [
    { label: 'Dashboard', href: '/admin/dashboard.html', icon: 'dashboard' },
    { label: 'Complaints', href: '/admin/complaints.html', icon: 'clipboard-list' },
    { label: 'Departments', href: '/admin/departments.html', icon: 'building' },
    { label: 'Officers', href: '/admin/officers.html', icon: 'user-cog' },
    { label: 'Students & Staff', href: '/admin/users.html', icon: 'users' },
    { label: 'Escalations', href: '/admin/escalations.html', icon: 'shield-alert' },
    { label: 'Analytics', href: '/admin/analytics.html', icon: 'bar-chart' },
    { label: 'Notifications', href: '/admin/notifications.html', icon: 'bell', badge: 'unread' },
    { label: 'Settings', href: '/admin/settings.html', icon: 'settings' },
  ],
}

/**
 * Mobile bottom navigation - the handful of destinations each role reaches
 * most often. This is a shortcut, not a replacement: the full MENUS list above
 * is still reachable from the drawer, so no screen becomes unreachable.
 *
 * `drawer: true` opens the full menu instead of navigating, which is how roles
 * with many screens keep everything within reach on a phone.
 */
export const TABS = {
  [ROLES.STUDENT]: [
    { label: 'Home', href: '/student/dashboard.html', icon: 'home' },
    { label: 'Complaints', href: '/student/complaints.html', icon: 'clipboard-list' },
    { label: 'Track', href: '/track.html', icon: 'file-search' },
    { label: 'Notifications', href: '/student/notifications.html', icon: 'bell', badge: 'unread' },
    { label: 'Profile', href: '/student/profile.html', icon: 'user' },
  ],

  [ROLES.OFFICER]: [
    { label: 'Home', href: '/officer/dashboard.html', icon: 'home' },
    { label: 'Assigned', href: '/officer/complaints.html', icon: 'clipboard-list' },
    { label: 'Queue', href: '/officer/department.html', icon: 'layers' },
    { label: 'Alerts', href: '/officer/notifications.html', icon: 'bell', badge: 'unread' },
    { label: 'Profile', href: '/officer/profile.html', icon: 'user' },
  ],

  [ROLES.ADMIN]: [
    { label: 'Home', href: '/admin/dashboard.html', icon: 'home' },
    { label: 'Complaints', href: '/admin/complaints.html', icon: 'clipboard-list' },
    { label: 'Analytics', href: '/admin/analytics.html', icon: 'bar-chart' },
    { label: 'Alerts', href: '/admin/notifications.html', icon: 'bell', badge: 'unread' },
    { label: 'Menu', href: '#menu', icon: 'menu', drawer: true },
  ],
}

/** Where each role's complaint details page lives. */
export const DETAILS_PAGE = {
  [ROLES.STUDENT]: '/student/complaint-details.html',
  [ROLES.OFFICER]: '/officer/complaint-details.html',
  [ROLES.ADMIN]: '/admin/complaint-details.html',
}

/** Where each role lands after signing in. */
export const HOME_PAGE = {
  [ROLES.STUDENT]: '/student/dashboard.html',
  [ROLES.OFFICER]: '/officer/dashboard.html',
  [ROLES.ADMIN]: '/admin/dashboard.html',
}
