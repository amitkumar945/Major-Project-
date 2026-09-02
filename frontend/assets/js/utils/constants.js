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

/* ------------------------------------------------- seeded demo accounts */

/**
 * The accounts `backend/seed.py` creates, used by the one-click buttons on the
 * login page.
 *
 * These are NOT a frontend auth bypass: the buttons only fill the form and
 * submit it, and the credentials are checked server-side against the bcrypt
 * hash by `POST /api/auth/login` like any other account. The passwords below
 * are the seed defaults, which `SEED_STUDENT_PASSWORD` / `SEED_OFFICER_PASSWORD`
 * / `SEED_ADMIN_PASSWORD` in `backend/.env` can override - change them there
 * and here together, or drop this list to hide the buttons.
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
 * `dsvv-logo.svg` is a neutral placeholder emblem, not the official crest —
 * see `assets/img/README.md`. Replacing that one file swaps the mark on every
 * page. If a path ever points at a missing file the interface falls back to a
 * clearly marked placeholder rather than a broken image.
 */
export const ASSETS = {
  logo: '/assets/img/dsvv-logo.svg',
}

/** Grievance cell contact details that already exist in the project. */
export const CONTACT = {
  email: 'grievance@dsvv.ac.in',
  location: UNIVERSITY_LOCATION,
}

/** Campus centre coordinates, used as the origin for simulated geo-tagging. */
export const CAMPUS_CENTER = { latitude: 29.99965, longitude: 78.1946 }

/**
 * The real DSVV campus outline, taken from OpenStreetMap way/1152422760
 * ("Dev Sanskriti Vishwavidyalaya (DSVV), NH34, Rishikesh, Haridwar").
 * Stored as [latitude, longitude] pairs because that is the order Leaflet
 * expects; the source GeoJSON is [longitude, latitude].
 *
 * Used to draw the campus boundary and to reject complaints tagged outside it.
 */
export const CAMPUS_POLYGON = [
  [30.0018344, 78.1905549],
  [29.9997622, 78.1906804],
  [29.9997529, 78.1909221],
  [29.9990507, 78.1909547],
  [29.999056, 78.1906994],
  [29.9982475, 78.1907323],
  [29.9979564, 78.191231],
  [29.9973232, 78.1919827],
  [29.9963837, 78.1931417],
  [29.9960528, 78.1935266],
  [29.9976137, 78.1954428],
  [29.9975361, 78.1955205],
  [29.9969588, 78.196077],
  [29.9967062, 78.1963394],
  [29.9977739, 78.1974088],
  [29.9972499, 78.1979616],
  [29.9979125, 78.1986453],
  [29.9983217, 78.1980056],
  [29.9986674, 78.1974636],
  [29.9990781, 78.1969717],
  [29.9997395, 78.1959467],
  [30.0004379, 78.1950392],
  [30.0010698, 78.1940502],
  [30.001891, 78.1929093],
  [30.0032553, 78.1910827],
  [30.0029709, 78.1908111],
  [30.0018757, 78.1909007],
  [30.0018344, 78.1905549],
]

/**
 * Bounding box of CAMPUS_POLYGON, padded by roughly 150 m so the map can pan
 * a little past the fence without ever reaching the next town. This is what
 * Leaflet's `maxBounds` uses; the polygon itself is what validation uses.
 */
export const CAMPUS_BOUNDS = {
  minLatitude: 29.9946,
  maxLatitude: 30.0047,
  minLongitude: 78.189,
  maxLongitude: 78.2002,
}

/** Zoom limits: 15 still frames the whole campus, so India never comes back. */
export const CAMPUS_ZOOM = { min: 15, default: 16, max: 19, point: 18 }

export const PAGE_SIZE_OPTIONS = [5, 10, 25, 50]
