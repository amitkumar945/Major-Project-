/**
 * Mock complaint records.
 *
 * Each seed below is expanded into a full complaint object (deadline, AI
 * prediction, evidence, timeline, escalation level). Dates are expressed as
 * "days ago" so the demo data always looks current whenever the app is opened.
 */

import {
  CAMPUS_CENTER,
  PRIORITY,
  STATUS,
  UNIVERSITY_SHORT,
} from '../utils/constants.js'
import {
  calculateDeadline,
  daysUntil,
  escalationAuthority,
  escalationLevelForOverdue,
} from '../utils/helpers.js'
import { buildTimeline } from '../utils/complaintTimeline.js'
import { officers, students } from './users.js'

/* -------------------------------------------------------------- utilities */

/** ISO timestamp for `days` ago at the given hour (campus local time). */
function daysAgo(days, hour = 10, minute = 15) {
  const date = new Date()
  date.setDate(date.getDate() - days)
  date.setHours(hour, minute, 0, 0)
  return date.toISOString()
}

/** Small deterministic offset so markers do not all sit on the same point. */
function campusPoint(index) {
  return {
    latitude: Number((CAMPUS_CENTER.latitude + (index % 7) * 0.00042 - 0.0012).toFixed(6)),
    longitude: Number((CAMPUS_CENTER.longitude + (index % 5) * 0.00051 - 0.0009).toFixed(6)),
  }
}

function file(name, kind, sizeKB) {
  return {
    id: `${name}-${sizeKB}`,
    name,
    kind, // 'image' | 'pdf' | 'doc'
    type:
      kind === 'image'
        ? 'image/jpeg'
        : kind === 'pdf'
          ? 'application/pdf'
          : 'application/msword',
    size: sizeKB * 1024,
    url: null, // real object URLs only exist for files uploaded in this session
  }
}

/** Compact reference to the complainant stored on the complaint record. */
function complainant(student) {
  return {
    id: student.id,
    name: student.name,
    userId: student.userId,
    email: student.email,
    userType: student.userType,
    hostel: student.hostel,
  }
}

/** Compact reference to the handling officer. */
function handler(officer) {
  if (!officer) return null
  return {
    id: officer.id,
    name: officer.name,
    designation: officer.designation,
    department: officer.department,
    email: officer.email,
    employeeId: officer.employeeId,
  }
}

const officerById = (id) => officers.find((officer) => officer.id === id)
const studentById = (id) => students.find((student) => student.id === id)

/* ------------------------------------------------------------------ seeds */

const SEEDS = [
  {
    title: 'Water leakage near Gayatri Bhavan hostel entrance',
    description:
      'A pipeline joint near the main entrance of Gayatri Bhavan has been leaking continuously for the last two days. Water has collected on the walkway and students are slipping while entering the hostel. The leakage seems to be from the underground supply line.',
    category: 'Water',
    department: 'Jal Kal Vibhag',
    priority: PRIORITY.HIGH,
    status: STATUS.IN_PROGRESS,
    student: 'USR-1001',
    officer: 'OFF-2002',
    address: 'Gayatri Bhavan, Main Entrance Walkway',
    block: 'Hostel Zone A',
    submitted: 4,
    evidence: [file('leakage-entrance.jpg', 'image', 842), file('leakage-closeup.jpg', 'image', 671)],
    remarks: [
      {
        by: 'Er. Pankaj Kumar Semwal',
        role: 'Officer',
        message: 'Site inspected. Joint replacement material has been ordered from the store.',
        daysAgo: 2,
      },
    ],
    keywords: ['water', 'leakage', 'pipeline', 'hostel'],
  },
  {
    title: 'Ceiling fan not working in Classroom C-204',
    description:
      'Both ceiling fans in classroom C-204 have stopped working since Monday morning. The regulator is also not responding. With around sixty students in the room during afternoon lectures it becomes extremely uncomfortable.',
    category: 'Electricity',
    department: 'Vidyut Vibhag',
    priority: PRIORITY.MEDIUM,
    status: STATUS.RESOLVED,
    student: 'USR-1003',
    officer: 'OFF-2003',
    address: 'Academic Block C, Room 204, Second Floor',
    block: 'Academic Zone',
    submitted: 11,
    resolvedAfter: 3,
    evidence: [file('fan-c204.jpg', 'image', 512)],
    resolution: {
      notes:
        'Both fan capacitors were replaced and the wiring of the regulator board was re-terminated. Fans tested at all five speeds in presence of the class representative.',
      proof: [file('fan-repair-report.pdf', 'pdf', 240)],
    },
    feedback: { rating: 5, comment: 'Very fast action by the electrical team. Thank you.', satisfied: true },
    remarks: [
      { by: 'Er. Naveen Chandra Painuli', role: 'Officer', message: 'Capacitor replacement scheduled for tomorrow morning.', daysAgo: 9 },
    ],
    keywords: ['fan', 'classroom', 'electricity', 'regulator'],
  },
  {
    title: 'Internet connectivity down in MCA Lab-2',
    description:
      'All twenty five systems in MCA Lab-2 are showing "no internet access". The LAN switch near the instructor desk keeps blinking red. Practical sessions of Web Technology could not be conducted today because of this.',
    category: 'Computer/Lab',
    department: 'MCA Lab / Computer Lab',
    priority: PRIORITY.URGENT,
    status: STATUS.ESCALATED,
    student: 'USR-1005',
    officer: 'OFF-2004',
    address: 'Shantikunj Bhavan, MCA Lab-2, Second Floor',
    block: 'Computer Science Zone',
    submitted: 6,
    evidence: [file('lab2-switch.jpg', 'image', 968), file('network-log.pdf', 'pdf', 118)],
    remarks: [
      { by: 'Mr. Sandeep Bijalwan', role: 'Officer', message: 'Switch appears faulty. Replacement unit requested from the purchase section.', daysAgo: 4 },
      { by: 'Dr. Shailendra Prakash Dwivedi', role: 'Admin', message: 'Deadline exceeded. Escalating to department head for immediate procurement approval.', daysAgo: 1 },
    ],
    keywords: ['internet', 'network', 'lab', 'switch', 'lan'],
  },
  {
    title: 'Broken window glass in Classroom B-110',
    description:
      'The window pane on the left side of classroom B-110 broke during last week\'s storm. Sharp glass pieces are still fixed in the frame and rain water enters the classroom, wetting the last two benches.',
    category: 'Classroom',
    department: 'Nirman Vibhag',
    priority: PRIORITY.HIGH,
    status: STATUS.ASSIGNED,
    student: 'USR-1008',
    officer: 'OFF-2001',
    address: 'Academic Block B, Room 110, First Floor',
    block: 'Academic Zone',
    submitted: 2,
    evidence: [file('broken-window.jpg', 'image', 1123)],
    keywords: ['window', 'glass', 'classroom', 'repair'],
  },
  {
    title: 'Drainage blockage behind Annapurna Bhavan',
    description:
      'The open drain behind the dining hall is completely blocked with waste and stagnant water has accumulated for nearly a week. There is a strong smell and mosquito breeding has increased in the surrounding area.',
    category: 'Water',
    department: 'Jal Kal Vibhag',
    priority: PRIORITY.URGENT,
    status: STATUS.PENDING,
    student: 'USR-1006',
    officer: 'OFF-2002',
    address: 'Rear Service Lane, Annapurna Bhavan',
    block: 'Dining Zone',
    submitted: 5,
    evidence: [file('drain-block.jpg', 'image', 1440), file('drain-side.jpg', 'image', 902)],
    remarks: [
      { by: 'Er. Pankaj Kumar Semwal', role: 'Officer', message: 'Suction machine is engaged at the boys hostel site. Work will start on Thursday.', daysAgo: 2 },
    ],
    keywords: ['drainage', 'blockage', 'sanitation', 'stagnant'],
  },
  {
    title: 'Street light not working on the path to Library',
    description:
      'Four street lights on the walkway between the Administrative Block and the Central Library are not switching on after 7 PM. The stretch becomes completely dark and it is unsafe for students returning from the evening reading session.',
    category: 'Electricity',
    department: 'Vidyut Vibhag',
    priority: PRIORITY.HIGH,
    status: STATUS.RESOLVED,
    student: 'USR-1004',
    officer: 'OFF-2006',
    address: 'Walkway between Administrative Block and Central Library',
    block: 'Central Campus',
    submitted: 16,
    resolvedAfter: 2,
    evidence: [file('street-light-dark.jpg', 'image', 388)],
    resolution: {
      notes:
        'Faulty photocell sensor on the pole circuit was replaced and two fused LED fittings were changed. The full stretch was tested after sunset.',
      proof: [file('street-light-fixed.jpg', 'image', 455)],
    },
    feedback: { rating: 4, comment: 'Lights are working now. Took a little time but the work is good.', satisfied: true },
    keywords: ['street light', 'dark', 'safety', 'led'],
  },
  {
    title: 'Projector not displaying in Seminar Hall',
    description:
      'The ceiling projector in the seminar hall shows a blank blue screen even after connecting the HDMI cable to two different laptops. A national webinar is scheduled here next week.',
    category: 'Computer/Lab',
    department: 'MCA Lab / Computer Lab',
    priority: PRIORITY.HIGH,
    status: STATUS.IN_PROGRESS,
    student: 'USR-1005',
    officer: 'OFF-2008',
    address: 'Seminar Hall, Shantikunj Bhavan, Ground Floor',
    block: 'Computer Science Zone',
    submitted: 3,
    evidence: [file('projector-blue-screen.jpg', 'image', 731)],
    remarks: [
      { by: 'Ms. Ritika Chamoli', role: 'Officer', message: 'HDMI port of the projector is damaged. Testing with a VGA converter as a temporary arrangement.', daysAgo: 1 },
    ],
    keywords: ['projector', 'hdmi', 'seminar hall', 'display'],
  },
  {
    title: 'Bathroom tap continuously running in Devi Bhavan',
    description:
      'The wash basin tap on the second floor of Devi Bhavan cannot be closed fully and water keeps running throughout the day. A large amount of water is being wasted every day.',
    category: 'Water',
    department: 'Jal Kal Vibhag',
    priority: PRIORITY.MEDIUM,
    status: STATUS.RESOLVED,
    student: 'USR-1004',
    officer: 'OFF-2002',
    address: 'Devi Bhavan, Second Floor Common Washroom',
    block: 'Hostel Zone B',
    submitted: 21,
    resolvedAfter: 4,
    evidence: [file('running-tap.jpg', 'image', 296)],
    resolution: {
      notes: 'Tap cartridge and washer replaced. Water flow checked and no leakage observed after fitting.',
      proof: [],
    },
    feedback: { rating: 2, comment: 'The tap was fixed but it started dripping again after a few days.', satisfied: false },
    keywords: ['tap', 'water wastage', 'washroom', 'hostel'],
  },
  {
    title: 'Loose electrical socket sparking in Hostel Room 214',
    description:
      'The wall socket beside the study table in room 214 sparks whenever a laptop charger is plugged in. There is a burnt smell and a black mark has appeared on the switch board.',
    category: 'Electricity',
    department: 'Vidyut Vibhag',
    priority: PRIORITY.URGENT,
    status: STATUS.RESOLVED,
    student: 'USR-1001',
    officer: 'OFF-2003',
    address: 'Gayatri Bhavan, Room 214, Second Floor',
    block: 'Hostel Zone A',
    submitted: 9,
    resolvedAfter: 1,
    evidence: [file('socket-burn-mark.jpg', 'image', 612)],
    resolution: {
      notes:
        'Complete switch board was replaced with an ISI marked modular unit and the branch wiring was checked for insulation damage. Earthing continuity verified.',
      proof: [file('socket-replaced.jpg', 'image', 508), file('safety-check.pdf', 'pdf', 96)],
    },
    feedback: { rating: 5, comment: 'Officer came within an hour of the complaint. Excellent response.', satisfied: true },
    keywords: ['socket', 'spark', 'fire hazard', 'wiring'],
  },
  {
    title: 'Desk and bench damaged in Classroom A-105',
    description:
      'Six benches in classroom A-105 have broken side supports and two desks have loose tops. Students sitting on them are at risk of injury during lectures.',
    category: 'Classroom',
    department: 'Nirman Vibhag',
    priority: PRIORITY.MEDIUM,
    status: STATUS.ACCEPTED,
    student: 'USR-1008',
    officer: 'OFF-2005',
    address: 'Academic Block A, Room 105, Ground Floor',
    block: 'Academic Zone',
    submitted: 7,
    evidence: [file('broken-bench.jpg', 'image', 786)],
    remarks: [
      { by: 'Mr. Girish Chandra Bahuguna', role: 'Officer', message: 'Carpentry team will visit on Saturday when classes are not in session.', daysAgo: 3 },
    ],
    keywords: ['furniture', 'bench', 'desk', 'carpentry'],
  },
  {
    title: 'RO water purifier not dispensing in Chetna Bhavan',
    description:
      'The RO purifier installed on the ground floor of Chetna Bhavan stopped dispensing water three days ago. The indicator light is on but no water comes out. Around 120 residents depend on this unit.',
    category: 'Water',
    department: 'Jal Kal Vibhag',
    priority: PRIORITY.HIGH,
    status: STATUS.ESCALATED,
    student: 'USR-1003',
    officer: 'OFF-2002',
    address: 'Chetna Bhavan, Ground Floor Water Point',
    block: 'Hostel Zone C',
    submitted: 8,
    evidence: [file('ro-unit.jpg', 'image', 545)],
    remarks: [
      { by: 'Er. Pankaj Kumar Semwal', role: 'Officer', message: 'Membrane and filter cartridge need replacement. AMC vendor has been informed.', daysAgo: 5 },
    ],
    keywords: ['ro', 'purifier', 'drinking water', 'hostel'],
  },
  {
    title: 'Computer system not booting in Lab-1, Terminal 12',
    description:
      'Terminal number 12 in MCA Lab-1 does not boot. The power LED glows but the monitor shows no signal. It was working normally until last Friday.',
    category: 'Computer/Lab',
    department: 'MCA Lab / Computer Lab',
    priority: PRIORITY.MEDIUM,
    status: STATUS.RESOLVED,
    student: 'USR-1007',
    officer: 'OFF-2004',
    address: 'Shantikunj Bhavan, MCA Lab-1, Terminal 12',
    block: 'Computer Science Zone',
    submitted: 14,
    resolvedAfter: 2,
    evidence: [],
    resolution: {
      notes: 'Faulty SMPS unit was replaced and the RAM modules were reseated. System booted successfully and was tested with the lab software image.',
      proof: [file('terminal12-fixed.jpg', 'image', 402)],
    },
    feedback: { rating: 5, comment: 'System is working perfectly now.', satisfied: true },
    keywords: ['computer', 'boot', 'smps', 'terminal'],
  },
  {
    title: 'Seepage on the ceiling of Library reading room',
    description:
      'Water seepage marks have appeared on the ceiling of the first floor reading room. Plaster has started peeling and drops fall on the reading tables when it rains.',
    category: 'Building',
    department: 'Nirman Vibhag',
    priority: PRIORITY.HIGH,
    status: STATUS.IN_PROGRESS,
    student: 'USR-1006',
    officer: 'OFF-2001',
    address: 'Central Library, First Floor Reading Room',
    block: 'Central Campus',
    submitted: 10,
    evidence: [file('ceiling-seepage.jpg', 'image', 1201), file('peeling-plaster.jpg', 'image', 887)],
    remarks: [
      { by: 'Er. Devendra Singh Rawat', role: 'Officer', message: 'Terrace waterproofing survey completed. Chemical treatment will start next week.', daysAgo: 4 },
    ],
    keywords: ['seepage', 'ceiling', 'waterproofing', 'library'],
  },
  {
    title: 'Power fluctuation damaging lab equipment',
    description:
      'Frequent voltage fluctuation is observed in the computer lab wing between 2 PM and 4 PM. Two UPS units have already tripped and one monitor stopped working after a surge.',
    category: 'Electricity',
    department: 'Vidyut Vibhag',
    priority: PRIORITY.URGENT,
    status: STATUS.UNDER_REVIEW,
    student: 'USR-1005',
    officer: null,
    address: 'Shantikunj Bhavan, Computer Lab Wing',
    block: 'Computer Science Zone',
    submitted: 1,
    evidence: [file('voltage-log.pdf', 'pdf', 156)],
    keywords: ['voltage', 'fluctuation', 'surge', 'ups'],
  },
  {
    title: 'Hostel corridor light fittings missing',
    description:
      'Three light fittings in the first floor corridor of Gayatri Bhavan have been removed for repair two weeks ago and were never reinstalled. The corridor stays dark at night.',
    category: 'Hostel',
    department: 'Vidyut Vibhag',
    priority: PRIORITY.MEDIUM,
    status: STATUS.PENDING,
    student: 'USR-1007',
    officer: 'OFF-2006',
    address: 'Gayatri Bhavan, First Floor Corridor',
    block: 'Hostel Zone A',
    submitted: 12,
    evidence: [],
    remarks: [
      { by: 'Mr. Anil Kumar Kandwal', role: 'Officer', message: 'Fittings are out of stock in the electrical store. Indent has been raised.', daysAgo: 6 },
    ],
    keywords: ['light fitting', 'corridor', 'hostel', 'dark'],
  },
  {
    title: 'Printer in MCA department not responding',
    description:
      'The shared network printer in the MCA department office shows offline status on all connected systems. Students are not able to take printouts of assignments and project reports.',
    category: 'Computer/Lab',
    department: 'MCA Lab / Computer Lab',
    priority: PRIORITY.LOW,
    status: STATUS.CLOSED,
    student: 'USR-1001',
    officer: 'OFF-2008',
    address: 'MCA Department Office, Shantikunj Bhavan',
    block: 'Computer Science Zone',
    submitted: 26,
    resolvedAfter: 3,
    evidence: [],
    resolution: {
      notes: 'Print spooler service was reset and a static IP was assigned to the printer so it no longer drops off the network.',
      proof: [],
    },
    feedback: { rating: 4, comment: 'Working fine now.', satisfied: true },
    keywords: ['printer', 'network', 'offline', 'department'],
  },
  {
    title: 'Overflowing water tank on hostel terrace',
    description:
      'The overhead tank on the Chetna Bhavan terrace overflows every morning because the float valve is not working. A large quantity of water is wasted daily and the terrace stays wet.',
    category: 'Water',
    department: 'Jal Kal Vibhag',
    priority: PRIORITY.MEDIUM,
    status: STATUS.SUBMITTED,
    student: 'USR-1003',
    officer: null,
    address: 'Chetna Bhavan, Terrace Overhead Tank',
    block: 'Hostel Zone C',
    submitted: 0,
    evidence: [file('tank-overflow.jpg', 'image', 623)],
    keywords: ['overflow', 'tank', 'float valve', 'water wastage'],
  },
  {
    title: 'Main gate approach road has large potholes',
    description:
      'The approach road from Gate No. 2 to the parking area has developed several deep potholes. Two-wheelers skid during rain and it becomes difficult for the university bus to pass.',
    category: 'Building',
    department: 'Nirman Vibhag',
    priority: PRIORITY.MEDIUM,
    status: STATUS.REOPENED,
    student: 'USR-1002',
    officer: 'OFF-2001',
    address: 'Approach Road, Gate No. 2 to Parking Area',
    block: 'Campus Periphery',
    submitted: 30,
    resolvedAfter: 8,
    evidence: [file('road-potholes.jpg', 'image', 1345)],
    resolution: {
      notes: 'Potholes were filled with cold mix bitumen as a temporary measure pending full re-carpeting approval.',
      proof: [],
    },
    feedback: { rating: 2, comment: 'The filling washed away in the first rain. The road is in the same condition again.', satisfied: false },
    keywords: ['road', 'pothole', 'civil', 'repair'],
  },
  {
    title: 'Air conditioner not cooling in Server Room',
    description:
      'The split AC in the server room is running but not cooling. Room temperature crossed 34 degrees today and the rack cooling alarm is beeping continuously.',
    category: 'Electricity',
    department: 'Vidyut Vibhag',
    priority: PRIORITY.URGENT,
    status: STATUS.IN_PROGRESS,
    student: 'USR-1005',
    officer: 'OFF-2003',
    address: 'Server Room, Shantikunj Bhavan, Ground Floor',
    block: 'Computer Science Zone',
    submitted: 1,
    evidence: [file('server-room-temp.jpg', 'image', 344)],
    remarks: [
      { by: 'Er. Naveen Chandra Painuli', role: 'Officer', message: 'Gas pressure is low. Refilling scheduled today evening. Portable cooler arranged as a temporary measure.', daysAgo: 0 },
    ],
    keywords: ['air conditioner', 'server room', 'cooling', 'urgent'],
  },
  {
    title: 'Washroom door lock broken in Academic Block A',
    description:
      'The latch of the ladies washroom door on the ground floor of Academic Block A is broken and the door does not stay closed. This is a serious privacy concern.',
    category: 'Building',
    department: 'Nirman Vibhag',
    priority: PRIORITY.HIGH,
    status: STATUS.RESOLVED,
    student: 'USR-1002',
    officer: 'OFF-2005',
    address: 'Academic Block A, Ground Floor Washroom',
    block: 'Academic Zone',
    submitted: 18,
    resolvedAfter: 1,
    evidence: [],
    resolution: {
      notes: 'New tower bolt and door latch installed, hinges tightened and door alignment corrected.',
      proof: [file('door-lock-fixed.jpg', 'image', 289)],
    },
    feedback: { rating: 5, comment: 'Resolved on the same day. Very satisfied with the response.', satisfied: true },
    keywords: ['door', 'lock', 'washroom', 'safety'],
  },
  {
    title: 'Wi-Fi signal very weak in the hostel study hall',
    description:
      'The Wi-Fi access point in the Gayatri Bhavan study hall gives a very weak signal. Students cannot attend online classes or download study material from the LMS during evening hours.',
    category: 'Computer/Lab',
    department: 'MCA Lab / Computer Lab',
    priority: PRIORITY.MEDIUM,
    status: STATUS.ASSIGNED,
    student: 'USR-1007',
    officer: 'OFF-2008',
    address: 'Gayatri Bhavan, Study Hall, Ground Floor',
    block: 'Hostel Zone A',
    submitted: 2,
    evidence: [file('wifi-signal.jpg', 'image', 214)],
    keywords: ['wifi', 'signal', 'access point', 'hostel'],
  },
  {
    title: 'Wall plaster falling in Yagyashala corridor',
    description:
      'Chunks of plaster are falling from the corridor wall near the Yagyashala. A piece fell close to a group of visiting students yesterday. The affected area needs immediate barricading and repair.',
    category: 'Building',
    department: 'Nirman Vibhag',
    priority: PRIORITY.URGENT,
    status: STATUS.ACCEPTED,
    student: 'USR-1006',
    officer: 'OFF-2001',
    address: 'Yagyashala Corridor, North Wing',
    block: 'Central Campus',
    submitted: 1,
    evidence: [file('falling-plaster.jpg', 'image', 1032)],
    remarks: [
      { by: 'Er. Devendra Singh Rawat', role: 'Officer', message: 'Area barricaded immediately. Masonry team deployed for plaster removal and re-plastering.', daysAgo: 0 },
    ],
    keywords: ['plaster', 'wall', 'safety hazard', 'civil'],
  },
  {
    title: 'Geyser not heating water in Saraswati Bhavan',
    description:
      'The geyser in the second floor bathroom of Saraswati Bhavan is not heating water at all. During the winter months it is very difficult for residents without hot water.',
    category: 'Hostel',
    department: 'Vidyut Vibhag',
    priority: PRIORITY.MEDIUM,
    status: STATUS.PENDING,
    student: 'USR-1002',
    officer: 'OFF-2006',
    address: 'Saraswati Bhavan, Second Floor Bathroom',
    block: 'Hostel Zone B',
    submitted: 13,
    evidence: [],
    remarks: [
      { by: 'Mr. Anil Kumar Kandwal', role: 'Officer', message: 'Heating element found faulty. Waiting for the replacement element to arrive.', daysAgo: 7 },
    ],
    keywords: ['geyser', 'hot water', 'heating element', 'hostel'],
  },
  {
    title: 'Sewage smell from the manhole near the sports ground',
    description:
      'A strong sewage smell is coming from the manhole beside the sports ground entrance. The cover is also partially broken which makes it dangerous for players in the evening.',
    category: 'Water',
    department: 'Jal Kal Vibhag',
    priority: PRIORITY.HIGH,
    status: STATUS.UNDER_REVIEW,
    student: 'USR-1003',
    officer: null,
    address: 'Sports Ground Entrance, Near Manhole SG-04',
    block: 'Sports Zone',
    submitted: 0,
    evidence: [file('manhole-broken.jpg', 'image', 764)],
    keywords: ['sewage', 'manhole', 'smell', 'sanitation'],
  },
  {
    title: 'Lab software licence expired on all lab machines',
    description:
      'The database software licence has expired on all lab systems and shows an activation prompt at startup. The DBMS practical batch of second semester cannot proceed with the lab work.',
    category: 'Computer/Lab',
    department: 'MCA Lab / Computer Lab',
    priority: PRIORITY.HIGH,
    status: STATUS.IN_PROGRESS,
    student: 'USR-1001',
    officer: 'OFF-2004',
    address: 'Shantikunj Bhavan, MCA Lab-1 and Lab-2',
    block: 'Computer Science Zone',
    submitted: 3,
    evidence: [file('license-expired.jpg', 'image', 178)],
    remarks: [
      { by: 'Mr. Sandeep Bijalwan', role: 'Officer', message: 'Renewal request forwarded to the accounts section. Trial licence applied so that practicals can continue.', daysAgo: 1 },
    ],
    keywords: ['software', 'licence', 'lab', 'dbms'],
  },
  {
    title: 'Fan regulator sparking in Reading Room 3',
    description:
      'The fan regulator in reading room 3 sparks and produces a crackling sound when the speed is changed. Students have stopped using that fan out of fear.',
    category: 'Electricity',
    department: 'Vidyut Vibhag',
    priority: PRIORITY.LOW,
    status: STATUS.SUBMITTED,
    student: 'USR-1008',
    officer: null,
    address: 'Central Library, Reading Room 3',
    block: 'Central Campus',
    submitted: 0,
    evidence: [],
    keywords: ['regulator', 'spark', 'fan', 'library'],
  },
]

/* ------------------------------------------------------- record expansion */

/**
 * Turn one seed into a complete complaint record.
 * The simulated AI prediction is derived from the seed so the classification
 * card always agrees with the rest of the record.
 */
function expandSeed(seed, index) {
  const student = studentById(seed.student)
  const officer = seed.officer ? officerById(seed.officer) : null
  const submittedAt = daysAgo(seed.submitted, 9 + (index % 8), (index * 7) % 60)
  const deadline = calculateDeadline(submittedAt, seed.priority)

  const isClosed = [STATUS.RESOLVED, STATUS.CLOSED].includes(seed.status)
  const resolvedAt =
    isClosed && seed.resolvedAfter != null
      ? daysAgo(Math.max(seed.submitted - seed.resolvedAfter, 0), 16, 30)
      : null

  const lastRemarkDays = seed.remarks?.length
    ? Math.min(...seed.remarks.map((r) => r.daysAgo))
    : null
  const updatedAt =
    resolvedAt ??
    (lastRemarkDays != null ? daysAgo(lastRemarkDays, 15, 40) : submittedAt)

  const overdueDays = isClosed ? 0 : Math.max(-daysUntil(deadline), 0)
  const escalationLevel =
    seed.status === STATUS.ESCALATED
      ? escalationLevelForOverdue(overdueDays)
      : overdueDays > 0 && !isClosed
        ? 1
        : 0

  const id = `${UNIVERSITY_SHORT}-GRV-2026-${String(101 + index).padStart(5, '0')}`

  const complaint = {
    id,
    title: seed.title,
    description: seed.description,
    category: seed.category,
    department: seed.department,
    priority: seed.priority,
    status: seed.status,

    submittedBy: complainant(student),
    assignedOfficer: handler(officer),

    location: {
      ...campusPoint(index),
      address: seed.address,
      block: seed.block,
      accuracy: 8 + (index % 5) * 3,
    },

    evidence: seed.evidence ?? [],

    // Simulated AI output. Replaced by the Flask /api/ai/classify response later.
    ai: {
      department: seed.department,
      priority: seed.priority,
      confidence: 0.87 + ((index * 13) % 11) / 100,
      duplicateProbability: ((index * 17) % 34) / 100,
      suggestedOfficer: officer?.designation ?? 'Department Head',
      keywords: seed.keywords ?? [],
      analysedAt: submittedAt,
    },

    submittedAt,
    updatedAt,
    deadline,
    resolvedAt,

    escalationLevel,
    escalationAuthority: escalationLevel
      ? escalationAuthority(escalationLevel)
      : null,
    daysOverdue: overdueDays,

    remarks: (seed.remarks ?? []).map((remark, remarkIndex) => ({
      id: `${id}-rm-${remarkIndex}`,
      author: remark.by,
      role: remark.role,
      message: remark.message,
      at: daysAgo(remark.daysAgo, 14, 20),
    })),

    resolution: seed.resolution
      ? {
          notes: seed.resolution.notes,
          proof: seed.resolution.proof ?? [],
          completedAt: resolvedAt ?? updatedAt,
          completedBy: officer?.name ?? 'Department Officer',
        }
      : null,

    feedback: seed.feedback
      ? {
          rating: seed.feedback.rating,
          comment: seed.feedback.comment,
          satisfied: seed.feedback.satisfied,
          at: resolvedAt ?? updatedAt,
        }
      : null,
  }

  complaint.timeline = buildTimeline(complaint)
  return complaint
}

/** The seeded complaint list used by `complaintService`. */
export const complaints = SEEDS.map(expandSeed)

export default complaints
