import 'dart:convert';
import 'dart:io';

import 'package:shared_preferences/shared_preferences.dart';

import 'briefing_logic.dart';
import 'pulse.dart';
import 'resource.dart';
import 'session.dart';

/// The morning briefing: a screen plus one local notification each morning (default 8:30 IST).
///
/// In the app the briefing is built from live data (radar, war room, pulse, streak). In the background WorkManager only has
/// the read-only pulse token, which can read replies and approvals but not the radar, interviews or streak, so those come
/// from a snapshot saved the last time the app was open (interviews are filtered by their real times, matches and streak are
/// dropped when the snapshot is too old). Tapping the notification always opens the screen, which loads live data.
class BriefingService {
  BriefingService._();
  static final BriefingService I = BriefingService._();

  static const kOn = 'briefing_on';
  static const kMinutes = 'briefing_minutes';
  static const kLastDay = 'briefing_last_day';
  static const kCache = 'briefing_cache';
  static const kSeen = 'briefing_seen';
  static const kNew = 'briefing_new_ids';
  static const kNewDay = 'briefing_new_day';
  static const notificationId = 880001;

  Future<SharedPreferences> _p() async {
    final p = await SharedPreferences.getInstance();
    await p.reload();
    return p;
  }

  Future<bool> isEnabled() async => (await _p()).getBool(kOn) ?? true;
  Future<int> minutes() async => (await _p()).getInt(kMinutes) ?? defaultBriefingMinutes;

  Future<void> setEnabled(bool v) async => (await SharedPreferences.getInstance()).setBool(kOn, v);
  Future<void> setMinutes(int m) async {
    final p = await SharedPreferences.getInstance();
    await p.setInt(kMinutes, m);
    await p.remove(kLastDay); // a new time can fire again today if it is still ahead
  }

  // ------------------------------------------------------------------ live data

  Future<dynamic> _try(Future<dynamic> Function() f) async {
    try {
      return await f();
    } catch (_) {
      return null;
    }
  }

  /// Builds the briefing from live data, saves the snapshot for background use and updates the "already seen" matches.
  Future<Briefing> loadLive({bool markSeen = true}) async {
    final api = Session.I.api;
    final r = await Future.wait([
      _try(() => api.get('/radar', query: {'top': 20})),
      _try(() => api.get('/war-room')),
      _try(() => api.get('/mobile/pulse')),
      _try(() => api.get('/mobile/streak')),
    ]);
    final matches = asList(asMap(r[0])['items']);
    final interviews = asList(asMap(r[1])['interviews']);
    final pulse = asMap(r[2]);
    final streak = asMap(r[3]);
    final now = DateTime.now().toUtc();
    final p = await _p();
    final cache = _readCache(p);
    // keep the old snapshot for any part that failed to load
    await p.setString(
      kCache,
      jsonEncode({
        'at': now.toIso8601String(),
        'name': Session.I.firstName,
        'matches': r[0] != null ? [for (final m in matches) {'id': m['id'], 'title': m['title'], 'company': m['company'], 'score': m['score']}] : cache['matches'],
        'interviews': r[1] != null ? interviews : cache['interviews'],
        'streak': r[3] != null ? streak : cache['streak'],
        'matches_at': r[0] != null ? now.toIso8601String() : cache['matches_at'],
        'streak_at': r[3] != null ? now.toIso8601String() : cache['streak_at'],
      }),
    );
    final exclude = _excluded(p, now);
    final b = assembleBriefing(
      now: now,
      matches: matches,
      interviews: interviews,
      replies: pulse['replies'] as List? ?? const [],
      approvals: (pulse['approvals'] as List? ?? const []).length,
      streak: r[3] != null ? streak : null,
      seenMatchIds: exclude,
    );
    if (markSeen) await _markSeen(p, [for (final m in matches) if (((m['score'] as num?) ?? 0) >= strongMatch) '${m['id']}'], now);
    return b;
  }

  Map<String, dynamic> _readCache(SharedPreferences p) {
    try {
      return Map<String, dynamic>.from(jsonDecode(p.getString(kCache) ?? '{}') as Map);
    } catch (_) {
      return {};
    }
  }

  /// Interview rows from the last snapshot (used by reminders and the background briefing).
  Future<void> saveInterviews(List<Map<String, dynamic>> interviews) async {
    final p = await SharedPreferences.getInstance();
    final c = _readCache(p);
    c['interviews'] = interviews;
    c['at'] ??= DateTime.now().toUtc().toIso8601String();
    await p.setString(kCache, jsonEncode(c));
  }

  Set<String> _excluded(SharedPreferences p, DateTime now) => excludeSeen(
        seen: (p.getStringList(kSeen) ?? const []).toSet(),
        newToday: (p.getStringList(kNew) ?? const []).toSet(),
        newDay: p.getString(kNewDay),
        today: istDay(now),
      );

  Future<void> _markSeen(SharedPreferences p, List<String> ids, DateTime now) async {
    final today = istDay(now);
    final seen = (p.getStringList(kSeen) ?? []).toList();
    final exclude = _excluded(p, now);
    final fresh = [for (final id in ids) if (!exclude.contains(id)) id];
    final sameDay = p.getString(kNewDay) == today;
    final todays = {if (sameDay) ...(p.getStringList(kNew) ?? const <String>[]), ...fresh};
    for (final id in ids) {
      if (!seen.contains(id)) seen.add(id);
    }
    await p.setStringList(kSeen, seen.length > 400 ? seen.sublist(seen.length - 400) : seen);
    await p.setStringList(kNew, todays.toList());
    await p.setString(kNewDay, today);
  }

  // ------------------------------------------------------------------ notification

  Future<bool> _due(SharedPreferences p, DateTime now) => Future.value(shouldShowBriefing(
        nowUtc: now,
        enabled: p.getBool(kOn) ?? true,
        minutes: p.getInt(kMinutes) ?? defaultBriefingMinutes,
        lastDay: p.getString(kLastDay),
      ));

  Future<void> _show(Briefing b, String name, SharedPreferences p, DateTime now) async {
    final (title, body) = briefingNotificationText(b, name: name);
    await Pulse.I.initPlugin(foreground: Session.I.state == AuthState.signedIn);
    await Pulse.I.show(notificationId, title, body, payload: 'briefing', channel: 'briefing');
    await p.setString(kLastDay, istDay(now)); // once per IST day
  }

  /// In the app (after a pulse check): if the briefing is due, build it from live data and show it once.
  Future<void> foregroundTick() async {
    if (!Platform.isAndroid) return;
    final p = await _p();
    final now = DateTime.now().toUtc();
    if (!await _due(p, now)) return;
    final b = await loadLive();
    if (b.isEmpty) return; // nothing real to say: stay quiet, try again later this morning
    await _show(b, Session.I.firstName, p, now);
  }

  /// In the background task: pulse data plus the saved snapshot. Needs no login session.
  Future<void> backgroundTick(Map<String, dynamic> pulse) async {
    final p = await _p();
    final now = DateTime.now().toUtc();
    if (!await _due(p, now)) return;
    final c = _readCache(p);
    bool freshWithin(String? iso, int days) {
      final t = DateTime.tryParse(iso ?? '');
      return t != null && now.difference(t).inHours < days * 24;
    }

    final useMatches = freshWithin(c['matches_at'] as String?, 1);
    final useStreak = freshWithin(c['streak_at'] as String?, 2);
    final matches = useMatches ? (c['matches'] as List? ?? const []) : const [];
    final b = assembleBriefing(
      now: now,
      matches: matches,
      interviews: c['interviews'] as List? ?? const [],
      replies: pulse['replies'] as List? ?? const [],
      approvals: (pulse['approvals'] as List? ?? const []).length,
      streak: useStreak ? Map<String, dynamic>.from(c['streak'] as Map? ?? const {}) : null,
      seenMatchIds: _excluded(p, now),
    );
    if (b.isEmpty) return;
    await _markSeen(p, [for (final m in _maps(matches)) if (((m['score'] as num?) ?? 0) >= strongMatch) '${m['id']}'], now);
    await _show(b, '${c['name'] ?? ''}', p, now);
  }

  List<Map<String, dynamic>> _maps(dynamic v) => asList(v);

  /// Shows today's briefing right away (Settings "Send a test").
  Future<void> test() async {
    if (!Platform.isAndroid) return;
    final b = await loadLive(markSeen: false);
    final (title, body) = briefingNotificationText(b, name: Session.I.firstName);
    await Pulse.I.initPlugin();
    await Pulse.I.show(notificationId, title, body.isEmpty ? 'Nothing new right now. Check back after your next reply or match.' : body, payload: 'briefing', channel: 'briefing');
  }
}
