import 'dart:io';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import 'api.dart';
import 'config.dart';

enum AuthState { unknown, signedOut, signedIn }

/// App-wide session + API singleton (kept deliberately tiny: ChangeNotifier, no framework).
class Session extends ChangeNotifier {
  Session._();
  static final Session I = Session._();

  late ApiClient api;
  AuthState state = AuthState.unknown;
  Map<String, dynamic> user = {};
  final ValueNotifier<int> unread = ValueNotifier(0);

  String get name => (user['name'] as String?) ?? '';
  String get firstName => name.trim().isEmpty ? 'there' : name.trim().split(' ').first;
  bool get isRecruiter => user['role'] == 'recruiter';
  bool get isAdmin => user['role'] == 'admin' || user['is_super_admin'] == true;
  bool get isSuperAdmin => user['is_super_admin'] == true;

  Future<void> init({ApiClient? client}) async {
    if (client != null) {
      api = client..onExpired = _expired;
      return;
    }
    final dio = Dio();
    try {
      final dir = await getApplicationSupportDirectory();
      dio.interceptors.add(CookieManager(PersistCookieJar(storage: FileStorage('${dir.path}${Platform.pathSeparator}cookies'))));
    } catch (_) {
      dio.interceptors.add(CookieManager(CookieJar()));
    }
    api = ApiClient(baseUrl: AppConfig.baseUrl, dio: dio, onExpired: _expired);
  }

  void _expired() {
    if (state == AuthState.signedIn) {
      state = AuthState.signedOut;
      notifyListeners();
    }
  }

  /// Restores the session from the persisted refresh cookie.
  Future<void> bootstrap() async {
    try {
      if (await api.refresh()) {
        user = Map<String, dynamic>.from(await api.get('/auth/me') as Map);
        state = AuthState.signedIn;
      } else {
        state = AuthState.signedOut;
      }
    } catch (_) {
      state = AuthState.signedOut;
    }
    notifyListeners();
  }

  Future<void> _afterToken(dynamic data) async {
    api.setToken((data as Map)['access_token'] as String);
    user = Map<String, dynamic>.from(await api.get('/auth/me') as Map);
    state = AuthState.signedIn;
    notifyListeners();
  }

  Future<void> login(String email, String password) async =>
      _afterToken(await api.post('/auth/login', data: {'email': email.trim(), 'password': password}));

  Future<void> loginWithGoogle(String idToken, {String role = 'jobseeker'}) async =>
      _afterToken(await api.post('/auth/google/mobile', data: {'id_token': idToken, 'role': role}));

  Future<void> register({required String name, required String email, required String password, required String role}) async =>
      _afterToken(await api.post('/auth/register', data: {'name': name.trim(), 'email': email.trim(), 'password': password, 'role': role}));

  Future<void> logout() async {
    try {
      await api.post('/auth/logout');
    } catch (_) {}
    api.setToken(null);
    user = {};
    state = AuthState.signedOut;
    notifyListeners();
  }

  Future<void> refreshUnread() async {
    try {
      final r = await api.get('/notifications/unread-count');
      unread.value = (r['unread'] as num?)?.toInt() ?? 0;
    } catch (_) {}
  }
}
