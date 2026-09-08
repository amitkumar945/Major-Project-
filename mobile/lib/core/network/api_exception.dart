/// A failed API call, carrying enough detail for the UI to be specific.
///
/// The backend's error envelope is
/// `{ "success": false, "message": "…", "error": { "fields": { … } } }`,
/// so [fieldErrors] can be mapped straight onto form inputs.
class ApiException implements Exception {
  ApiException(
    this.message, {
    this.statusCode = 0,
    this.fieldErrors = const {},
    this.isNetworkError = false,
  });

  final String message;
  final int statusCode;
  final Map<String, String> fieldErrors;
  final bool isNetworkError;

  factory ApiException.network([String? detail]) => ApiException(
        detail ??
            'Cannot reach the server. Check your internet connection and try again.',
        isNetworkError: true,
      );

  factory ApiException.timeout() => ApiException(
        'The server took too long to respond. Please try again.',
        isNetworkError: true,
      );

  /// 401 after a refresh attempt already failed: the session is genuinely gone.
  bool get isUnauthorized => statusCode == 401;
  bool get isForbidden => statusCode == 403;
  bool get isNotFound => statusCode == 404;
  bool get isValidation => statusCode == 422 || fieldErrors.isNotEmpty;

  @override
  String toString() => message;
}
