import 'dart:async';

import 'package:dio/dio.dart';

/// Error with a human readable message (never contains tokens).
class ApiException implements Exception {
  ApiException(this.message, {this.status, this.offline = false});
  final String message;
  final int? status;
  final bool offline;
  @override
  String toString() => message;
}

/// Thin dio wrapper: in-memory access token, CSRF header, and a single
/// shared refresh when a call returns 401 (then one retry, then [onExpired]).
class ApiClient {
  ApiClient({required String baseUrl, Dio? dio, this.onExpired}) : dio = dio ?? Dio() {
    this.dio.options
      ..baseUrl = baseUrl
      ..connectTimeout = const Duration(seconds: 15)
      ..receiveTimeout = const Duration(seconds: 60)
      ..headers['X-Requested-With'] = 'saige' // CSRF header the backend requires
      ..validateStatus = (s) => s != null && s < 400;
  }

  final Dio dio;
  void Function()? onExpired;
  String? _token;
  Future<bool>? _refreshing;

  String? get token => _token;
  bool get hasToken => _token != null;
  set baseUrl(String v) => dio.options.baseUrl = v;
  void setToken(String? t) => _token = t;

  /// Rotates the session via the HttpOnly refresh cookie. Concurrent callers share one request.
  Future<bool> refresh() => _refreshing ??= _doRefresh().whenComplete(() => _refreshing = null);

  Future<bool> _doRefresh() async {
    try {
      final r = await dio.post<dynamic>('/auth/refresh');
      final d = r.data;
      final t = d is Map ? d['access_token'] : null;
      if (t is String && t.isNotEmpty) {
        _token = t;
        return true;
      }
    } on DioException catch (_) {
      // fall through
    }
    _token = null;
    return false;
  }

  Future<Response<dynamic>> _send(String method, String path, {Object? data, Map<String, dynamic>? query}) {
    final o = Options(method: method, headers: {if (_token != null) 'Authorization': 'Bearer $_token'});
    return dio.request<dynamic>(path, data: data, queryParameters: query, options: o);
  }

  Future<dynamic> request(String method, String path, {Object? data, Map<String, dynamic>? query}) async {
    final isAuth = path.startsWith('/auth/login') || path.startsWith('/auth/register') || path.startsWith('/auth/refresh');
    try {
      return (await _send(method, path, data: data, query: query)).data;
    } on DioException catch (e) {
      if (e.response?.statusCode == 401 && !isAuth) {
        if (await refresh()) {
          try {
            return (await _send(method, path, data: data, query: query)).data;
          } on DioException catch (e2) {
            throw _wrap(e2);
          }
        }
        onExpired?.call();
      }
      throw _wrap(e);
    }
  }

  Future<dynamic> get(String p, {Map<String, dynamic>? query}) => request('GET', p, query: query);
  Future<dynamic> post(String p, {Object? data, Map<String, dynamic>? query}) => request('POST', p, data: data, query: query);
  Future<dynamic> put(String p, {Object? data}) => request('PUT', p, data: data);

  /// Downloads a binary file (resume PDF/DOCX). Returns the bytes and the server's suggested filename.
  Future<(List<int>, String?)> download(String path, {Map<String, dynamic>? query}) async {
    Future<Response<List<int>>> go() => dio.request<List<int>>(path,
        queryParameters: query,
        options: Options(method: 'GET', responseType: ResponseType.bytes, headers: {if (_token != null) 'Authorization': 'Bearer $_token'}));
    Response<List<int>> r;
    try {
      try {
        r = await go();
      } on DioException catch (e) {
        if (e.response?.statusCode == 401 && await refresh()) {
          r = await go();
        } else {
          rethrow;
        }
      }
    } on DioException catch (e) {
      throw _wrap(e);
    }
    final cd = r.headers.value('content-disposition') ?? '';
    final m = RegExp(r'filename\*?=(?:UTF-8.{2})?"?([^";]+)"?').firstMatch(cd);
    return (r.data ?? <int>[], m == null ? null : Uri.decodeComponent(m.group(1)!));
  }

  static ApiException _wrap(DioException e) {
    final code = e.response?.statusCode;
    if (code == null) {
      return ApiException("You're offline or the server can't be reached.", offline: true);
    }
    final d = e.response?.data;
    var msg = 'Something went wrong ($code).';
    if (d is Map) {
      final det = d['detail'] ?? d['message'];
      if (det is String) {
        msg = det;
      } else if (det is List && det.isNotEmpty && det.first is Map) {
        msg = '${(det.first as Map)['msg'] ?? msg}';
      } else if (det is Map && det['message'] is String) {
        msg = det['message'] as String;
      }
    }
    return ApiException(msg, status: code);
  }
}
