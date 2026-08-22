/**
 * Application-wide constants.
 *
 * Every screen imports its labels, colours and option lists from this file so
 * that a status or a department is spelled exactly the same way everywhere.
 * When the Flask backend arrives, only the values here need to match the API.
 */

/* ------------------------------------------------------------------ roles */

export const ROLES = {
  STUDENT: 'student',
  OFFICER: 'officer',
  ADMIN: 'admin',
}

export const ROLE_LABELS = {
  [ROLES.STUDENT]: 'Student / Staff',
  [ROLES.OFFICER]: 'Department Officer',
  [ROLES.ADMIN]: 'Administrator',
}

/** Landing route for each role after a successful login. */
export const ROLE_HOME = {
  [ROLES.STUDENT]: '/student/dashboard',
  [ROLES.OFFICER]: '/officer/dashboard',
  [ROLES.ADMIN]: '/admin/dashboard',
}

/* ------------------------------------------------------------ departments */

export const DEPARTMENT_CODES = {
  NIRMAN: 'NIRMAN',
  JALKAL: 'JALKAL',
  VIDYUT: 'VIDYUT',
  MCALAB: 'MCALAB',
}

/**
 * Department master list. `services/departmentService.js` serves this data and
 * the admin department screen edits a copy of it in memory.
 */
export const DEPARTMENTS = [
  {
    code: DEPARTMENT_CODES.NIRMAN,
    name: 'Nirman Vibhag',
    english: 'Construction & Maintenance',
    description:
      'Civil works, building repair, furniture, carpentry, painting and campus infrastructure upkeep.',
    color: 'amber',
  },
  {
    code: DEPARTMENT_CODES.JALKAL,
    name: 'Jal Kal Vibhag',
    english: 'Water & Sanitation',
    description:
      'Water supply, plumbing, RO plants, drainage, sewage lines and campus sanitation.',
    color: 'sky',
  },
  {
    code: DEPARTMENT_CODES.VIDYUT,
    name: 'Vidyut Vibhag',
    english: 'Electricity & Power',
    description:
      'Power supply, wiring, fans, lights, generators, street lights and electrical safety.',
    color: 'yellow',
  },
  {
    code: DEPARTMENT_CODES.MCALAB,
    name: 'MCA Lab / Computer Lab',
    english: 'Computing & Network',
    description:
      'Lab computers, projectors, printers, LAN, Wi-Fi, software installation and lab support.',
    color: 'violet',
  },
]

export const DEPARTMENT_NAMES = DEPARTMENTS.map((d) => d.name)

/** Quick lookup: department name -> department object. */
export const DEPARTMENT_BY_NAME = DEPARTMENTS.reduce((acc, dept) => {
  acc[dept.name] = dept
  return acc
}, {})

/* ------------------------------------------------------------- categories */

export const CATEGORIES = [
  'Building',
  'Water',
  'Electricity',
  'Computer/Lab',
  'Hostel',
  'Classroom',
  'Other',
]

/**
 * Category -> department mapping used by the simulated AI classifier.
 * The real model will return the department; this table keeps the prototype
 * behaving sensibly in the meantime.
 */
export const CATEGORY_DEPARTMENT_MAP = {
  Building: 'Nirman Vibhag',
  Water: 'Jal Kal Vibhag',
  Electricity: 'Vidyut Vibhag',
  'Computer/Lab': 'MCA Lab / Computer Lab',
  Hostel: 'Nirman Vibhag',
  Classroom: 'Nirman Vibhag',
  Other: 'Nirman Vibhag',
}

/* ---------------------------------------------------------------- status */

export const STATUS = {
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under Review',
  ASSIGNED: 'Assigned',
  ACCEPTED: 'Accepted',
  IN_PROGRESS: 'In Progress',
  PENDING: 'Pending',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
  REOPENED: 'Reopened',
  ESCALATED: 'Escalated',
}

export const STATUS_LIST = Object.values(STATUS)

/**
 * CSS modifier class for each status badge.
 * The colours themselves live in `assets/css/components.css` under
 * `.badge--submitted`, `.badge--resolved` and so on.
 */
export const STATUS_STYLES = {
  [STATUS.SUBMITTED]: 'badge--submitted',
  [STATUS.UNDER_REVIEW]: 'badge--review',
  [STATUS.ASSIGNED]: 'badge--assigned',
  [STATUS.ACCEPTED]: 'badge--accepted',
  [STATUS.IN_PROGRESS]: 'badge--progress',
  [STATUS.PENDING]: 'badge--pending',
  [STATUS.RESOLVED]: 'badge--resolved',
  [STATUS.CLOSED]: 'badge--closed',
  [STATUS.REOPENED]: 'badge--reopened',
  [STATUS.ESCALATED]: 'badge--escalated',
}

/* Chart colours are NOT defined here - see `utils/chartTheme.js`.
   Badge colours and chart colours have different jobs (a badge sits on white
   with its own text label, a chart mark sits next to other marks), so they are
   chosen and validated separately. */

/** Statuses that mean "the complaint is still open". */
export const ACTIVE_STATUSES = [
  STATUS.SUBMITTED,
  STATUS.UNDER_REVIEW,
  STATUS.ASSIGNED,
  STATUS.ACCEPTED,
  STATUS.IN_PROGRESS,
  STATUS.PENDING,
  STATUS.REOPENED,
  STATUS.ESCALATED,
]

/** Status values a department officer is allowed to set. */
export const OFFICER_STATUS_OPTIONS = [
  STATUS.ASSIGNED,
  STATUS.ACCEPTED,
  STATUS.IN_PROGRESS,
  STATUS.PENDING,
  STATUS.RESOLVED,
]

/* -------------------------------------------------------------- priority */

export const PRIORITY = {
  LOW: 'Low',
  MEDIUM: 'Medium',
  HIGH: 'High',
  URGENT: 'Urgent',
}

export const PRIORITY_LIST = Object.values(PRIORITY)

export const PRIORITY_STYLES = {
  [PRIORITY.LOW]: 'badge--low',
  [PRIORITY.MEDIUM]: 'badge--medium',
  [PRIORITY.HIGH]: 'badge--high',
  [PRIORITY.URGENT]: 'badge--urgent',
}

/** Service-level agreement in days, used to compute the resolution deadline. */
export const PRIORITY_SLA_DAYS = {
  [PRIORITY.URGENT]: 1,
  [PRIORITY.HIGH]: 3,
  [PRIORITY.MEDIUM]: 7,
  [PRIORITY.LOW]: 14,
}

/* ------------------------------------------------------------ escalation */

export const ESCALATION_LEVELS = [
  { level: 1, authority: 'Department Officer', afterDays: 0 },
  { level: 2, authority: 'Department Head', afterDays: 2 },
  { level: 3, authority: 'Admin / Higher Authority', afterDays: 5 },
]

export const ESCALATION_STYLES = {
  1: 'badge--progress',
  2: 'badge--pending',
  3: 'badge--escalated',
}

/* --------------------------------------------------------- notifications */

export const NOTIFICATION_TYPES = {
  SUBMITTED: 'submitted',
  ASSIGNED: 'assigned',
  STATUS_CHANGED: 'status_changed',
  OFFICER_ASSIGNED: 'officer_assigned',
  RESOLUTION_SUBMITTED: 'resolution_submitted',
  RESOLVED: 'resolved',
  DEADLINE_APPROACHING: 'deadline_approaching',
  ESCALATED: 'escalated',
  FEEDBACK_REQUESTED: 'feedback_requested',
}

/* ------------------------------------------------------- upload settings */

export const UPLOAD_LIMITS = {
  maxFiles: 5,
  maxSizeMB: 5,
  accept: 'image/png,image/jpeg,image/jpg,image/webp,application/pdf,.doc,.docx',
}

/* ----------------------------------------------- demo (frontend-only) auth */

/**
 * DEMO CREDENTIALS - frontend prototype only.
 *
 * These accounts exist purely so the UI can be demonstrated without a server.
 * They are validated in `services/authService.js` and MUST be deleted once the
 * Flask `/api/auth/login` endpoint is connected. No real password is stored.
 */
export const DEMO_ACCOUNTS = [
  { email: 'student@dsvv.ac.in', password: 'student123', role: ROLES.STUDENT },
  { email: 'officer@dsvv.ac.in', password: 'officer123', role: ROLES.OFFICER },
  { email: 'admin@dsvv.ac.in', password: 'admin123', role: ROLES.ADMIN },
]

/* -------------------------------------------------------- misc constants */

export const APP_NAME = 'Grievance Management System'
export const UNIVERSITY_NAME = 'Dev Sanskriti Vishwavidyalaya'
export const UNIVERSITY_SHORT = 'DSVV'
export const UNIVERSITY_LOCATION = 'Haridwar, Uttarakhand'

/**
 * Official image assets.
 *
 * These files are not part of the repository yet. While a path points at a
 * missing file the interface falls back to a clearly marked placeholder
 * rather than a broken image or an invented substitute — see
 * `assets/img/README.md`. Drop the real files in and they appear
 * everywhere at once.
 */
export const ASSETS = {
  logo: '/assets/img/dsvv-logo.png',
  campus: '/assets/img/campus.jpg',
}

/** Grievance cell contact details that already exist in the project. */
export const CONTACT = {
  email: 'grievance@dsvv.ac.in',
  location: UNIVERSITY_LOCATION,
}

/** Campus centre coordinates, used as the origin for simulated geo-tagging. */
export const CAMPUS_CENTER = { latitude: 29.9457, longitude: 78.1642 }

export const PAGE_SIZE_OPTIONS = [5, 10, 25, 50]
