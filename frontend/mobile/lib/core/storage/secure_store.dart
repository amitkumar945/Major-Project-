import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Token and session persistence.
///
/// MOBILE_API.md is explicit that the refresh token goes in secure storage and
/// "never in prefs", so both tokens live in the Keystore-backed store. Only the
/// non-sensitive cached user profile uses SharedPreferences, purely so the app
/// can paint the right shell before the network answers.
class SecureStore {
  SecureStore._();
  static final SecureStore instance = SecureStore._();

  static const _accessTokenKey = 'access_token';
  static const _refreshTokenKey = 'refresh_token';
  static const _expiresAtKey = 'access_expires_at';
  static const _userKey = 'cached_user';

  final FlutterSecureStorage _secure = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  Future<void> saveTokens({
    required String accessToken,
    String? refreshToken,
    int? expiresInSeconds,
  }) async {
    await _secure.write(key: _accessTokenKey, value: accessToken);

    // The server rotates the refresh token on every refresh; a null here means
    // "unchanged", so the stored one must survive rather than be wiped.
    if (refreshToken != null && refreshToken.isNotEmpty) {
      await _secure.write(key: _refreshTokenKey, value: refreshToken);
    }

    if (expiresInSeconds != null && expiresInSeconds > 0) {
      // Refresh 60s early so a request in flight cannot straddle the expiry.
      final expiry = DateTime.now()
          .add(Duration(seconds: expiresInSeconds - 60))
          .millisecondsSinceEpoch;
      await _secure.write(key: _expiresAtKey, value: expiry.toString());
    }
  }

  Future<String?> readAccessToken() => _secure.read(key: _accessTokenKey);
  Future<String?> readRefreshToken() => _secure.read(key: _refreshTokenKey);

  Future<bool> isAccessTokenExpired() async {
    final raw = await _secure.read(key: _expiresAtKey);
    if (raw == null) return false; // unknown expiry: let the 401 path decide
    final millis = int.tryParse(raw);
    if (millis == null) return false;
    return DateTime.now().millisecondsSinceEpoch >= millis;
  }

  Future<void> saveUser(Map<String, dynamic> user) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_userKey, jsonEncode(user));
  }

  Future<Map<String, dynamic>?> readUser() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_userKey);
    if (raw == null) return null;
    try {
      return jsonDecode(raw) as Map<String, dynamic>;
    } catch (_) {
      return null; // corrupted cache is not worth crashing a launch over
    }
  }

  Future<void> clear() async {
    await _secure.delete(key: _accessTokenKey);
    await _secure.delete(key: _refreshTokenKey);
    await _secure.delete(key: _expiresAtKey);
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_userKey);
  }
}
