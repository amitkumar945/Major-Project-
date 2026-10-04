import 'package:flutter/foundation.dart';

import '../core/network/api_exception.dart';
import '../models/notification.dart';
import '../services/notification_service.dart';

/// The notification feed and its unread badge.
///
/// Held app-wide (one instance above the router) so the bottom-navigation
/// badge and the notifications screen never disagree.
class NotificationProvider extends ChangeNotifier {
  final NotificationApi _api = NotificationApi.instance;

  List<AppNotification> _items = [];
  int _unread = 0;
  bool _loading = false;
  String? _error;

  List<AppNotification> get items => List.unmodifiable(_items);
  int get unreadCount => _unread;
  bool get isLoading => _loading;
  String? get error => _error;
  bool get isEmpty => !_loading && _error == null && _items.isEmpty;

  Future<void> load() async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      _items = await _api.list();
      _unread = _items.where((n) => !n.read).length;
    } on ApiException catch (e) {
      _error = e.message;
    } catch (_) {
      _error = 'Could not load your notifications.';
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  /// Cheap badge poll, used on launch and when the app resumes.
  Future<void> refreshBadge() async {
    try {
      _unread = await _api.unreadCount();
      notifyListeners();
    } catch (_) {
      // A stale badge is not worth an error state.
    }
  }

  /// Mark one as read, updating the UI first and reverting if the call fails.
  Future<void> markRead(String id) async {
    final index = _items.indexWhere((n) => n.id == id);
    if (index == -1 || _items[index].read) return;

    final previous = _items[index];
    _items[index] = previous.copyWith(read: true);
    _unread = (_unread - 1).clamp(0, 9999);
    notifyListeners();

    try {
      await _api.markRead(id);
    } catch (_) {
      _items[index] = previous;
      _unread += 1;
      notifyListeners();
    }
  }

  Future<void> markAllRead() async {
    if (_items.every((n) => n.read)) return;

    final previous = List<AppNotification>.from(_items);
    final previousUnread = _unread;
    _items = _items.map((n) => n.copyWith(read: true)).toList();
    _unread = 0;
    notifyListeners();

    try {
      await _api.markAllRead();
    } catch (_) {
      _items = previous;
      _unread = previousUnread;
      notifyListeners();
    }
  }

  Future<void> remove(String id) async {
    final index = _items.indexWhere((n) => n.id == id);
    if (index == -1) return;

    final removed = _items.removeAt(index);
    if (!removed.read) _unread = (_unread - 1).clamp(0, 9999);
    notifyListeners();

    try {
      await _api.remove(id);
    } catch (_) {
      _items.insert(index, removed);
      if (!removed.read) _unread += 1;
      notifyListeners();
    }
  }

  /// Clear everything on sign-out, so the next account starts clean.
  void reset() {
    _items = [];
    _unread = 0;
    _error = null;
    notifyListeners();
  }
}
