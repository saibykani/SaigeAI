import 'package:flutter/foundation.dart';

import 'api.dart';

/// Stale-while-revalidate loader: keeps old data visible while reloading.
class Resource<T> extends ChangeNotifier {
  Resource(this._loader);
  final Future<T> Function() _loader;
  T? data;
  ApiException? error;
  bool loading = false;
  bool _disposed = false;

  Future<void> load() async {
    if (loading) return;
    loading = true;
    error = null;
    notifyListeners();
    try {
      data = await _loader();
    } on ApiException catch (e) {
      error = e;
    } catch (_) {
      error = ApiException('Unexpected response. Pull to retry.');
    }
    loading = false;
    if (!_disposed) notifyListeners();
  }

  void set(T v) {
    data = v;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}

Map<String, dynamic> asMap(dynamic v) => v is Map ? Map<String, dynamic>.from(v) : <String, dynamic>{};
List<Map<String, dynamic>> asList(dynamic v) =>
    v is List ? v.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList() : <Map<String, dynamic>>[];
