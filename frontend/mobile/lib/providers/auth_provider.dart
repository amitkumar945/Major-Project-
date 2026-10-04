import 'package:flutter/foundation.dart';

import '../core/network/api_client.dart';
import '../core/network/api_exception.dart';
import '../core/storage/secure_store.dart';
import '../models/user.dart';
import '../services/auth_service.dart';
import '../services/push_service.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

/// Session state for the whole app. The router listens to this, so a sign-in,
/// a sign-out, or an unrecoverable 401 all move the user automatically.
class AuthProvider extends ChangeNotifier {
  AuthProvider() {
    // The API client cannot import this class without a cycle, so it calls
    // back here when a refresh fails and the session is genuinely over.
    ApiClient.instance.onSessionExpired = _forceSignOut;
  }

  final AuthService _auth = AuthService.instance;

  AuthStatus _status = AuthStatus.unknown;
  AppUser? _user;
  bool _busy = false;

  AuthStatus get status => _status;
  AppUser? get user => _user;
  bool get busy => _busy;
  bool get isSignedIn => _status == AuthStatus.authenticated && _user != null;

  /// Decide where the app should start, without blocking on the network.
  ///
  /// A cached user paints the right shell immediately; `/auth/me` then confirms
  /// the token in the background. If the device is offline the cached session
  /// is kept rather than kicking the user out to login for no reason.
  Future<void> restoreSession() async {
    final cached = await SecureStore.instance.readUser();
    final token = await SecureStore.instance.readAccessToken();

    if (token == null || token.isEmpty) {
      _set(AuthStatus.unauthenticated, null);
      return;
    }

    if (cached != null) {
      _user = AppUser.fromJson(cached);
      _set(AuthStatus.authenticated, _user);
    }

    try {
      final fresh = await _auth.me();
      _set(AuthStatus.authenticated, fresh);
      await PushService.instance.registerAfterLogin();
    } on ApiException catch (e) {
      if (e.isNetworkError && cached != null) {
        return; // offline with a cached session: stay signed in
      }
      await _clearLocal();
    } catch (_) {
      if (cached == null) await _clearLocal();
    }
  }

  Future<AppUser> signIn({
    required String identifier,
    required String password,
  }) async {
    _setBusy(true);
    try {
      final user = await _auth.login(identifier: identifier, password: password);
      _set(AuthStatus.authenticated, user);
      await PushService.instance.registerAfterLogin();
      return user;
    } finally {
      _setBusy(false);
    }
  }

  Future<AppUser> register(Map<String, dynamic> values) async {
    _setBusy(true);
    try {
      final user = await _auth.register(values);
      _set(AuthStatus.authenticated, user);
      await PushService.instance.registerAfterLogin();
      return user;
    } finally {
      _setBusy(false);
    }
  }

  /// Adopt a session created by a verified login OTP.
  void adoptSession(AppUser user) {
    _set(AuthStatus.authenticated, user);
    PushService.instance.registerAfterLogin();
  }

  Future<void> signOut() async {
    _setBusy(true);
    try {
      // Detach the handset first, while the token is still valid.
      await PushService.instance.unregister();
      await _auth.logout();
    } finally {
      _user = null;
      _status = AuthStatus.unauthenticated;
      _setBusy(false);
      notifyListeners();
    }
  }

  Future<void> refreshProfile() async {
    try {
      final fresh = await _auth.me();
      _set(AuthStatus.authenticated, fresh);
    } catch (_) {
      // A failed refresh leaves the existing profile in place.
    }
  }

  Future<AppUser> updateProfile(Map<String, dynamic> changes) async {
    final updated = await _auth.updateProfile(changes);
    _set(AuthStatus.authenticated, updated);
    return updated;
  }

  /// Called by the API client when a refresh could not save the session.
  void _forceSignOut() {
    if (_status == AuthStatus.unauthenticated) return;
    _clearLocal();
  }

  Future<void> _clearLocal() async {
    await SecureStore.instance.clear();
    _user = null;
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }

  void _set(AuthStatus status, AppUser? user) {
    _status = status;
    _user = user;
    notifyListeners();
  }

  void _setBusy(bool value) {
    _busy = value;
    notifyListeners();
  }
}
