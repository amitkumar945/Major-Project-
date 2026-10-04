/// Dart mirror of `backend/constants.py`.
///
/// The backend validates against these exact literals, so every dropdown in
/// the app must offer the same strings - a mismatch becomes a 422 the user
/// cannot fix.
class Domain {
  const Domain._();

  // ------------------------------------------------------------- roles
  static const String roleStudent = 'student';
  static const String roleOfficer = 'officer';
  static const String roleAdmin = 'admin';

  // ------------------------------------------------------- departments
  static const Map<String, String> departmentCodes = {
    'NIRMAN': 'Nirman Vibhag',
    'JALKAL': 'Jal Kal Vibhag',
    'VIDYUT': 'Vidyut Vibhag',
    'MCALAB': 'MCA Lab / Computer Lab',
  };

  static const List<String> departmentNames = [
    'Nirman Vibhag',
    'Jal Kal Vibhag',
    'Vidyut Vibhag',
    'MCA Lab / Computer Lab',
  ];

  // -------------------------------------------------------- categories
  static const List<String> categories = [
    'Building',
    'Water',
    'Electricity',
    'Computer/Lab',
    'Hostel',
    'Classroom',
    'Other',
  ];

  static const Map<String, String> categoryDepartment = {
    'Building': 'Nirman Vibhag',
    'Water': 'Jal Kal Vibhag',
    'Electricity': 'Vidyut Vibhag',
    'Computer/Lab': 'MCA Lab / Computer Lab',
    'Hostel': 'Nirman Vibhag',
    'Classroom': 'Nirman Vibhag',
    'Other': 'Nirman Vibhag',
  };

  // ------------------------------------------------------------ status
  static const String statusSubmitted = 'Submitted';
  static const String statusUnderReview = 'Under Review';
  static const String statusAssigned = 'Assigned';
  static const String statusAccepted = 'Accepted';
  static const String statusInProgress = 'In Progress';
  static const String statusPending = 'Pending';
  static const String statusResolved = 'Resolved';
  static const String statusClosed = 'Closed';
  static const String statusReopened = 'Reopened';
  static const String statusEscalated = 'Escalated';

  static const List<String> statusList = [
    statusSubmitted,
    statusUnderReview,
    statusAssigned,
    statusAccepted,
    statusInProgress,
    statusPending,
    statusResolved,
    statusClosed,
    statusReopened,
    statusEscalated,
  ];

  static const List<String> activeStatuses = [
    statusSubmitted,
    statusUnderReview,
    statusAssigned,
    statusAccepted,
    statusInProgress,
    statusPending,
    statusReopened,
    statusEscalated,
  ];

  static const List<String> closedStatuses = [statusResolved, statusClosed];

  /// The only statuses the backend lets an officer set
  /// (`OFFICER_STATUS_OPTIONS` in constants.py). Offering more would produce
  /// a 403 the officer cannot act on.
  static const List<String> officerStatusOptions = [
    statusAssigned,
    statusAccepted,
    statusInProgress,
    statusPending,
    statusResolved,
  ];

  // ---------------------------------------------------------- priority
  static const String priorityLow = 'Low';
  static const String priorityMedium = 'Medium';
  static const String priorityHigh = 'High';
  static const String priorityUrgent = 'Urgent';

  static const List<String> priorityList = [
    priorityLow,
    priorityMedium,
    priorityHigh,
    priorityUrgent,
  ];

  // ----------------------------------------------------------- uploads
  static const List<String> allowedExtensions = [
    'png', 'jpg', 'jpeg', 'webp', 'pdf', 'doc', 'docx',
  ];

  // ------------------------------------------- registration (student side)

  /// Courses / departments a registering user picks from. Mirrors the COURSES
  /// list in `frontend/assets/js/pages/register.js`. This is the person's own
  /// course - unrelated to the grievance departments above.
  static const List<String> courses = [
    'MCA - Department of Computer Science',
    'BCA - Department of Computer Science',
    'M.Sc. Yogic Science',
    'M.A. Clinical Psychology',
    'B.A. Journalism & Mass Communication',
    'Department of Computer Science',
    'Library & Information Centre',
    'Other Department',
  ];

  static const List<String> userTypes = ['Student', 'Staff'];

  // ------------------------------------------------------------- misc
  static const String appName = 'Grievance Management System';
  static const String universityShort = 'DSVV';
}
