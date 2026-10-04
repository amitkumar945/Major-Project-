import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import '../config/app_config.dart';
import '../storage/secure_store.dart';
import 'api_exception.dart';

/// The single HTTP entry point for the app.
///
/// Responsibilities, all of which the screens are then free to ignore:
///  * attach `Authorization: Bearer ...` and `X-Client-Type: mobile`
///  * unwrap the `{ success, message, data }` envelope
///  * turn failures into a typed [ApiException] with per-field errors
///  * refresh a 401 exactly once and replay the original request
///
/// The refresh is guarded by a single [Completer]. MOBILE_API.md section 2
/// warns that concurrent refreshes trip the reuse detection and revoke every
/// session for the user, so parallel 401s must queue behind one call rather
/// than each firing their own.
class ApiClient {
  ApiClient._();
  static final ApiClient instance = ApiClient._();

  final http.Client _http = http.Client();
  final SecureStore _store = SecureStore.instance;

  Completer<bool>? _refreshInFlight;

  /// Invoked when the session cannot be recovered, so the app can route to
  /// login. Set by AuthProvider; a callback avoids a circular import.
  void Function()? onSessionExpired;

  // ------------------------------------------------------------- verbs

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) =>
      _send('GET', path, query: query);

  Future<dynamic> post(String path, {Object? body, bool authenticated = true}) =>
      _send('POST', path, body: body, authenticated: authenticated);

  Future<dynamic> put(String path, {Object? body}) =>
      _send('PUT', path, body: body);

  Future<dynamic> delete(String path, {Object? body}) =>
      _send('DELETE', path, body: body);

  // ------------------------------------------------------- core request

  Future<dynamic> _send(
    String method,
    String path, {
    Object? body,
    Map<String, dynamic>? query,
    bool authenticated = true,
    bool isRetry = false,
  }) async {
    final uri = _uri(path, query);

    // Refresh proactively once the stored expiry has passed, so the common
    // case costs one request instead of a guaranteed 401 plus a replay.
    if (authenticated && !isRetry && await _store.isAccessTokenExpired()) {
      await _refreshSession();
    }

    http.Response response;
    try {
      final headers = await _headers(authenticated: authenticated);
      final encoded = body == null ? null : jsonEncode(body);

      final request = http.Request(method, uri)..headers.addAll(headers);
      if (encoded != null) request.body = encoded;

      final streamed =
          await _http.send(request).timeout(AppConfig.requestTimeout);
      response = await http.Response.fromStream(streamed);
    } on SocketException {
      throw ApiException.network();
    } on HandshakeException {
      throw ApiException.network('Secure connection to the server failed.');
    } on TimeoutException {
      throw ApiException.timeout();
    } on http.ClientException catch (e) {
      throw ApiException.network(e.message);
    }

    // One refresh, one replay. `isRetry` stops an infinite 401 loop.
    if (response.statusCode == 401 && authenticated && !isRetry) {
      final refreshed = await _refreshSession();
      if (refreshed) {
        return _send(method, path,
            body: body,
            query: query,
            authenticated: authenticated,
            isRetry: true);
      }
      onSessionExpired?.call();
    }

    return _decode(response);
  }

  // ------------------------------------------------------------ upload

  /// Multipart submit, used by complaint creation and officer resolutions.
  ///
  /// Map and list values are JSON-encoded, because `complaint_routes._payload()`
  /// decodes exactly the `location` and `ai` keys back into dictionaries.
  Future<dynamic> multipart(
    String path, {
    required Map<String, dynamic> fields,
    List<File> files = const [],
    String fileField = 'files',
    String method = 'POST',
    bool isRetry = false,
  }) async {
    final uri = _uri(path, null);

    http.Response response;
    try {
      final request = http.MultipartRequest(method, uri)
        ..headers.addAll(await _headers(json: false));

      fields.forEach((key, value) {
        if (value == null) return;
        request.fields[key] =
            value is Map || value is List ? jsonEncode(value) : value.toString();
      });

      for (final file in files) {
        request.files.add(await http.MultipartFile.fromPath(
          fileField,
          file.path,
          contentType: _contentTypeFor(file.path),
        ));
      }

      final streamed = await request.send().timeout(AppConfig.requestTimeout);
      response = await http.Response.fromStream(streamed);
    } on SocketException {
      throw ApiException.network();
    } on TimeoutException {
      throw ApiException.timeout();
    } on http.ClientException catch (e) {
      throw ApiException.network(e.message);
    }

    if (response.statusCode == 401 && !isRetry) {
      if (await _refreshSession()) {
        return multipart(path,
            fields: fields,
            files: files,
            fileField: fileField,
            method: method,
            isRetry: true);
      }
      onSessionExpired?.call();
    }

    return _decode(response);
  }

  MediaType? _contentTypeFor(String path) {
    final ext = path.split('.').last.toLowerCase();
    switch (ext) {
      case 'png':
        return MediaType('image', 'png');
      case 'jpg':
      case 'jpeg':
        return MediaType('image', 'jpeg');
      case 'webp':
        return MediaType('image', 'webp');
      case 'pdf':
        return MediaType('application', 'pdf');
      default:
        return null; // let the server sniff it; it validates magic numbers
    }
  }

  // ----------------------------------------------------------- refresh

  /// Exchange the refresh token, serialised behind one completer.
  Future<bool> _refreshSession() {
    final existing = _refreshInFlight;
    if (existing != null) return existing.future; // join the in-flight call

    final completer = Completer<bool>();
    _refreshInFlight = completer;

    _performRefresh().then((ok) {
      _refreshInFlight = null;
      completer.complete(ok);
    }).catchError((_) {
      _refreshInFlight = null;
      completer.complete(false);
    });

    return completer.future;
  }

  Future<bool> _performRefresh() async {
    final refreshToken = await _store.readRefreshToken();
    if (refreshToken == null || refreshToken.isEmpty) return false;

    try {
      final response = await _http
          .post(
            _uri('/auth/refresh', null),
            headers: {
              'Content-Type': 'application/json',
              'X-Client-Type': AppConfig.clientType,
            },
            body: jsonEncode({'refreshToken': refreshToken}),
          )
          .timeout(AppConfig.requestTimeout);

      if (response.statusCode != 200) return false;

      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      final data = decoded['data'] as Map<String, dynamic>?;
      if (data == null || data['token'] == null) return false;

      // The refresh token is rotated on every success; storing the new one is
      // mandatory, or the next refresh replays a consumed token and the server
      // revokes every session for this user.
      await _store.saveTokens(
        accessToken: data['token'] as String,
        refreshToken: data['refreshToken'] as String?,
        expiresInSeconds: (data['expiresIn'] as num?)?.toInt(),
      );
      if (data['user'] is Map<String, dynamic>) {
        await _store.saveUser(data['user'] as Map<String, dynamic>);
      }
      return true;
    } catch (_) {
      return false; // offline: keep the tokens, the user may retry later
    }
  }

  // ------------------------------------------------------------ helpers

  Uri _uri(String path, Map<String, dynamic>? query) {
    final normalised = path.startsWith('/') ? path : '/$path';
    final uri = Uri.parse('${AppConfig.apiRoot}$normalised');
    if (query == null || query.isEmpty) return uri;

    final params = <String, String>{};
    query.forEach((key, value) {
      if (value == null) return;
      final text = value.toString();
      if (text.isEmpty) return; // empty filters are simply not sent
      params[key] = text;
    });
    return uri.replace(queryParameters: {...uri.queryParameters, ...params});
  }

  Future<Map<String, String>> _headers({
    bool authenticated = true,
    bool json = true,
  }) async {
    final headers = <String, String>{
      'Accept': 'application/json',
      'X-Client-Type': AppConfig.clientType,
    };
    if (json) headers['Content-Type'] = 'application/json';

    if (authenticated) {
      final token = await _store.readAccessToken();
      if (token != null && token.isNotEmpty) {
        headers['Authorization'] = 'Bearer $token';
      }
    }
    return headers;
  }

  /// Unwrap the envelope, or raise a typed error.
  dynamic _decode(http.Response response) {
    Map<String, dynamic>? decoded;
    if (response.body.isNotEmpty) {
      try {
        final parsed = jsonDecode(response.body);
        if (parsed is Map<String, dynamic>) {
          decoded = parsed;
        } else if (parsed is List) {
          // Bare arrays: officers, departments, notifications, users, feedback
          // return one when no `page` is sent (MOBILE_API.md section 5).
          if (response.statusCode >= 200 && response.statusCode < 300) {
            return parsed;
          }
        }
      } catch (_) {
        // A non-JSON body means a proxy or HTML error page, not an API answer.
        if (response.statusCode >= 400) {
          throw ApiException(
            'The server returned an unexpected response (${response.statusCode}).',
            statusCode: response.statusCode,
          );
        }
      }
    }

    final ok = response.statusCode >= 200 && response.statusCode < 300;
    if (ok && decoded == null) return null;

    if (ok && decoded!['success'] != false) {
      return decoded.containsKey('data') ? decoded['data'] : decoded;
    }

    throw ApiException(
      (decoded?['message'] as String?)?.trim().isNotEmpty == true
          ? decoded!['message'] as String
          : _fallbackMessage(response.statusCode),
      statusCode: response.statusCode,
      fieldErrors: _fields(decoded),
    );
  }

  Map<String, String> _fields(Map<String, dynamic>? decoded) {
    final error = decoded?['error'];
    if (error is! Map) return const {};
    final fields = error['fields'];
    if (fields is! Map) return const {};
    return fields.map((key, value) => MapEntry('$key', '$value'));
  }

  String _fallbackMessage(int status) {
    switch (status) {
      case 400:
        return 'That request could not be processed.';
      case 401:
        return 'Your session has expired. Please sign in again.';
      case 403:
        return 'You do not have permission to do that.';
      case 404:
        return 'We could not find what you were looking for.';
      case 409:
        return 'That conflicts with something that already exists.';
      case 422:
        return 'Please check the highlighted fields.';
      case 429:
        return 'Too many attempts. Please wait a moment and try again.';
      case 500:
      case 502:
      case 503:
        return 'The server ran into a problem. Please try again shortly.';
      default:
        return 'Something went wrong (error $status).';
    }
  }
}
