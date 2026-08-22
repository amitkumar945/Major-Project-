/**
 * Mock user directory: students/staff, department officers and administrators.
 *
 * All names, IDs and email addresses below are invented for this
 * prototype. They do not belong to any real person.
 */

import { ROLES } from '../utils/constants.js'

/* ------------------------------------------------------- students & staff */

export const students = [
  {
    id: 'USR-1001',
    role: ROLES.STUDENT,
    name: 'Rakesh Patidar',
    userId: 'MCA/2024/018',
    email: 'student@dsvv.ac.in',
    department: 'MCA - Department of Computer Science',
    course: 'Master of Computer Applications',
    year: '2nd Year',
    hostel: 'Gayatri Bhavan, Room 214',
    userType: 'Student',
    avatarColor: '#4f46e5',
    joinedAt: '2024-07-21T04:30:00.000Z',
  },
  {
    id: 'USR-1002',
    role: ROLES.STUDENT,
    name: 'Sneha Bhardwaj',
    userId: 'MSC/2025/044',
    email: 'sneha.bhardwaj@dsvv.ac.in',
    department: 'M.Sc. Yogic Science',
    course: 'M.Sc. Yogic Science',
    year: '1st Year',
    hostel: 'Saraswati Bhavan, Room 108',
    userType: 'Student',
    avatarColor: '#059669',
    joinedAt: '2025-07-18T04:30:00.000Z',
  },
  {
    id: 'USR-1003',
    role: ROLES.STUDENT,
    name: 'Aditya Nautiyal',
    userId: 'BCA/2024/091',
    email: 'aditya.nautiyal@dsvv.ac.in',
    department: 'BCA - Department of Computer Science',
    course: 'Bachelor of Computer Applications',
    year: '3rd Year',
    hostel: 'Chetna Bhavan, Room 302',
    userType: 'Student',
    avatarColor: '#d97706',
    joinedAt: '2023-07-24T04:30:00.000Z',
  },
  {
    id: 'USR-1004',
    role: ROLES.STUDENT,
    name: 'Priyanka Semwal',
    userId: 'MA/2025/017',
    email: 'priyanka.semwal@dsvv.ac.in',
    department: 'M.A. Clinical Psychology',
    course: 'M.A. Clinical Psychology',
    year: '1st Year',
    hostel: 'Devi Bhavan, Room 011',
    userType: 'Student',
    avatarColor: '#9333ea',
    joinedAt: '2025-07-19T04:30:00.000Z',
  },
  {
    id: 'USR-1005',
    role: ROLES.STUDENT,
    name: 'Dr. Vikram Uniyal',
    userId: 'EMP/2019/233',
    email: 'vikram.uniyal@dsvv.ac.in',
    department: 'Department of Computer Science',
    course: '—',
    year: '—',
    hostel: 'Staff Quarters, Block C-4',
    userType: 'Staff',
    avatarColor: '#0369a1',
    joinedAt: '2019-01-14T04:30:00.000Z',
  },
  {
    id: 'USR-1006',
    role: ROLES.STUDENT,
    name: 'Kavita Dobhal',
    userId: 'EMP/2021/118',
    email: 'kavita.dobhal@dsvv.ac.in',
    department: 'Library & Information Centre',
    course: '—',
    year: '—',
    hostel: 'Staff Quarters, Block A-2',
    userType: 'Staff',
    avatarColor: '#e11d48',
    joinedAt: '2021-03-08T04:30:00.000Z',
  },
  {
    id: 'USR-1007',
    role: ROLES.STUDENT,
    name: 'Harshit Rawat',
    userId: 'MCA/2025/007',
    email: 'harshit.rawat@dsvv.ac.in',
    department: 'MCA - Department of Computer Science',
    course: 'Master of Computer Applications',
    year: '1st Year',
    hostel: 'Gayatri Bhavan, Room 119',
    userType: 'Student',
    avatarColor: '#0d9488',
    joinedAt: '2025-07-21T04:30:00.000Z',
  },
  {
    id: 'USR-1008',
    role: ROLES.STUDENT,
    name: 'Meenakshi Thapliyal',
    userId: 'BA/2024/205',
    email: 'meenakshi.thapliyal@dsvv.ac.in',
    department: 'B.A. Journalism & Mass Communication',
    course: 'B.A. Journalism & Mass Communication',
    year: '2nd Year',
    hostel: 'Devi Bhavan, Room 224',
    userType: 'Student',
    avatarColor: '#4338ca',
    joinedAt: '2024-07-22T04:30:00.000Z',
  },
]

/* ---------------------------------------------------- department officers */

export const officers = [
  {
    id: 'OFF-2001',
    role: ROLES.OFFICER,
    name: 'Er. Devendra Singh Rawat',
    employeeId: 'DSVV/NIR/114',
    email: 'officer@dsvv.ac.in',
    department: 'Nirman Vibhag',
    designation: 'Civil Maintenance Officer',
    userType: 'Officer',
    isActive: true,
    avatarColor: '#b45309',
    joinedAt: '2018-04-02T04:30:00.000Z',
    stats: { activeComplaints: 12, resolved: 148, avgResolutionDays: 3.4, rating: 4.3 },
  },
  {
    id: 'OFF-2002',
    role: ROLES.OFFICER,
    name: 'Er. Pankaj Kumar Semwal',
    employeeId: 'DSVV/JAL/207',
    email: 'pankaj.semwal@dsvv.ac.in',
    department: 'Jal Kal Vibhag',
    designation: 'Water Supply Officer',
    userType: 'Officer',
    isActive: true,
    avatarColor: '#0369a1',
    joinedAt: '2020-06-15T04:30:00.000Z',
    stats: { activeComplaints: 5, resolved: 96, avgResolutionDays: 2.1, rating: 4.6 },
  },
  {
    id: 'OFF-2003',
    role: ROLES.OFFICER,
    name: 'Er. Naveen Chandra Painuli',
    employeeId: 'DSVV/VID/331',
    email: 'naveen.painuli@dsvv.ac.in',
    department: 'Vidyut Vibhag',
    designation: 'Electrical Maintenance Officer',
    userType: 'Officer',
    isActive: true,
    avatarColor: '#a16207',
    joinedAt: '2017-09-11T04:30:00.000Z',
    stats: { activeComplaints: 9, resolved: 172, avgResolutionDays: 1.8, rating: 4.5 },
  },
  {
    id: 'OFF-2004',
    role: ROLES.OFFICER,
    name: 'Mr. Sandeep Bijalwan',
    employeeId: 'DSVV/MCA/402',
    email: 'sandeep.bijalwan@dsvv.ac.in',
    department: 'MCA Lab / Computer Lab',
    designation: 'Lab Systems Administrator',
    userType: 'Officer',
    isActive: true,
    avatarColor: '#6d28d9',
    joinedAt: '2019-11-04T04:30:00.000Z',
    stats: { activeComplaints: 7, resolved: 121, avgResolutionDays: 1.5, rating: 4.7 },
  },
  {
    id: 'OFF-2005',
    role: ROLES.OFFICER,
    name: 'Mr. Girish Chandra Bahuguna',
    employeeId: 'DSVV/NIR/158',
    email: 'girish.bahuguna@dsvv.ac.in',
    department: 'Nirman Vibhag',
    designation: 'Junior Engineer (Carpentry & Furniture)',
    userType: 'Officer',
    isActive: true,
    avatarColor: '#c2410c',
    joinedAt: '2021-02-19T04:30:00.000Z',
    stats: { activeComplaints: 4, resolved: 63, avgResolutionDays: 4.2, rating: 4.0 },
  },
  {
    id: 'OFF-2006',
    role: ROLES.OFFICER,
    name: 'Mr. Anil Kumar Kandwal',
    employeeId: 'DSVV/VID/345',
    email: 'anil.kandwal@dsvv.ac.in',
    department: 'Vidyut Vibhag',
    designation: 'Electrician Supervisor',
    userType: 'Officer',
    isActive: true,
    avatarColor: '#4d7c0f',
    joinedAt: '2022-08-01T04:30:00.000Z',
    stats: { activeComplaints: 6, resolved: 54, avgResolutionDays: 2.6, rating: 4.1 },
  },
  {
    id: 'OFF-2007',
    role: ROLES.OFFICER,
    name: 'Mr. Mohan Lal Kukreti',
    employeeId: 'DSVV/JAL/219',
    email: 'mohan.kukreti@dsvv.ac.in',
    department: 'Jal Kal Vibhag',
    designation: 'Sanitation Supervisor',
    userType: 'Officer',
    isActive: false,
    avatarColor: '#0e7490',
    joinedAt: '2016-05-23T04:30:00.000Z',
    stats: { activeComplaints: 0, resolved: 210, avgResolutionDays: 3.1, rating: 3.9 },
  },
  {
    id: 'OFF-2008',
    role: ROLES.OFFICER,
    name: 'Ms. Ritika Chamoli',
    employeeId: 'DSVV/MCA/418',
    email: 'ritika.chamoli@dsvv.ac.in',
    department: 'MCA Lab / Computer Lab',
    designation: 'Network & Hardware Engineer',
    userType: 'Officer',
    isActive: true,
    avatarColor: '#a21caf',
    joinedAt: '2023-01-16T04:30:00.000Z',
    stats: { activeComplaints: 3, resolved: 38, avgResolutionDays: 1.2, rating: 4.8 },
  },
]

/* ---------------------------------------------------------- administrator */

export const admins = [
  {
    id: 'ADM-3001',
    role: ROLES.ADMIN,
    name: 'Dr. Shailendra Prakash Dwivedi',
    employeeId: 'DSVV/ADM/001',
    email: 'admin@dsvv.ac.in',
    department: 'Office of the Registrar',
    designation: 'Grievance Redressal Cell - Nodal Officer',
    userType: 'Administrator',
    isActive: true,
    avatarColor: '#1e293b',
    joinedAt: '2015-08-10T04:30:00.000Z',
  },
]

/** Flat directory of every account in the system. */
export const allUsers = [...students, ...officers, ...admins]

/** Look up any account by its id. */
export function findUserById(id) {
  return allUsers.find((user) => user.id === id) ?? null
}

/** Officers belonging to one department. */
export function officersByDepartment(departmentName) {
  return officers.filter((officer) => officer.department === departmentName)
}

export default allUsers
