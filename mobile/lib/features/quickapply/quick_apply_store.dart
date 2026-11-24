import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'quick_apply_logic.dart';

/// On-phone memory for Quick apply: the "Ready to send" tray, jobs the user skipped and jobs already handled.
class QuickApplyStore {
  QuickApplyStore._() {
    tray.addListener(() => count.value = tray.value.length);
  }
  static final QuickApplyStore I = QuickApplyStore._();

  static const _kTray = 'qa_tray';
  static const _kSkipped = 'qa_skipped';
  static const _kHandled = 'qa_handled';

  /// Number of items in the tray (drawer badge).
  static final ValueNotifier<int> count = ValueNotifier(0);

  final ValueNotifier<List<ReadyItem>> tray = ValueNotifier(const []);
  Set<String> skipped = {};
  Set<String> handled = {};
  bool _loaded = false;

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    tray.value = decodeTray(p.getString(_kTray));
    skipped = (p.getStringList(_kSkipped) ?? const []).toSet();
    handled = (p.getStringList(_kHandled) ?? const []).toSet();
    _loaded = true;
  }

  Future<void> _save() async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kTray, encodeTray(tray.value));
    await p.setStringList(_kSkipped, capIds(skipped));
    await p.setStringList(_kHandled, capIds(handled));
  }

  Future<void> ensure() async {
    if (!_loaded) await load();
  }

  Future<void> skip(String jobId) async {
    skipped.add(jobId);
    await _save();
  }

  Future<void> clearSkipped() async {
    skipped = {};
    await _save();
  }

  Future<void> add(ReadyItem item) async {
    handled.add(item.jobId);
    tray.value = [item, ...tray.value.where((e) => e.jobId != item.jobId)];
    await _save();
  }

  /// Removes an item after it was sent or discarded. A discarded job is remembered as skipped so it does not come back.
  Future<void> remove(String jobId, {bool discarded = false}) async {
    tray.value = [for (final e in tray.value) if (e.jobId != jobId) e];
    if (discarded) skipped.add(jobId);
    await _save();
  }

  /// Signed-out cleanup: the tray belongs to the old account.
  Future<void> reset() async {
    tray.value = const [];
    skipped = {};
    handled = {};
    _loaded = false;
    final p = await SharedPreferences.getInstance();
    for (final k in [_kTray, _kSkipped, _kHandled]) {
      await p.remove(k);
    }
  }

  Future<void> clearAll() async {
    tray.value = const [];
    skipped = {};
    handled = {};
    await _save();
  }
}
