import '../core/network/api_client.dart';
import '../models/complaint.dart';
import '../models/stats.dart';
import '../models/user.dart';

/// Admin-side reads and writes: users, officers, departments, analytics.
///
/// Every route here is already role-gated on the server (`@role_required`), so
/// a student who somehow reached these screens would get a 403 rather than
/// data - the app hides them, the backend enforces it.
class AdminService {
  AdminService._();
  static final AdminService instance = AdminService._();

  final ApiClient _api = ApiClient.instance;

  // ----------------------------------------------------------------- users

  Future<List<AppUser>> users({
    String search = '',
    String role = '',
    int page = 1,
    int pageSize = 50,
  }) async {
    final data = await _api.get('/users', query: {
      'page': page,
      'pageSize': pageSize,
      if (search.isNotEmpty) 'search': search,
      if (role.isNotEmpty) 'role': role,
    });
    return _parseList(data, AppUser.fromJson);
  }

  Future<Map<String, dynamic>> userSummary() async {
    final data = await _api.get('/users/summary');
    return (data as Map<String, dynamic>?) ?? {};
  }

  /// Flip an account between active and inactive.
  ///
  /// The endpoint is a TOGGLE: it reads the stored value and inverts it, and
  /// ignores the request body entirely. So there is no target state to send -
  /// the caller must be sure of the current one, which is why the screens
  /// re-fetch the list afterwards rather than assuming a result.
  ///
  /// The server refuses to let an admin deactivate their own account (409).
  Future<void> toggleUserActive(String userId) async {
    await _api.put('/users/$userId/status');
  }

  // -------------------------------------------------------------- officers

  Future<List<Officer>> officers({
    String department = '',
    String search = '',
    bool activeOnly = false,
    int page = 1,
    int pageSize = 50,
  }) async {
    final data = await _api.get('/officers', query: {
      'page': page,
      'pageSize': pageSize,
      if (department.isNotEmpty) 'department': department,
      if (search.isNotEmpty) 'search': search,
      if (activeOnly) 'activeOnly': true,
    });
    return _parseList(data, Officer.fromJson);
  }

  Future<Officer> createOfficer(Map<String, dynamic> values) async {
    final data = await _api.post('/officers', body: values);
    return Officer.fromJson(data as Map<String, dynamic>);
  }

  Future<Officer> updateOfficer(
      String officerId, Map<String, dynamic> changes) async {
    final data = await _api.put('/officers/$officerId', body: changes);
    return Officer.fromJson(data as Map<String, dynamic>);
  }

  /// Flip an officer between active and inactive. Also a toggle, and the
  /// server refuses deactivation while the officer still has open work (409),
  /// so the failure message is worth showing verbatim.
  Future<void> toggleOfficerActive(String officerId) async {
    await _api.put('/officers/$officerId/status');
  }

  /// The least-loaded active officer in a department, used to pre-select the
  /// assignee in the assign dialog.
  Future<Officer?> suggestOfficer(String department) async {
    try {
      final data = await _api.get('/officers/suggest',
          query: {'department': department});
      if (data is Map<String, dynamic> && data['id'] != null) {
        return Officer.fromJson(data);
      }
    } catch (_) {
      // No active officer in that department: the admin picks manually.
    }
    return null;
  }

  // ----------------------------------------------------------- departments

  Future<List<Department>> departments() async {
    final data = await _api.get('/departments', query: {'page': 1, 'pageSize': 50});
    return _parseList(data, Department.fromJson);
  }

  /// Flip a department between active and inactive. Toggle, as above.
  Future<void> toggleDepartmentActive(String code) async {
    await _api.put('/departments/$code/status');
  }

  Future<Department> updateDepartment(
      String code, Map<String, dynamic> changes) async {
    final data = await _api.put('/departments/$code', body: changes);
    return Department.fromJson(data as Map<String, dynamic>);
  }

  // ------------------------------------------------------------- dashboard

  Future<Map<String, dynamic>> dashboard() async {
    final data = await _api.get('/admin/dashboard');
    return (data as Map<String, dynamic>?) ?? {};
  }

  /// Escalated complaints awaiting an admin decision.
  Future<List<Complaint>> escalations() async {
    final data = await _api.get('/complaints/escalations');
    return _parseList(data, Complaint.fromJson);
  }

  // ------------------------------------------------------------- analytics

  Future<Map<String, dynamic>> analyticsSummary() async {
    final data = await _api.get('/analytics/summary');
    return (data as Map<String, dynamic>?) ?? {};
  }

  Future<Map<String, dynamic>> analyticsOverview() async {
    final data = await _api.get('/analytics/overview');
    return (data as Map<String, dynamic>?) ?? {};
  }

  /// Complaint counts per department, as `[{name, value}]`.
  ///
  /// The endpoint wraps three series in one object, so the distribution is
  /// pulled out here rather than in the screen.
  Future<List<ChartPoint>> analyticsDepartments() async {
    final data = await _api.get('/analytics/departments');
    final raw = data is Map ? data['distribution'] : data;
    return ChartPoint.listFrom(raw);
  }

  Future<List<ChartPoint>> analyticsStatus() async {
    final data = await _api.get('/analytics/status');
    return ChartPoint.listFrom(data);
  }

  Future<List<ChartPoint>> analyticsPriority() async {
    final data = await _api.get('/analytics/priority');
    return ChartPoint.listFrom(data);
  }

  /// Registered vs resolved per month, from the `monthly` series.
  Future<List<TrendPoint>> analyticsTrend() async {
    final data = await _api.get('/analytics/trend');
    final raw = data is Map ? data['monthly'] : data;
    if (raw is! List) return const [];
    return raw
        .whereType<Map<String, dynamic>>()
        .map(TrendPoint.fromJson)
        .toList();
  }

  Future<Map<String, dynamic>> analyticsSla() async {
    final data = await _api.get('/analytics/sla');
    return (data as Map<String, dynamic>?) ?? {};
  }

  // -------------------------------------------------------------- settings

  /// Non-secret configuration for the settings screen. The server explicitly
  /// withholds MONGO_URI and JWT_SECRET_KEY, so nothing sensitive is exposed.
  Future<Map<String, dynamic>> settings() async {
    final data = await _api.get('/admin/settings');
    return (data as Map<String, dynamic>?) ?? {};
  }

  /// Run the SLA sweep on demand: escalate breaches, warn on due-soon.
  Future<Map<String, dynamic>> runSlaCheck() async {
    final data = await _api.post('/admin/sla-check');
    return (data as Map<String, dynamic>?) ?? {};
  }

  Future<Map<String, dynamic>> slaReport() async {
    final data = await _api.get('/admin/sla');
    return (data as Map<String, dynamic>?) ?? {};
  }

  // --------------------------------------------------------------- helpers

  /// Handles both the bare array and the paginated envelope.
  List<T> _parseList<T>(dynamic data, T Function(Map<String, dynamic>) parse) {
    final raw = data is List ? data : (data is Map ? data['items'] : null);
    if (raw is! List) return const [];
    return raw.whereType<Map<String, dynamic>>().map(parse).toList();
  }

}
