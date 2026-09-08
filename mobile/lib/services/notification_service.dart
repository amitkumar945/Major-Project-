import '../core/network/api_client.dart';
import '../models/notification.dart';

/// Everything under `/api/notifications` and `/api/devices`.
///
/// The in-app feed is authoritative. Device registration is additive: if the
/// server has `PUSH_ENABLED=false` the feed still works, so a failed
/// registration is never surfaced as an error to the user.
class NotificationApi {
  NotificationApi._();
  static final NotificationApi instance = NotificationApi._();

  final ApiClient _api = ApiClient.instance;

  Future<List<AppNotification>> list({int page = 1, int pageSize = 50}) async {
    final data =
        await _api.get('/notifications', query: {'page': page, 'pageSize': pageSize});

    // Sends `page`, so the paginated envelope comes back; the bare-array branch
    // is kept because the endpoint still supports it.
    final items = data is List ? data : (data as Map<String, dynamic>?)?['items'];
    if (items is! List) return const [];
    return items
        .whereType<Map<String, dynamic>>()
        .map(AppNotification.fromJson)
        .toList();
  }

  Future<int> unreadCount() async {
    final data = await _api.get('/notifications/unread-count');
    if (data is Map<String, dynamic>) {
      return (data['count'] as num?)?.toInt() ??
          (data['unread'] as num?)?.toInt() ??
          0;
    }
    return (data as num?)?.toInt() ?? 0;
  }

  Future<void> markRead(String id) => _api.put('/notifications/$id/read');
  Future<void> markUnread(String id) => _api.put('/notifications/$id/unread');
  Future<void> markAllRead() => _api.put('/notifications/read-all');
  Future<void> remove(String id) => _api.delete('/notifications/$id');

  // ------------------------------------------------------------- devices

  /// Register this handset for push. Safe on every launch: re-registering the
  /// same token updates the row instead of duplicating it.
  Future<void> registerDevice({
    required String token,
    String platform = 'android',
    String deviceName = '',
  }) async {
    await _api.post('/devices/register', body: {
      'token': token,
      'platform': platform,
      if (deviceName.isNotEmpty) 'deviceName': deviceName,
    });
  }

  /// Called on logout so the handset stops receiving this account's alerts.
  Future<void> unregisterDevice(String token) async {
    await _api.delete('/devices/register', body: {'token': token});
  }
}
