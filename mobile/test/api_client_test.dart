import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:saige_mobile/core/api.dart';

/// Scripted adapter: records requests and answers from a handler.
class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.handler);
  final (int, Object?) Function(RequestOptions) handler;
  final calls = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(RequestOptions o, Stream<Uint8List>? body, Future<void>? cancel) async {
    calls.add(o);
    final (code, data) = handler(o);
    return ResponseBody.fromString(jsonEncode(data), code, headers: {
      Headers.contentTypeHeader: ['application/json'],
    });
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  test('401 triggers one shared refresh, then retries with the new token', () async {
    var token = 'old';
    var refreshes = 0;
    final adapter = FakeAdapter((o) {
      if (o.path == '/auth/refresh') {
        refreshes++;
        token = 'new';
        return (200, {'access_token': 'new', 'expires_in': 900});
      }
      return o.headers['Authorization'] == 'Bearer $token' ? (200, {'ok': true}) : (401, {'detail': 'expired'});
    });
    final api = ApiClient(baseUrl: 'https://x.test/api', dio: Dio()..httpClientAdapter = adapter)..setToken('stale');
    final results = await Future.wait([api.get('/jobs'), api.get('/applications')]);
    expect(results.every((r) => r['ok'] == true), isTrue);
    expect(refreshes, 1, reason: 'concurrent 401s must share one refresh');
    expect(api.token, 'new');
  });

  test('sends the CSRF header on every call', () async {
    final adapter = FakeAdapter((o) => (200, {'access_token': 't', 'expires_in': 900}));
    final api = ApiClient(baseUrl: 'https://x.test/api', dio: Dio()..httpClientAdapter = adapter);
    await api.refresh();
    expect(adapter.calls.single.headers['X-Requested-With'], 'saige');
  });

  test('failed refresh calls onExpired once and surfaces the error', () async {
    var expired = 0;
    final adapter = FakeAdapter((o) => (401, {'detail': 'nope'}));
    final api = ApiClient(baseUrl: 'https://x.test/api', dio: Dio()..httpClientAdapter = adapter, onExpired: () => expired++)..setToken('t');
    await expectLater(api.get('/jobs'), throwsA(isA<ApiException>().having((e) => e.status, 'status', 401)));
    expect(expired, 1);
    expect(api.hasToken, isFalse);
  });

  test('login 401 does not try to refresh and keeps the server message', () async {
    final adapter = FakeAdapter((o) => (401, {'detail': 'Invalid email or password'}));
    final api = ApiClient(baseUrl: 'https://x.test/api', dio: Dio()..httpClientAdapter = adapter);
    await expectLater(api.post('/auth/login', data: {}), throwsA(isA<ApiException>().having((e) => e.message, 'message', 'Invalid email or password')));
    expect(adapter.calls.length, 1);
  });
}
