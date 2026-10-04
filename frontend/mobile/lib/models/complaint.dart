import '../core/config/constants.dart';

/// One evidence file, as `file_utils.save_file` stores it.
class Evidence {
  const Evidence({
    required this.url,
    required this.name,
    required this.kind,
    this.size = 0,
  });

  final String url; // "/api/files/evidence/xxxx.jpg" - relative to the host
  final String name;
  final String kind; // image | pdf | doc
  final int size;

  bool get isImage => kind == 'image';

  factory Evidence.fromJson(Map<String, dynamic> json) => Evidence(
        url: '${json['url'] ?? ''}',
        name: '${json['originalName'] ?? json['name'] ?? 'attachment'}',
        kind: '${json['kind'] ?? 'doc'}',
        size: (json['size'] as num?)?.toInt() ?? 0,
      );
}

/// Where the complaint is. Latitude/longitude are what the server validates
/// against the campus fence, and `address` is the required landmark.
class ComplaintLocation {
  const ComplaintLocation({
    this.latitude,
    this.longitude,
    this.address = '',
    this.building = '',
    this.floor = '',
    this.room = '',
  });

  final double? latitude;
  final double? longitude;
  final String address;
  final String building;
  final String floor;
  final String room;

  bool get hasCoordinates => latitude != null && longitude != null;

  /// One readable line for a card: landmark first, then the finer detail.
  String get summary {
    final parts = [address, building, floor, room]
        .where((p) => p.trim().isNotEmpty)
        .toList();
    return parts.isEmpty ? 'Location not specified' : parts.join(' - ');
  }

  factory ComplaintLocation.fromJson(Map<String, dynamic> json) =>
      ComplaintLocation(
        latitude: (json['latitude'] as num?)?.toDouble(),
        longitude: (json['longitude'] as num?)?.toDouble(),
        address: '${json['address'] ?? ''}',
        building: '${json['building'] ?? ''}',
        floor: '${json['floor'] ?? ''}',
        room: '${json['room'] ?? ''}',
      );

  Map<String, dynamic> toJson() => {
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
        'address': address,
        if (building.isNotEmpty) 'building': building,
        if (floor.isNotEmpty) 'floor': floor,
        if (room.isNotEmpty) 'room': room,
      };
}

/// One entry in the complaint timeline.
class TimelineEntry {
  const TimelineEntry({
    required this.status,
    required this.note,
    required this.at,
    this.byName = '',
  });

  final String status;
  final String note;
  final DateTime? at;
  final String byName;

  factory TimelineEntry.fromJson(Map<String, dynamic> json) {
    final by = json['by'];
    return TimelineEntry(
      status: '${json['status'] ?? json['action'] ?? ''}',
      note: '${json['note'] ?? json['message'] ?? ''}',
      at: DateTime.tryParse('${json['at'] ?? json['createdAt'] ?? ''}'),
      byName: by is Map ? '${by['name'] ?? ''}' : '${by ?? ''}',
    );
  }
}

/// A remark on a complaint.
class Remark {
  const Remark({required this.message, required this.at, this.byName = ''});

  final String message;
  final DateTime? at;
  final String byName;

  factory Remark.fromJson(Map<String, dynamic> json) {
    final by = json['by'];
    return Remark(
      message: '${json['message'] ?? ''}',
      at: DateTime.tryParse('${json['at'] ?? json['createdAt'] ?? ''}'),
      byName: by is Map ? '${by['name'] ?? ''}' : '${by ?? ''}',
    );
  }
}

/// The server-side AI analysis block. The server always recomputes this, so
/// the app only ever displays it.
class AiAnalysis {
  const AiAnalysis({
    this.department = '',
    this.priority = '',
    this.confidence = 0,
    this.reason = '',
  });

  final String department;
  final String priority;
  final double confidence;
  final String reason;

  /// Confidence arrives either as 0-1 or already as a percentage.
  int get confidencePercent {
    final value = confidence <= 1 ? confidence * 100 : confidence;
    return value.round().clamp(0, 100);
  }

  factory AiAnalysis.fromJson(Map<String, dynamic> json) => AiAnalysis(
        department: '${json['department'] ?? ''}',
        priority: '${json['priority'] ?? ''}',
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
        reason: '${json['reason'] ?? json['priorityReason'] ?? ''}',
      );
}

/// A complaint, matching what `complaint_service` stores and decorates.
class Complaint {
  const Complaint({
    required this.id,
    required this.title,
    required this.description,
    required this.category,
    required this.department,
    required this.priority,
    required this.status,
    this.location = const ComplaintLocation(),
    this.evidence = const [],
    this.timeline = const [],
    this.remarks = const [],
    this.ai,
    this.submittedByName = '',
    this.submittedById = '',
    this.assignedOfficerName = '',
    this.assignedOfficerId = '',
    this.submittedAt,
    this.updatedAt,
    this.deadline,
    this.resolvedAt,
    this.escalationLevel = 0,
    this.daysOverdue = 0,
    this.resolutionNotes = '',
    this.resolutionProof = const [],
    this.feedbackRating,
    this.feedbackComment = '',
  });

  final String id;
  final String title;
  final String description;
  final String category;
  final String department;
  final String priority;
  final String status;
  final ComplaintLocation location;
  final List<Evidence> evidence;
  final List<TimelineEntry> timeline;
  final List<Remark> remarks;
  final AiAnalysis? ai;
  final String submittedByName;
  final String submittedById;
  final String assignedOfficerName;
  final String assignedOfficerId;
  final DateTime? submittedAt;
  final DateTime? updatedAt;
  final DateTime? deadline;
  final DateTime? resolvedAt;
  final int escalationLevel;
  final int daysOverdue;
  final String resolutionNotes;
  final List<Evidence> resolutionProof;
  final int? feedbackRating;
  final String feedbackComment;

  bool get isActive => Domain.activeStatuses.contains(status);
  bool get isResolved => status == Domain.statusResolved;
  bool get isClosed => Domain.closedStatuses.contains(status);
  bool get isOverdue => daysOverdue > 0 && isActive;
  bool get hasFeedback => feedbackRating != null;

  /// A student may rate a complaint only once it has been resolved or closed.
  bool get canGiveFeedback => isClosed && !hasFeedback;

  /// Reopening is offered on a finished complaint that did not actually help.
  bool get canReopen => isClosed;

  factory Complaint.fromJson(Map<String, dynamic> json) {
    final submittedBy = json['submittedBy'];
    final officer = json['assignedOfficer'];
    final resolution = json['resolution'];
    final feedback = json['feedback'];

    List<Evidence> files(dynamic raw) => (raw is List)
        ? raw
            .whereType<Map<String, dynamic>>()
            .map(Evidence.fromJson)
            .toList()
        : const [];

    return Complaint(
      id: '${json['id'] ?? ''}',
      title: '${json['title'] ?? ''}',
      description: '${json['description'] ?? ''}',
      category: '${json['category'] ?? ''}',
      department: '${json['department'] ?? ''}',
      priority: '${json['priority'] ?? Domain.priorityMedium}',
      status: '${json['status'] ?? Domain.statusSubmitted}',
      location: json['location'] is Map<String, dynamic>
          ? ComplaintLocation.fromJson(json['location'] as Map<String, dynamic>)
          : const ComplaintLocation(),
      evidence: files(json['evidence']),
      timeline: (json['timeline'] is List)
          ? (json['timeline'] as List)
              .whereType<Map<String, dynamic>>()
              .map(TimelineEntry.fromJson)
              .toList()
          : const [],
      remarks: (json['remarks'] is List)
          ? (json['remarks'] as List)
              .whereType<Map<String, dynamic>>()
              .map(Remark.fromJson)
              .toList()
          : const [],
      ai: json['ai'] is Map<String, dynamic>
          ? AiAnalysis.fromJson(json['ai'] as Map<String, dynamic>)
          : null,
      submittedByName: submittedBy is Map ? '${submittedBy['name'] ?? ''}' : '',
      submittedById: submittedBy is Map ? '${submittedBy['id'] ?? ''}' : '',
      assignedOfficerName: officer is Map ? '${officer['name'] ?? ''}' : '',
      assignedOfficerId: officer is Map ? '${officer['id'] ?? ''}' : '',
      submittedAt: DateTime.tryParse('${json['submittedAt'] ?? ''}'),
      updatedAt: DateTime.tryParse('${json['updatedAt'] ?? ''}'),
      deadline: DateTime.tryParse('${json['deadline'] ?? ''}'),
      resolvedAt: DateTime.tryParse('${json['resolvedAt'] ?? ''}'),
      escalationLevel: (json['escalationLevel'] as num?)?.toInt() ?? 0,
      daysOverdue: (json['daysOverdue'] as num?)?.toInt() ?? 0,
      resolutionNotes:
          resolution is Map ? '${resolution['notes'] ?? ''}' : '',
      resolutionProof:
          resolution is Map ? files(resolution['proof']) : const [],
      feedbackRating:
          feedback is Map ? (feedback['rating'] as num?)?.toInt() : null,
      feedbackComment: feedback is Map ? '${feedback['comment'] ?? ''}' : '',
    );
  }
}

/// The paginated envelope every complaint list endpoint returns.
class Paginated<T> {
  const Paginated({
    required this.items,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.totalPages,
  });

  final List<T> items;
  final int total;
  final int page;
  final int pageSize;
  final int totalPages;

  bool get hasMore => page < totalPages;

  static Paginated<T> empty<T>() =>
      Paginated<T>(items: const [], total: 0, page: 1, pageSize: 10, totalPages: 0);

  /// Handles both shapes described in MOBILE_API.md section 5: the paginated
  /// envelope, and the bare array some endpoints return without `?page=`.
  factory Paginated.fromJson(
    dynamic raw,
    T Function(Map<String, dynamic>) parse,
  ) {
    if (raw is List) {
      final items =
          raw.whereType<Map<String, dynamic>>().map(parse).toList();
      return Paginated<T>(
        items: items,
        total: items.length,
        page: 1,
        pageSize: items.length,
        totalPages: 1,
      );
    }

    final map = raw is Map<String, dynamic> ? raw : <String, dynamic>{};
    final list = map['items'];
    return Paginated<T>(
      items: list is List
          ? list.whereType<Map<String, dynamic>>().map(parse).toList()
          : const [],
      total: (map['total'] as num?)?.toInt() ?? 0,
      page: (map['page'] as num?)?.toInt() ?? 1,
      pageSize: (map['pageSize'] as num?)?.toInt() ?? 10,
      totalPages: (map['totalPages'] as num?)?.toInt() ?? 0,
    );
  }
}
