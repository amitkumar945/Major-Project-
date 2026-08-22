/**
 * Form validation rules.
 *
 * Every validator returns an object of `{ fieldName: 'error message' }`.
 * An empty object means the form is valid. Pages call these before submitting
 * so validation logic is never duplicated inside components.
 */

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

export function isEmail(value = '') {
  return EMAIL_RE.test(value.trim())
}

/**
 * Password strength as a 0-4 score plus a label, shown on the register screen.
 */
export function passwordStrength(password = '') {
  let score = 0
  if (password.length >= 8) score += 1
  if (/[A-Z]/.test(password)) score += 1
  if (/[0-9]/.test(password)) score += 1
  if (/[^A-Za-z0-9]/.test(password)) score += 1
  const labels = ['Very weak', 'Weak', 'Fair', 'Good', 'Strong']
  return { score, label: labels[score] }
}

export function validateLogin({ identifier, password }) {
  const errors = {}
  if (!identifier?.trim()) errors.identifier = 'Email address is required'
  else if (!isEmail(identifier))
    errors.identifier = 'Enter a valid email address'
  if (!password) errors.password = 'Password is required'
  else if (password.length < 6)
    errors.password = 'Password must be at least 6 characters'
  return errors
}

export function validateRegistration(values) {
  const errors = {}

  if (!values.fullName?.trim()) errors.fullName = 'Full name is required'
  else if (values.fullName.trim().length < 3)
    errors.fullName = 'Full name looks too short'

  if (!values.userId?.trim()) errors.userId = 'Student / Employee ID is required'

  if (!values.email?.trim()) errors.email = 'Email address is required'
  else if (!isEmail(values.email)) errors.email = 'Enter a valid email address'

  if (!values.department) errors.department = 'Please select your department or course'

  if (!values.password) errors.password = 'Password is required'
  else if (values.password.length < 8)
    errors.password = 'Password must be at least 8 characters'

  if (!values.confirmPassword)
    errors.confirmPassword = 'Please confirm your password'
  else if (values.password !== values.confirmPassword)
    errors.confirmPassword = 'Passwords do not match'

  if (!values.acceptTerms)
    errors.acceptTerms = 'Please accept the terms to continue'

  return errors
}

export function validateComplaintDetails(values) {
  const errors = {}
  if (!values.title?.trim()) errors.title = 'Complaint title is required'
  else if (values.title.trim().length < 8)
    errors.title = 'Title should be at least 8 characters'

  if (!values.description?.trim())
    errors.description = 'Please describe the problem'
  else if (values.description.trim().length < 25)
    errors.description = 'Description should be at least 25 characters so it can be classified correctly'

  if (!values.category) errors.category = 'Select a category'
  if (!values.department) errors.department = 'Select a department'
  return errors
}

export function validateLocation(location) {
  const errors = {}
  if (location?.latitude == null || location?.longitude == null)
    errors.location = 'Capture or enter the complaint location'
  if (!location?.address?.trim())
    errors.address = 'Enter a landmark or building name'
  return errors
}

export function validateProfile(values) {
  const errors = {}
  if (!values.name?.trim()) errors.name = 'Name is required'
  if (!values.email?.trim()) errors.email = 'Email is required'
  else if (!isEmail(values.email)) errors.email = 'Enter a valid email address'
  return errors
}

export function validatePasswordChange(values) {
  const errors = {}
  if (!values.currentPassword) errors.currentPassword = 'Enter your current password'
  if (!values.newPassword) errors.newPassword = 'Enter a new password'
  else if (values.newPassword.length < 8)
    errors.newPassword = 'New password must be at least 8 characters'
  else if (values.newPassword === values.currentPassword)
    errors.newPassword = 'New password must differ from the current one'
  if (values.confirmPassword !== values.newPassword)
    errors.confirmPassword = 'Passwords do not match'
  return errors
}

export function validateOfficer(values) {
  const errors = {}
  if (!values.name?.trim()) errors.name = 'Officer name is required'
  if (!values.employeeId?.trim()) errors.employeeId = 'Employee ID is required'
  if (!values.email?.trim()) errors.email = 'Email is required'
  else if (!isEmail(values.email)) errors.email = 'Enter a valid email address'
  if (!values.department) errors.department = 'Assign a department'
  if (!values.designation?.trim()) errors.designation = 'Designation is required'
  return errors
}

export function validateDepartment(values) {
  const errors = {}
  if (!values.name?.trim()) errors.name = 'Department name is required'
  if (!values.code?.trim()) errors.code = 'Short code is required'
  if (!values.head?.trim()) errors.head = 'Department head is required'
  if (!values.email?.trim()) errors.email = 'Contact email is required'
  else if (!isEmail(values.email)) errors.email = 'Enter a valid email address'
  return errors
}

export function validateFeedback(values) {
  const errors = {}
  if (!values.rating) errors.rating = 'Please select a star rating'
  if (!values.comment?.trim()) errors.comment = 'Please write a short comment'
  else if (values.comment.trim().length < 10)
    errors.comment = 'Comment should be at least 10 characters'
  return errors
}

/** True when a validation result contains no messages. */
export function isValid(errors) {
  return Object.keys(errors).length === 0
}
