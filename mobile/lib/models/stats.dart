/// Dashboard counters from `GET /api/complaints/statistics`.
///
/// The endpoint scopes itself to the caller: a student gets their own totals,
/// an officer their queue, an admin the whole system. The app therefore uses
/// one model for all three roles.
class ComplaintStats {
  const ComplaintStats({
    this.total = 0,
    this.submitted = 0,
    this.underReview = 0,
    this.assigned = 0,
    this.accepted = 0,
    this.pending = 0,
    this.inProgress = 0,
    this.resolved = 0,
    this.reopened = 0,
    this.escalated = 0,
    this.overdue = 0,
    this.byStatus = const {},
    this.byDepartment = const {},
    this.byPriority = const {},
  });

  final int total;
  final int submitted;
  final int underReview;
  final int assigned;
  final int accepted;
  final int pending;
  final int inProgress;
  final int resolved;
  final int reopened;
  final int escalated;
  final int overdue;
  final Map<String, int> byStatus;
  final Map<String, int> byDepartment;
  final Map<String, int> byPriority;

  /// Share of complaints that reached Resolved or Closed, 0-100.
  int get resolutionRate =>
      total == 0 ? 0 : ((resolved / total) * 100).round();

  static Map<String, int> _counts(dynamic raw) {
    if (raw is! Map) return const {};
    final result = <String, int>{};
    raw.forEach((key, value) {
      final count = (value as num?)?.toInt();
      if (count != null) result['$key'] = count;
    });
    return result;
  }

  factory ComplaintStats.fromJson(Map<String, dynamic> json) {
    int read(String key) => (json[key] as num?)?.toInt() ?? 0;
    return ComplaintStats(
      total: read('total'),
      submitted: read('submitted'),
      underReview: read('underReview'),
      assigned: read('assigned'),
      accepted: read('accepted'),
      pending: read('pending'),
      inProgress: read('inProgress'),
      resolved: read('resolved'),
      reopened: read('reopened'),
      escalated: read('escalated'),
      overdue: read('overdue'),
      byStatus: _counts(json['byStatus']),
      byDepartment: _counts(json['byDepartment']),
      byPriority: _counts(json['byPriority']),
    );
  }
}

/// An officer in the directory, with the live workload the backend computes.
class Officer {
  const Officer({
    required this.id,
    required this.name,
    required this.email,
    this.department = '',
    this.designation = '',
    this.phone = '',
    this.isActive = true,
    this.activeCount = 0,
    this.resolvedCount = 0,
    this.totalCount = 0,
  });

  final String id;
  final String name;
  final String email;
  final String department;
  final String designation;
  final String phone;
  final bool isActive;
  final int activeCount;
  final int resolvedCount;
  final int totalCount;

  String get initials {
    final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty);
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts.first[0].toUpperCase();
    return (parts.first[0] + parts.last[0]).toUpperCase();
  }

  factory Officer.fromJson(Map<String, dynamic> json) {
    final workload = json['workload'];
    int fromWorkload(String key, String fallback) {
      if (workload is Map && workload[key] is num) {
        return (workload[key] as num).toInt();
      }
      return (json[fallback] as num?)?.toInt() ?? 0;
    }

    return Officer(
      id: '${json['id'] ?? ''}',
      name: '${json['name'] ?? ''}',
      email: '${json['email'] ?? ''}',
      department: '${json['department'] ?? ''}',
      designation: '${json['designation'] ?? ''}',
      phone: '${json['phone'] ?? ''}',
      isActive: json['isActive'] != false,
      activeCount: fromWorkload('active', 'activeComplaints'),
      resolvedCount: fromWorkload('resolved', 'resolvedComplaints'),
      totalCount: fromWorkload('total', 'totalComplaints'),
    );
  }
}

/// A department from `GET /api/departments`.
class Department {
  const Department({
    required this.code,
    required this.name,
    this.english = '',
    this.description = '',
    this.head = '',
    this.email = '',
    this.office = '',
    this.isActive = true,
    this.complaintCount = 0,
    this.officerCount = 0,
  });

  final String code;
  final String name;
  final String english;
  final String description;
  final String head;
  final String email;
  final String office;
  final bool isActive;
  final int complaintCount;
  final int officerCount;

  factory Department.fromJson(Map<String, dynamic> json) => Department(
        code: '${json['code'] ?? ''}',
        name: '${json['name'] ?? ''}',
        english: '${json['english'] ?? ''}',
        description: '${json['description'] ?? ''}',
        head: '${json['head'] ?? ''}',
        email: '${json['email'] ?? ''}',
        office: '${json['office'] ?? ''}',
        isActive: json['isActive'] != false,
        complaintCount: (json['complaintCount'] as num?)?.toInt() ??
            (json['totalComplaints'] as num?)?.toInt() ??
            0,
        officerCount: (json['officerCount'] as num?)?.toInt() ??
            (json['totalOfficers'] as num?)?.toInt() ??
            0,
      );
}

/// One `{name, value}` point, the shape `to_chart_data` produces for every
/// distribution chart in the system.
class ChartPoint {
  const ChartPoint({required this.name, required this.value});

  final String name;
  final int value;

  factory ChartPoint.fromJson(Map<String, dynamic> json) => ChartPoint(
        name: '${json['name'] ?? ''}',
        value: (json['value'] as num?)?.toInt() ?? 0,
      );

  static List<ChartPoint> listFrom(dynamic raw) {
    if (raw is! List) return const [];
    return raw
        .whereType<Map<String, dynamic>>()
        .map(ChartPoint.fromJson)
        .toList();
  }
}

/// One month of the registered-vs-resolved trend.
class TrendPoint {
  const TrendPoint({
    required this.month,
    required this.registered,
    required this.resolved,
  });

  final String month;
  final int registered;
  final int resolved;

  factory TrendPoint.fromJson(Map<String, dynamic> json) => TrendPoint(
        month: '${json['month'] ?? ''}',
        registered: (json['registered'] as num?)?.toInt() ?? 0,
        resolved: (json['resolved'] as num?)?.toInt() ?? 0,
      );
}
