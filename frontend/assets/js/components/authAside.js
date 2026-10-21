/**
 * Decorative panel beside the login and registration forms.
 * Hidden below 1024px, where the form takes the whole screen.
 */

import { icon } from './dom.js'
import { mountChatbot } from './chatbot.js'
import { initLanguage } from './language.js'

const POINTS = [
  'Register a grievance in under two minutes with photo and location evidence',
  'Automatic routing to the correct department with a priority and a deadline',
  'Live status tracking, notifications and escalation if a deadline is missed',
  'Rate the resolution, or reopen the complaint if the work is not satisfactory',
]

export function authAside() {
  initLanguage()
  mountChatbot()
  return `
    <div>
      <img
        class="auth__university-logo"
        src="/assets/img/dsvv-wordmark.png"
        alt="Dev Sanskriti Vishwavidyalaya"
        width="2048"
        height="488"
      >
      <h2>One window for every campus grievance</h2>
      <p>
        Our grievance management system connects students and staff directly with the department
        that can fix the problem.
      </p>

      <ul class="auth__points">
        ${POINTS.map(
          (point) => `<li class="auth__point">${icon('check-circle', 'icon-md')}<span>${point}</span></li>`,
        ).join('')}
      </ul>
    </div>

    <p class="auth__note">Developed by Amit Kumar, MCA 2nd Year Student, Department of Computer Science</p>`
}

export default authAside
