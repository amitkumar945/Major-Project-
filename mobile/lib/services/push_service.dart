import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'notification_service.dart';

/// Firebase Cloud Messaging, wired to the backend's existing device registry.
///
/// Deliberately fail-soft. The backend ships with `PUSH_ENABLED=false` and
/// Firebase needs a `google-services.json` that is not in the repository, so
/// this whole subsystem is optional: every entry point catches its own errors
/// and leaves the app fully usable, because the in-app notification feed is
/// the source of truth either way.
class PushService {
  PushService._();
  static final PushService instance = PushService._();

  final FlutterLocalNotificationsPlugin _local =
      FlutterLocalNotificationsPlugin();

  bool _available = false;
  String? _token;

  /// The FCM token, or null when push is not configured on this build.
  String? get token => _token;
  bool get isAvailable => _available;

  /// Emits the complaint id when a notification is tapped, so the router can
  /// open that complaint. Broadcast: several listeners may come and go.
  final StreamController<String> _tapped = StreamController<String>.broadcast();
  Stream<String> get onNotificationTap => _tapped.stream;

  /// Called once at startup. Never throws.
  Future<void> initialise() async {
    try {
      await Firebase.initializeApp();
    } catch (e) {
      // No google-services.json, or Firebase not set up for this project.
      debugPrint('Push disabled: Firebase could not start ($e)');
      _available = false;
      return;
    }

    try {
      await _setupLocalNotifications();

      final messaging = FirebaseMessaging.instance;

      // Android 13+ requires an explicit runtime prompt for notifications.
      await messaging.requestPermission(alert: true, badge: true, sound: true);

      _token = await messaging.getToken();
      _available = _token != null;

      // A rotated token must reach the backend, or pushes stop silently.
      messaging.onTokenRefresh.listen((fresh) async {
        _token = fresh;
        await _registerWithBackend();
      });

      FirebaseMessaging.onMessage.listen(_showForeground);
      FirebaseMessaging.onMessageOpenedApp.listen(_handleTap);

      // Cold start from a notification.
      final initial = await messaging.getInitialMessage();
      if (initial != null) _handleTap(initial);
    } catch (e) {
      debugPrint('Push setup failed, continuing without it: $e');
      _available = false;
    }
  }

  Future<void> _setupLocalNotifications() async {
    const settings = InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
    );
    await _local.initialize(
      settings,
      onDidReceiveNotificationResponse: (response) {
        final payload = response.payload;
        if (payload != null && payload.isNotEmpty) _tapped.add(payload);
      },
    );
  }

  /// FCM does not draw a banner while the app is in the foreground, so a local
  /// notification stands in for it.
  Future<void> _showForeground(RemoteMessage message) async {
    final notification = message.notification;
    if (notification == null) return;

    const details = NotificationDetails(
      android: AndroidNotificationDetails(
        'grievance_updates',
        'Complaint updates',
        channelDescription: 'Status changes and replies on your complaints',
        importance: Importance.high,
        priority: Priority.high,
      ),
    );

    await _local.show(
      notification.hashCode,
      notification.title ?? 'Grievance update',
      notification.body ?? '',
      details,
      payload: '${message.data['complaintId'] ?? ''}',
    );
  }

  void _handleTap(RemoteMessage message) {
    final complaintId = '${message.data['complaintId'] ?? ''}';
    if (complaintId.isNotEmpty) _tapped.add(complaintId);
  }

  /// Register this handset against the signed-in account. Called after login,
  /// and safe to repeat: the backend updates the existing row.
  Future<void> registerAfterLogin() async {
    if (!_available) return;
    await _registerWithBackend();
  }

  Future<void> _registerWithBackend() async {
    final value = _token;
    if (value == null) return;
    try {
      await NotificationApi.instance.registerDevice(
        token: value,
        platform: 'android',
        deviceName: 'Android device',
      );
    } catch (e) {
      // Push is an enhancement; a failed registration must not break login.
      debugPrint('Device registration skipped: $e');
    }
  }

  /// Detach this handset on logout, so the next account does not inherit
  /// the previous user's alerts.
  Future<void> unregister() async {
    final value = _token;
    if (value == null) return;
    try {
      await NotificationApi.instance.unregisterDevice(value);
    } catch (e) {
      debugPrint('Device unregistration skipped: $e');
    }
  }

  void dispose() => _tapped.close();
}
