import 'dart:io';

import '../core/network/api_client.dart';
import '../models/complaint.dart';
import '../models/stats.dart';

/// Everything under `/api/complaints`, plus the AI helpers the submit form uses.
///
/// Scoping is the server's job: `/complaints` already returns only what the
/// caller may see, so the app never filters for security, only for display.
class ComplaintService {
  ComplaintService._();
  static final ComplaintService instance = ComplaintService._();

  final ApiClient _api = ApiClient.instance;

  // -------------------------------------------------------------- creation

  /// Submit a complaint, with optional camera/gallery evidence.
  ///
  /// Sent as multipart whenever files are attached: `complaint_routes._payload()`
  /// re-decodes `location` and `ai` from JSON strings in that case, which is why
  /// they are passed as maps and encoded by the client.
  Future<Complaint> create({
    required String title,
    required String description,
    required String category,
    required ComplaintLocation location,
    List<File> files = const [],
    String? department,
    String? priority,
  }) async {
    final fields = <String, dynamic>{
      'title': title.trim(),
      'description': description.trim(),
      'category': category,
      'location': location.toJson(),
      if (department != null && department.isNotEmpty) 'department': department,
      if (priority != null && priority.isNotEmpty) 'priority': priority,
    };

    final data = files.isEmpty
        ? await _api.post('/complaints', body: fields)
        : await _api.multipart('/complaints', fields: fields, files: files);

    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  /// Attach more files to an existing complaint.
  Future<Complaint> addEvidence(String complaintId, List<File> files) async {
    final data = await _api.multipart(
      '/complaints/$complaintId/evidence',
      fields: const {},
      files: files,
    );
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  // --------------------------------------------------------------- reading

  /// The signed-in student's own complaints.
  Future<Paginated<Complaint>> myComplaints({
    int page = 1,
    int pageSize = 10,
    Map<String, dynamic> filters = const {},
  }) =>
      _list('/complaints/my', page, pageSize, filters);

  /// The signed-in officer's work queue.
  Future<Paginated<Complaint>> assignedComplaints({
    int page = 1,
    int pageSize = 10,
    Map<String, dynamic> filters = const {},
  }) =>
      _list('/complaints/assigned', page, pageSize, filters);

  /// All complaints the caller may see - the admin list.
  Future<Paginated<Complaint>> allComplaints({
    int page = 1,
    int pageSize = 10,
    Map<String, dynamic> filters = const {},
  }) =>
      _list('/complaints', page, pageSize, filters);

  Future<Paginated<Complaint>> _list(
    String path,
    int page,
    int pageSize,
    Map<String, dynamic> filters,
  ) async {
    // `page` is always sent, so every list parses through the one envelope
    // (MOBILE_API.md section 5).
    final data = await _api.get(path, query: {
      'page': page,
      'pageSize': pageSize,
      ...filters,
    });
    return Paginated<Complaint>.fromJson(data, Complaint.fromJson);
  }

  Future<Complaint> byId(String complaintId) async {
    final data = await _api.get('/complaints/$complaintId');
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  /// Public tracking by reference id - the only endpoint needing no token.
  Future<Map<String, dynamic>> track(String referenceId) async {
    final data = await _api.get('/complaints/track/$referenceId');
    return (data as Map<String, dynamic>?) ?? {};
  }

  Future<ComplaintStats> statistics({String? department}) async {
    final data = await _api.get('/complaints/statistics', query: {
      if (department != null && department.isNotEmpty) 'department': department,
    });
    return ComplaintStats.fromJson((data as Map<String, dynamic>?) ?? {});
  }

  Future<List<Complaint>> escalations() async {
    final data = await _api.get('/complaints/escalations');
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map(Complaint.fromJson)
          .toList();
    }
    return Paginated<Complaint>.fromJson(data, Complaint.fromJson).items;
  }

  // ---------------------------------------------------- officer and admin

  /// Officers may only set the statuses in `OFFICER_STATUS_OPTIONS`; the UI
  /// offers exactly those, so a 403 here would mean a genuine bug.
  Future<Complaint> updateStatus(
    String complaintId,
    String status, {
    String note = '',
  }) async {
    final data = await _api.put('/complaints/$complaintId/status', body: {
      'status': status,
      if (note.isNotEmpty) 'note': note,
    });
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  Future<Complaint> addRemark(String complaintId, String message) async {
    final data = await _api
        .post('/complaints/$complaintId/remarks', body: {'message': message});
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  /// Submit a resolution, optionally with proof photos.
  Future<Complaint> resolve(
    String complaintId, {
    required String notes,
    List<File> files = const [],
  }) async {
    final fields = {'notes': notes};
    final data = files.isEmpty
        ? await _api.post('/complaints/$complaintId/resolve', body: fields)
        : await _api.multipart('/complaints/$complaintId/resolve',
            fields: fields, files: files);
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  Future<Complaint> assign(String complaintId, String officerId,
      {String reason = ''}) async {
    final data = await _api.post('/complaints/$complaintId/assign', body: {
      'officerId': officerId,
      if (reason.isNotEmpty) 'reason': reason,
    });
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  Future<Complaint> reassign(String complaintId, String officerId,
      {String reason = ''}) async {
    final data = await _api.put('/complaints/$complaintId/reassign', body: {
      'officerId': officerId,
      if (reason.isNotEmpty) 'reason': reason,
    });
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  Future<Complaint> changePriority(String complaintId, String priority) async {
    final data = await _api
        .put('/complaints/$complaintId/priority', body: {'priority': priority});
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  Future<Complaint> escalate(String complaintId, {String reason = ''}) async {
    final data = await _api.post('/complaints/$complaintId/escalate',
        body: {if (reason.isNotEmpty) 'reason': reason});
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  Future<Complaint> close(String complaintId) async {
    final data = await _api.post('/complaints/$complaintId/close');
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  // --------------------------------------------------------------- student

  Future<Complaint> reopen(String complaintId, String reason) async {
    final data = await _api
        .post('/complaints/$complaintId/reopen', body: {'reason': reason});
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  Future<Complaint> submitFeedback(
    String complaintId, {
    required int rating,
    String comment = '',
  }) async {
    final data = await _api.post('/complaints/$complaintId/feedback', body: {
      'rating': rating,
      if (comment.isNotEmpty) 'comment': comment,
      'satisfied': rating >= 3,
    });
    return Complaint.fromJson(data as Map<String, dynamic>);
  }

  // -------------------------------------------------------------------- AI

  /// Live classification for the submit form. Purely advisory: the server
  /// recomputes the analysis on submit, so a failure here must never block
  /// the user - callers swallow the error and simply show nothing.
  Future<AiAnalysis?> classify({
    required String title,
    required String description,
    required String category,
  }) async {
    final data = await _api.post('/ai/classify', body: {
      'title': title,
      'description': description,
      'category': category,
    });
    if (data is! Map<String, dynamic>) return null;
    return AiAnalysis.fromJson(data);
  }
}
