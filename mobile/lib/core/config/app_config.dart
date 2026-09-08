/// Build-time configuration.
///
/// The base URL is supplied with `--dart-define`, so one source tree builds
/// against a laptop, a LAN phone, or the deployed backend without an edit:
///
///   flutter run                                         (emulator default)
///   flutter run   --dart-define=API_BASE_URL=http://192.168.1.7:5000
///   flutter build apk --release \
///       --dart-define=API_BASE_URL=https://your-app.vercel.app
///
/// 10.0.2.2 is how the Android emulator reaches the host machine's localhost;
/// a real handset cannot resolve it, which is why it is only the *default*.
class AppConfig {
  const AppConfig._();

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:5000',
  );

  /// `/api` is the prefix every blueprint in the Flask backend registers under.
  static String get apiRoot => '$apiBaseUrl/api';

  /// Sent as `X-Client-Type`, which makes the backend return a refresh token
  /// alongside the short-lived access token (see backend/MOBILE_API.md §1).
  static const String clientType = 'mobile';

  static const Duration requestTimeout = Duration(seconds: 30);

  /// Mirrors MAX_FILE_SIZE / MAX_FILES_PER_REQUEST in backend/config.py, so the
  /// app can reject an oversized file before spending the upload.
  static const int maxFileSizeBytes = 5 * 1024 * 1024;
  static const int maxFilesPerRequest = 5;

  static const bool isProduction = bool.fromEnvironment('dart.vm.product');
}
