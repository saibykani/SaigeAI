import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// What the OS asked the app to do: a shortcut / widget route, or content shared into Saige.
class LaunchRequest {
  LaunchRequest({required this.kind, this.route, this.mic = false, this.id, this.text, this.image});
  final String kind; // 'route' | 'share'
  final String? route; // home | assistant | pipeline | scan | interview
  final bool mic;
  final String? id;
  final String? text;
  final String? image;

  factory LaunchRequest.fromMap(Map<dynamic, dynamic> m) => LaunchRequest(
        kind: '${m['kind']}',
        route: m['route'] as String?,
        mic: m['mic'] == true,
        id: m['id'] as String?,
        text: (m['text'] as String?)?.trim(),
        image: m['image'] as String?,
      );
}

/// MethodChannel to MainActivity. The pending request survives until the signed-in Shell consumes it,
/// so a share received while signed out continues after login.
class NativeBridge {
  NativeBridge._();
  static final NativeBridge I = NativeBridge._();
  static const _ch = MethodChannel('ai.saige/native');

  final ValueNotifier<LaunchRequest?> pending = ValueNotifier(null);

  Future<void> init() async {
    if (!Platform.isAndroid) return;
    _ch.setMethodCallHandler((call) async {
      if (call.method == 'launch' && call.arguments is Map) pending.value = LaunchRequest.fromMap(call.arguments as Map);
      return null;
    });
    try {
      final r = await _ch.invokeMethod<Map<dynamic, dynamic>>('initial');
      if (r != null) pending.value = LaunchRequest.fromMap(r);
    } catch (_) {}
  }

  LaunchRequest? take() {
    final r = pending.value;
    pending.value = null;
    return r;
  }

  /// Writes the home-screen widget data and asks Android to redraw it.
  Future<void> updateWidget({required String interview, String? interviewId, required String matches}) async {
    if (!Platform.isAndroid) return;
    try {
      await _ch.invokeMethod<void>('updateWidget', {'interview': interview, 'interviewId': interviewId ?? '', 'matches': matches});
    } catch (_) {}
  }
}
