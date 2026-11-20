import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:workmanager/workmanager.dart';

import 'api.dart';
import 'config.dart';
import 'session.dart';

/// Phone alerts: recruiter replies and items waiting for approval.
///
/// - In the app: [check] runs on start, on resume and every few minutes, using the normal session.
/// - In the background: WorkManager runs [pulseDispatcher] every ~15 minutes with a separate read-only
///   "pulse" token (it can only read /mobile/pulse/bg), so it never rotates the login session.
/// - Approve on a notification opens the app and sends through the normal endpoints, so the truth guard,
///   pauses and the daily caps still apply. Nothing is sent from the background.
class Pulse {
  Pulse._();
  static final Pulse I = Pulse._();

  static const task = 'saige-pulse';
  static const _kToken = 'pulse_token';
  static const _kSince = 'pulse_since';
  static const _kSeen = 'pulse_seen';
  static const _kSummary = 'pulse_summary_day';
  static const flag = 'phone_alerts';

  final FlutterLocalNotificationsPlugin _n = FlutterLocalNotificationsPlugin();
  bool _inited = false;

  /// Live state for the in-app Approvals screen and badge.
  final ValueNotifier<Map<String, dynamic>> data = ValueNotifier({'replies': [], 'approvals': []});

  /// A notification action the app must handle once signed in: (actionId, payload).
  final ValueNotifier<(String, String)?> pending = ValueNotifier(null);

  /// Number of items waiting for approval (drawer badge).
  final ValueNotifier<int> waiting = ValueNotifier(0);

  Future<void> initPlugin({bool foreground = true}) async {
    if (_inited || !Platform.isAndroid) return;
    _inited = true;
    await _n.initialize(
      settings: const InitializationSettings(android: AndroidInitializationSettings('@mipmap/ic_launcher')),
      onDidReceiveNotificationResponse: foreground ? (r) => pending.value = (r.actionId ?? 'open', r.payload ?? '') : null,
    );
    if (foreground) {
      final launch = await _n.getNotificationAppLaunchDetails();
      final r = launch?.notificationResponse;
      if (launch?.didNotificationLaunchApp == true && r != null) pending.value = (r.actionId ?? 'open', r.payload ?? '');
    }
  }

  /// Called once the user is signed in: asks for permission, gets a pulse token and schedules background checks.
  Future<void> start() async {
    if (!Platform.isAndroid) return;
    await initPlugin();
    if (!AppConfig.getFlag(flag)) return;
    await _n.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()?.requestNotificationsPermission();
    final prefs = await SharedPreferences.getInstance();
    if ((prefs.getString(_kToken) ?? '').isEmpty) {
      try {
        final r = await Session.I.api.post('/mobile/pulse-token');
        await prefs.setString(_kToken, '${(r as Map)['token']}');
      } catch (_) {}
    }
    try {
      await Workmanager().initialize(pulseDispatcher);
      await Workmanager().registerPeriodicTask(task, task,
          frequency: const Duration(minutes: 15),
          constraints: Constraints(networkType: NetworkType.connected),
          existingWorkPolicy: ExistingPeriodicWorkPolicy.keep);
    } catch (_) {}
    await check();
  }

  /// Turns alerts off: cancels background checks and revokes the token.
  Future<void> stop() async {
    if (!Platform.isAndroid) return;
    final prefs = await SharedPreferences.getInstance();
    try {
      await Workmanager().cancelByUniqueName(task);
    } catch (_) {}
    try {
      await Session.I.api.request('DELETE', '/mobile/pulse-token');
    } catch (_) {}
    await prefs.remove(_kToken);
  }

  /// Signed-out cleanup (the token belongs to the old account).
  Future<void> signOut() async {
    await stop();
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kSeen);
    await prefs.remove(_kSince);
    await prefs.remove(_kSummary);
    data.value = {'replies': [], 'approvals': []};
    waiting.value = 0;
  }

  /// In-app check with the login session; updates [data] and notifies about anything new.
  Future<void> check() async {
    try {
      final d = Map<String, dynamic>.from(await Session.I.api.get('/mobile/pulse') as Map);
      data.value = d;
      waiting.value = (d['approvals'] as List? ?? const []).length;
      if (AppConfig.getFlag(flag)) {
        await notifyNew(d);
        await _dailySummary(d);
      }
    } catch (_) {}
  }

  /// Once a day after 9:00 IST: "Today: X new replies, Y waiting approvals, streak Z days" (only if something is non-zero).
  Future<void> _dailySummary(Map<String, dynamic> d) async {
    if (!Platform.isAndroid) return;
    final ist = DateTime.now().toUtc().add(const Duration(hours: 5, minutes: 30));
    if (ist.hour < 9) return;
    final day = '${ist.year}-${ist.month.toString().padLeft(2, '0')}-${ist.day.toString().padLeft(2, '0')}';
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getString(_kSummary) == day) return;
    var streak = 0;
    try {
      streak = ((await Session.I.api.get('/mobile/streak') as Map)['current'] as num?)?.toInt() ?? 0;
    } catch (_) {}
    final replies = (d['replies'] as List? ?? const []).length;
    final approvals = (d['approvals'] as List? ?? const []).length;
    await prefs.setString(_kSummary, day);
    if (replies + approvals + streak == 0) return;
    await initPlugin();
    await _show('summary:$day', 'Your day in Saige',
        'Today: $replies new ${replies == 1 ? 'reply' : 'replies'}, $approvals waiting ${approvals == 1 ? 'approval' : 'approvals'}, streak $streak ${streak == 1 ? 'day' : 'days'}',
        payload: 'approvals', channel: 'approvals');
  }

  /// Shows a sample notification right away (asks for permission first).
  Future<void> test() async {
    if (!Platform.isAndroid) return;
    await initPlugin();
    await _n.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()?.requestNotificationsPermission();
    await _show('test:${DateTime.now().millisecondsSinceEpoch}', 'Saige test notification', 'Alerts are working. You will see replies and approvals here.',
        payload: 'approvals', channel: 'approvals');
  }

  /// Shows one notification per item not shown before (remembered in prefs, last 300 ids).
  Future<void> notifyNew(Map<String, dynamic> d) async {
    if (!Platform.isAndroid) return;
    final prefs = await SharedPreferences.getInstance();
    await prefs.reload();
    final seen = (prefs.getStringList(_kSeen) ?? []).toList();
    final first = !prefs.containsKey(_kSeen); // first run: remember what exists, don't flood the shade
    final replies = (d['replies'] as List? ?? []).cast<Map>();
    final approvals = (d['approvals'] as List? ?? []).cast<Map>();
    for (final r in replies) {
      final key = 'r:${r['id']}';
      if (seen.contains(key)) continue;
      seen.add(key);
      if (first) continue;
      final bounced = r['status'] == 'bounced';
      await _show(key, bounced ? 'Email bounced: ${r['company'] ?? r['to'] ?? ''}' : 'Reply from ${r['company'] ?? r['to'] ?? 'a recruiter'}',
          bounced ? 'Your email to ${r['to'] ?? 'this contact'} could not be delivered.' : '${r['snippet'] ?? r['subject'] ?? ''}',
          payload: 'reply:${r['id']}', channel: 'replies');
    }
    for (final a in approvals) {
      final key = 'a:${a['type']}:${a['id']}';
      if (seen.contains(key)) continue;
      seen.add(key);
      if (first) continue;
      await _show(key, '${a['title']}${a['company'] != null ? ' · ${a['company']}' : ''}', '${a['subject'] ?? 'Waiting for your approval'}',
          payload: '${a['type']}:${a['id']}', channel: 'approvals', actions: true);
    }
    if (first && approvals.isNotEmpty) {
      final n = approvals.length;
      await _show('summary:first', 'Waiting for your approval', '$n ${n == 1 ? 'item' : 'items'} waiting for your approval',
          payload: 'approvals', channel: 'approvals');
    }
    await prefs.setStringList(_kSeen, seen.length > 300 ? seen.sublist(seen.length - 300) : seen);
  }

  Future<void> _show(String key, String title, String body, {required String payload, required String channel, bool actions = false}) async {
    final details = AndroidNotificationDetails(
      channel,
      channel == 'replies' ? 'Recruiter replies' : 'Waiting for approval',
      channelDescription: channel == 'replies' ? 'Replies and bounces to emails you sent' : 'Applications and emails ready to send after you approve',
      importance: Importance.high,
      priority: Priority.high,
      styleInformation: BigTextStyleInformation(body),
      actions: actions
          ? const [
              AndroidNotificationAction('approve', 'Approve & send', showsUserInterface: true),
              AndroidNotificationAction('skip', 'Not now', cancelNotification: true),
            ]
          : null,
    );
    await _n.show(id: key.hashCode & 0x7fffffff, title: title, body: body, notificationDetails: NotificationDetails(android: details), payload: payload);
  }

  /// Approves one item through the normal endpoints. Returns a message for the user.
  Future<String> approve(String type, String id) async {
    try {
      if (type == 'outreach') {
        await Session.I.api.post('/outreach/$id/send', query: {'approve': true});
        await _n.cancel(id: 'a:outreach:$id'.hashCode & 0x7fffffff);
        await check();
        return 'Sent from your Gmail';
      }
      final r = await Session.I.api.post('/applications/approve-bulk', data: {'ids': [id]});
      await _n.cancel(id: 'a:application:$id'.hashCode & 0x7fffffff);
      await check();
      final res = (r is Map ? r['results'] as List? : null) ?? const [];
      final first = res.isNotEmpty ? Map<String, dynamic>.from(res.first as Map) : <String, dynamic>{};
      return '${first['message'] ?? 'Approved'}';
    } on ApiException catch (e) {
      return e.message;
    }
  }
}

/// WorkManager entry point (background isolate). Reads the pulse with the read-only token and notifies.
@pragma('vm:entry-point')
void pulseDispatcher() {
  Workmanager().executeTask((name, input) async {
    try {
      await AppConfig.load();
      final prefs = await SharedPreferences.getInstance();
      await prefs.reload();
      final token = prefs.getString(Pulse._kToken) ?? '';
      if (token.isEmpty || !(prefs.getBool(Pulse.flag) ?? true)) return true;
      final since = prefs.getString(Pulse._kSince);
      final dio = Dio(BaseOptions(baseUrl: AppConfig.baseUrl, connectTimeout: const Duration(seconds: 15), receiveTimeout: const Duration(seconds: 30),
          headers: {'Authorization': 'Bearer $token', 'X-Requested-With': 'saige'}));
      final r = await dio.get<dynamic>('/mobile/pulse/bg', queryParameters: {'since': ?since});
      final d = Map<String, dynamic>.from(r.data as Map);
      await Pulse.I.initPlugin(foreground: false);
      await Pulse.I.notifyNew(d);
      if (d['now'] is String) await prefs.setString(Pulse._kSince, d['now'] as String);
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        final prefs = await SharedPreferences.getInstance();
        await prefs.remove(Pulse._kToken); // revoked: the app gets a new one next time it opens
      }
    } catch (_) {}
    return true;
  });
}
