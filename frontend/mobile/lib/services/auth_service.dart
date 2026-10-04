import '../core/config/app_config.dart';
import '../core/network/api_client.dart';
import '../core/storage/secure_store.dart';
import '../models/user.dart';

/// Everything under `/api/auth`.
///
/// `client: "mobile"` is sent on login and register, which is what makes the
/// backend add `refreshToken` / `expiresIn` to the session payload
/// (backend/MOBILE_API.md section 1). The API client also sends the
/// `X-Client-Type` header, so either signal alone would do; both are harmless.
class AuthService {
  AuthService._();
  static final AuthService instance = AuthService._();

  final ApiClient _api = ApiClient.instance;
  final SecureStore _store = SecureStore.instance;

  /// OTP purposes the backend recognises (`otp_service.PURPOSE_*`).
  static const String purposeVerify = 'verify';
  static const String purposeRegister = 'register';
  static const String purposeLogin = 'login';
  static const String purposeReset = 'reset';

  // --------------------------------------------------------------- session

  Future<AppUser> login({
    required String identifier,
    required String password,
    String role = '',
  }) async {
    final data = await _api.post(
      '/auth/login',
      authenticated: false,
      body: {
        'identifier': identifier.trim(),
        'password': password,
        if (role.isNotEmpty) 'role': role,
        'client': AppConfig.clientType,
      },
    ) as Map<String, dynamic>;

    return _persistSession(data);
  }

  Future<AppUser> register(Map<String, dynamic> values) async {
    final data = await _api.post(
      '/auth/register',
      authenticated: false,
      body: {...values, 'client': AppConfig.clientType},
    ) as Map<String, dynamic>;

    return _persistSession(data);
  }

  /// Store tokens + user from a login/register/verify-otp payload.
  Future<AppUser> _persistSession(Map<String, dynamic> data) async {
    final user = AppUser.fromJson(data['user'] as Map<String, dynamic>);

    await _store.saveTokens(
      accessToken: '${data['token']}',
      refreshToken: data['refreshToken'] as String?,
      expiresInSeconds: (data['expiresIn'] as num?)?.toInt(),
    );
    await _store.saveUser(user.toJson());
    return user;
  }

  /// Confirms the stored access token still works and re-hydrates the profile.
  Future<AppUser> me() async {
    final data = await _api.get('/auth/me') as Map<String, dynamic>;
    final user = AppUser.fromJson(data);
    await _store.saveUser(user.toJson());
    return user;
  }

  /// Revoke this device's session, then clear local state.
  ///
  /// The network call is best-effort: if it fails the tokens are still wiped,
  /// because a user who taps Logout must end up signed out either way.
  Future<void> logout({bool allDevices = false}) async {
    try {
      final refreshToken = await _store.readRefreshToken();
      await _api.post('/auth/logout', body: {
        if (allDevices) 'allDevices': true,
        if (!allDevices && refreshToken != null) 'refreshToken': refreshToken,
      });
    } catch (_) {
      // Offline or already-expired session: local sign-out still proceeds.
    }
    await _store.clear();
  }

  // ------------------------------------------------------------------- OTP

  /// Request a code. `purpose` decides which pre-check the server applies:
  /// `register` requires the address to be free, `reset` requires it to exist.
  Future<Map<String, dynamic>> sendOtp({
    required String email,
    String purpose = purposeVerify,
  }) async {
    final data = await _api.post(
      '/auth/send-otp',
      authenticated: false,
      body: {'email': email.trim(), 'purpose': purpose},
    );
    return (data as Map<String, dynamic>?) ?? {};
  }

  Future<Map<String, dynamic>> resendOtp({
    required String email,
    String purpose = purposeVerify,
  }) async {
    final data = await _api.post(
      '/auth/resend-otp',
      authenticated: false,
      body: {'email': email.trim(), 'purpose': purpose},
    );
    return (data as Map<String, dynamic>?) ?? {};
  }

  /// Verify a code. For `purpose: login` the response also carries a full
  /// session, which is persisted here so the caller is signed in immediately.
  Future<({bool verified, AppUser? user})> verifyOtp({
    required String email,
    required String otp,
    String purpose = purposeVerify,
  }) async {
    final data = await _api.post(
      '/auth/verify-otp',
      authenticated: false,
      body: {'email': email.trim(), 'otp': otp.trim(), 'purpose': purpose},
    ) as Map<String, dynamic>;

    AppUser? user;
    if (data['user'] is Map<String, dynamic> && data['token'] != null) {
      user = await _persistSession(data);
    }
    return (verified: data['verified'] == true, user: user);
  }

  // -------------------------------------------------------- password reset

  /// Start a reset. Always reports success, so it cannot be used to discover
  /// which addresses are registered.
  Future<Map<String, dynamic>> forgotPassword(String email) async {
    final data = await _api.post(
      '/auth/forgot-password',
      authenticated: false,
      body: {'email': email.trim()},
    );
    return (data as Map<String, dynamic>?) ?? {};
  }

  Future<void> resetPassword({
    required String email,
    required String otp,
    required String newPassword,
  }) async {
    await _api.post('/auth/reset-password', authenticated: false, body: {
      'email': email.trim(),
      'otp': otp.trim(),
      'newPassword': newPassword,
    });
  }

  // --------------------------------------------------------------- profile

  Future<AppUser> updateProfile(Map<String, dynamic> changes) async {
    final data = await _api.put('/auth/profile', body: changes)
        as Map<String, dynamic>;
    final user = AppUser.fromJson(data);
    await _store.saveUser(user.toJson());
    return user;
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    await _api.put('/auth/password', body: {
      'currentPassword': currentPassword,
      'newPassword': newPassword,
    });
  }
}
