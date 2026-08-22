/**
 * Department master records.
 *
 * The static identity of each department lives in `utils/constants.js`; this
 * file adds the administrative fields the admin department screen manages
 * (head, contact details, office location, active flag).
 */

import { DEPARTMENTS } from '../utils/constants.js'

const DEPARTMENT_DETAILS = {
  NIRMAN: {
    head: 'Er. Mahesh Chandra Joshi',
    email: 'nirman@dsvv.ac.in',
    office: 'Estate Office, Administrative Block, Ground Floor',
    establishedYear: 2004,
    isActive: true,
  },
  JALKAL: {
    head: 'Er. Suresh Prasad Nautiyal',
    email: 'jalkal@dsvv.ac.in',
    office: 'Water Works Cell, Behind Annapurna Bhavan',
    establishedYear: 2006,
    isActive: true,
  },
  VIDYUT: {
    head: 'Er. Rakesh Kumar Bhatt',
    email: 'vidyut@dsvv.ac.in',
    office: 'Electrical Substation, Gate No. 2',
    establishedYear: 2004,
    isActive: true,
  },
  MCALAB: {
    head: 'Dr. Anupam Kaushik',
    email: 'computerlab@dsvv.ac.in',
    office: 'Department of Computer Science, Shantikunj Bhavan, 2nd Floor',
    establishedYear: 2011,
    isActive: true,
  },
}

/** Full department list used by services and admin screens. */
export const departments = DEPARTMENTS.map((dept) => ({
  ...dept,
  ...DEPARTMENT_DETAILS[dept.code],
}))

export default departments
