import 'dart:io';

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/timezone.dart' as tz;

import 'briefing.dart';
import 'briefing_logic.dart';
import 'pulse.dart';
import 'resource.dart';
import 'session.dart';

/// Local notifications 24 h and 1 h before each upcoming interview. Scheduled on the phone (no server push), tapping one
/// opens the War Room. Re-synced whenever the app opens, resumes or the interview list changes.
class Reminders {
  Reminders._();
  static final Reminders I = Reminders._();

  static const kOn = 'interview_reminders';
  static const _kIds = 'reminder_ids';
  DateTime? _last;

  Future<bool> isEnabled() async => (await SharedPreferences.getInstance()).getBool(kOn) ?? true;

  Future<void> setEnabled(bool v) async {
    await (await SharedPreferences.getInstance()).setBool(kOn, v);
    if (v) {
      await sync(force: true);
    } else {
      await cancelAll();
    }
  }

  Future<void> cancelAll() async {
    if (!Platform.isAndroid) return;
    final p = await SharedPreferences.getInstance();
    for (final id in p.getStringList(_kIds) ?? const <String>[]) {
      final n = int.tryParse(id.split('|').first);
      if (n != null) await Pulse.I.plugin.cancel(id: n);
    }
    await p.remove(_kIds);
  }

  /// Loads the 14-day interview list (the same one the War Room shows) and schedules what is still ahead.
  Future<void> sync({bool force = false}) async {
    if (!Platform.isAndroid || Session.I.state != AuthState.signedIn || Session.I.isRecruiter) return;
    final now = DateTime.now();
    if (!force && _last != null && now.difference(_last!).inMinutes < 20) return;
    _last = now;
    if (!await isEnabled()) return;
    List<Map<String, dynamic>> rows;
    try {
      rows = asList(asMap(await Session.I.api.get('/war-room'))['interviews']);
    } catch (_) {
      return; // offline: keep what is already scheduled
    }
    await BriefingService.I.saveInterviews(rows);
    await schedule(rows);
  }

  /// Replaces the scheduled reminders with the ones for [rows] (war-room rows).
  Future<void> schedule(List<Map<String, dynamic>> rows) async {
    await Pulse.I.initPlugin();
    final p = await SharedPreferences.getInstance();
    final plugin = Pulse.I.plugin;
    final now = DateTime.now().toUtc();
    final slots = slotsForInterviews(rows, now);
    final wanted = {for (final s in slots) s.id};
    for (final old in p.getStringList(_kIds) ?? const <String>[]) {
      final n = int.tryParse(old.split('|').first);
      if (n != null && !wanted.contains(n)) await plugin.cancel(id: n); // interview moved, cancelled or done
    }
    final byId = {for (final r in rows) '${r['interview_id'] ?? r['id']}': r};
    final saved = <String>[];
    for (final s in slots) {
      final r = byId[s.interviewId] ?? const {};
      final at = DateTime.parse('${r['scheduled_at']}');
      final (title, body) = reminderText(s.kind, '${r['company'] ?? ''}', '${r['round'] ?? r['role'] ?? ''}', at);
      try {
        await plugin.zonedSchedule(
          id: s.id,
          title: title,
          body: body,
          scheduledDate: tz.TZDateTime.from(s.at, tz.UTC),
          notificationDetails: NotificationDetails(android: Pulse.I.details('interviews', body)),
          androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle, // no exact-alarm permission needed; may land a few minutes late
          payload: 'interview:${s.interviewId}',
        );
        saved.add('${s.id}|${s.interviewId}');
      } catch (_) {}
    }
    await p.setStringList(_kIds, saved);
  }
}
