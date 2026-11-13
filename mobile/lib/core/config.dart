import 'package:shared_preferences/shared_preferences.dart';

/// Runtime configuration. The base URL points at the web host, whose `/api`
/// proxy keeps the refresh cookie first-party. Change it in Profile > Settings.
class AppConfig {
  static const defaultBaseUrl = 'https://saige-ai.vercel.app/api';
  static const _key = 'base_url';
  static String baseUrl = defaultBaseUrl;
  static SharedPreferences? _prefs;

  static Future<void> load() async {
    try {
      _prefs = await SharedPreferences.getInstance();
      baseUrl = _prefs?.getString(_key) ?? defaultBaseUrl;
    } catch (_) {
      baseUrl = defaultBaseUrl;
    }
  }

  static Future<void> setBaseUrl(String url) async {
    final clean = url.trim().replaceAll(RegExp(r'/+$'), '');
    baseUrl = clean.isEmpty ? defaultBaseUrl : clean;
    await _prefs?.setString(_key, baseUrl);
  }

  static String get lang => _prefs?.getString('lang') ?? 'en';
  static Future<void> setLang(String v) async => _prefs?.setString('lang', v);

  static bool getFlag(String k, {bool def = true}) => _prefs?.getBool(k) ?? def;
  static Future<void> setFlag(String k, bool v) async => _prefs?.setBool(k, v);
}
