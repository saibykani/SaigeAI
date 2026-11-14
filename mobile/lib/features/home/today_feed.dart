import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/ui.dart';
import '../applications/application_detail_screen.dart';
import '../interviews/interviews_screen.dart';
import '../jobs/job_detail_screen.dart';
import '../resume/ats_coach_screen.dart';

/// One actionable card in the Today feed.
class TodayItem {
  TodayItem({required this.id, required this.icon, required this.color, required this.title, required this.detail,
      required this.primary, required this.primaryIcon, this.secondary, this.confirm, this.onPrimary, this.onSecondary, this.onOpen,
      this.keepOnPrimary = false});
  final String id;
  final IconData icon;
  final Color color;
  final String title, detail;
  final String primary;
  final IconData primaryIcon;
  final String? secondary;

  /// Outward actions ask first: (title, body, button label).
  final (String, String, String)? confirm;

  /// Returns true when the card is finished and should leave the feed.
  final Future<bool> Function(BuildContext)? onPrimary;
  final Future<bool> Function(BuildContext)? onSecondary;
  final VoidCallback? onOpen;

  /// The primary action only navigates (e.g. Join), so the card stays.
  final bool keepOnPrimary;
}

String _today() {
  final n = DateTime.now();
  return '${n.year}-${n.month}-${n.day}';
}

Future<Set<String>> _loadDismissed() async {
  try {
    final p = await SharedPreferences.getInstance();
    final raw = p.getStringList('today_dismissed') ?? const [];
    if (raw.isEmpty || raw.first != _today()) return {};
    return raw.skip(1).toSet();
  } catch (_) {
    return {};
  }
}

Future<void> _saveDismissed(Set<String> ids) async {
  try {
    final p = await SharedPreferences.getInstance();
    await p.setStringList('today_dismissed', [_today(), ...ids]);
  } catch (_) {}
}

String _when(DateTime at) {
  final now = DateTime.now();
  final d = at.difference(now);
  final sameDay = at.year == now.year && at.month == now.month && at.day == now.day;
  final hm = '${at.hour.toString().padLeft(2, '0')}:${at.minute.toString().padLeft(2, '0')}';
  if (d.isNegative) return 'started at $hm';
  if (sameDay) return d.inMinutes < 60 ? 'in ${math.max(d.inMinutes, 1)} min, $hm' : 'today in ${d.inHours}h ${d.inMinutes % 60}m, $hm';
  return 'tomorrow $hm';
}

Future<List<TodayItem>> _build(Map<String, dynamic> dash, List<Map<String, dynamic>> tips, BuildContext ctx) async {
  final api = Session.I.api;
  final now = DateTime.now();
  final dayStart = DateTime(now.year, now.month, now.day);
  final tomorrowEnd = dayStart.add(const Duration(days: 2));
  Future<V> safe<V>(Future<V> f, V fallback) async {
    try {
      return await f;
    } catch (_) {
      return fallback;
    }
  }

  final res = await Future.wait<dynamic>([
    safe(api.get('/emails/interviews'), const []),
    safe(api.get('/applications'), const []),
    safe(api.get('/jobs', query: {'limit': 100, 'status': 'saved'}), const {}),
    safe(api.get('/jobs', query: {'limit': 100, 'status': 'shortlisted'}), const {}),
    safe(api.get('/growth/ghosting'), const []),
  ]);
  final items = <TodayItem>[];

  // 1. Interviews today / tomorrow, from the dashboard and from interview mail (deduped by time).
  final ivs = <(DateTime, Map<String, dynamic>)>[];
  for (final i in asList(dash['upcoming_interviews'])) {
    final at = DateTime.tryParse('${i['scheduled_at']}')?.toLocal();
    if (at != null) ivs.add((at, {'id': '${i['id']}', 'company': i['company'], 'role': i['role'], 'round': i['round'], 'url': i['meeting_url']}));
  }
  for (final e in asList(res[0])) {
    final ex = asMap(e['extracted']);
    final at = DateTime.tryParse('${ex['interview_at']}')?.toLocal();
    if (at == null || ivs.any((x) => (x.$1.difference(at).inMinutes).abs() < 30)) continue;
    ivs.add((at, {'id': 'm${e['id']}', 'company': ex['sender_name'] ?? e['subject'], 'role': e['subject'], 'round': ex['interview_round'], 'url': ex['meeting_url']}));
  }
  ivs.sort((a, b) => a.$1.compareTo(b.$1));
  for (final (at, i) in ivs) {
    if (at.isBefore(now.subtract(const Duration(hours: 1))) || !at.isBefore(tomorrowEnd)) continue;
    final url = '${i['url'] ?? ''}';
    items.add(TodayItem(
      id: 'int:${i['id']}',
      icon: Icons.event_available_rounded,
      color: C.good,
      title: '${i['company'] ?? 'Interview'}: ${i['round'] ?? 'Interview'}',
      detail: '${_when(at)}${'${i['role'] ?? ''}'.isEmpty ? '' : '  ·  ${i['role']}'}',
      primary: url.isEmpty ? 'Open' : 'Join',
      primaryIcon: url.isEmpty ? Icons.event_rounded : Icons.videocam_rounded,
      keepOnPrimary: true,
      onPrimary: (c) async {
        if (url.isEmpty) {
          pushDepth(c, (_) => const InterviewsScreen());
        } else {
          await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication).catchError((_) => false);
        }
        return false;
      },
      secondary: 'Prep',
      onSecondary: (c) async {
        pushDepth(c, (_) => const InterviewsScreen());
        return false;
      },
      onOpen: () => pushDepth(ctx, (_) => const InterviewsScreen()),
    ));
  }

  // 2. Applications waiting for approval.
  final waiting = asList(res[1]).where((a) => const {'APPROVAL_REQUIRED', 'READY_TO_APPLY'}.contains(a['status'])).take(4);
  for (final a in waiting) {
    final detailScreen = ApplicationDetailScreen(appId: '${a['id']}');
    items.add(TodayItem(
      id: 'app:${a['id']}',
      icon: Icons.gavel_rounded,
      color: C.primary,
      title: 'Approve: ${a['role']}',
      detail: '${a['company']}${a['match_score'] != null ? '  ·  ${a['match_score']}% match' : ''}  ·  waiting for you',
      primary: 'Approve',
      primaryIcon: Icons.check_rounded,
      secondary: 'Review',
      confirm: ('Approve and apply?', 'Your tailored resume goes to ${a['company']} for ${a['role']}. Nothing is sent until you confirm.', 'Approve'),
      onPrimary: (c) async => await guarded(c, () => api.post('/applications/${a['id']}/approve'), ok: 'Approved: ${a['company']}') != null,
      onSecondary: (c) async {
        pushDepth(c, (_) => detailScreen);
        return false;
      },
      onOpen: () => pushDepth(ctx, (_) => detailScreen),
    ));
  }

  // 3. Saved jobs closing within 3 days.
  final closing = <(DateTime, Map<String, dynamic>)>[];
  for (final j in [...asList(asMap(res[2])['items']), ...asList(asMap(res[3])['items'])]) {
    final d = DateTime.tryParse('${j['deadline']}')?.toLocal();
    if (d == null) continue;
    final days = DateTime(d.year, d.month, d.day).difference(dayStart).inDays;
    if (days >= 0 && days <= 3) closing.add((d, j));
  }
  closing.sort((a, b) => a.$1.compareTo(b.$1));
  for (final (d, j) in closing.take(3)) {
    final days = DateTime(d.year, d.month, d.day).difference(dayStart).inDays;
    items.add(TodayItem(
      id: 'dl:${j['id']}',
      icon: Icons.timer_outlined,
      color: C.warn,
      title: '${j['title']}',
      detail: '${j['company']}  ·  closes ${days == 0 ? 'today' : days == 1 ? 'tomorrow' : 'in $days days'}',
      primary: 'Apply',
      primaryIcon: Icons.send_rounded,
      secondary: 'Hide',
      onPrimary: (c) async => await guarded(c, () => api.post('/applications', data: {'job_id': j['id']}), ok: 'Added to your approval queue') != null,
      onSecondary: (c) async => await guarded(c, () => api.post('/jobs/${j['id']}/status', data: {'status': 'archived'}), ok: 'Hidden') != null,
      onOpen: () => pushDepth(ctx, (_) => JobDetailScreen(jobId: '${j['id']}', heroTag: 'today-${j['id']}')),
    ));
  }

  // 4. Follow-ups due (applications silent for 10+ days).
  for (final g in asList(res[4]).take(3)) {
    final days = (g['silent_days'] as num?)?.toInt() ?? 0;
    final screen = ApplicationDetailScreen(appId: '${g['id']}');
    items.add(TodayItem(
      id: 'fu:${g['id']}',
      icon: Icons.mark_chat_unread_rounded,
      color: C.violet,
      title: 'Follow up with ${g['company'] == '' ? g['title'] : g['company']}',
      detail: 'No reply for $days days  ·  ${g['title']}',
      primary: 'Draft follow-up',
      primaryIcon: Icons.edit_note_rounded,
      secondary: 'Done',
      keepOnPrimary: true,
      onPrimary: (c) async {
        pushDepth(c, (_) => screen);
        return false;
      },
      onSecondary: (c) async => true,
      onOpen: () => pushDepth(ctx, (_) => screen),
    ));
  }

  // 5. Best new matches.
  final shown = items.map((e) => e.id).toSet();
  for (final m in asList(dash['high_match_jobs']).take(3)) {
    if (shown.contains('dl:${m['id']}')) continue;
    items.add(TodayItem(
      id: 'match:${m['id']}',
      icon: Icons.auto_awesome_rounded,
      color: C.blue,
      title: '${m['title']}',
      detail: '${m['company']}  ·  ${m['score'] ?? '--'}% match',
      primary: 'Save',
      primaryIcon: Icons.bookmark_add_outlined,
      secondary: 'Skip',
      onPrimary: (c) async => await guarded(c, () => api.post('/jobs/${m['id']}/status', data: {'status': 'saved'}), ok: 'Saved') != null,
      onSecondary: (c) async => await guarded(c, () => api.post('/jobs/${m['id']}/status', data: {'status': 'archived'})) != null,
      onOpen: () => pushDepth(ctx, (_) => JobDetailScreen(jobId: '${m['id']}', heroTag: 'today-${m['id']}')),
    ));
  }

  // 6. Coach tip of the day.
  if (tips.isNotEmpty) {
    final t = tips.first;
    items.add(TodayItem(
      id: 'tip:${t['id'] ?? t['title']}',
      icon: Icons.lightbulb_outline_rounded,
      color: C.lime,
      title: 'Coach tip: ${t['title'] ?? ''}',
      detail: '${t['why'] ?? 'A small fix that helps your applications.'}',
      primary: 'Got it',
      primaryIcon: Icons.check_rounded,
      secondary: 'Open coach',
      onPrimary: (c) async => true,
      onSecondary: (c) async {
        pushDepth(c, (_) => const AtsCoachScreen());
        return false;
      },
    ));
  }
  return items;
}

/// The "Today" feed: swipeable action cards from real data. Right = primary action, left = dismiss for today.
class TodayFeed extends StatefulWidget {
  const TodayFeed({super.key, required this.dash, required this.tips, this.reload = 0});
  final Map<String, dynamic> dash;
  final List<Map<String, dynamic>> tips;

  /// Bump to rebuild the feed (pull-to-refresh).
  final int reload;
  @override
  State<TodayFeed> createState() => _TodayFeedState();
}

class _TodayFeedState extends State<TodayFeed> {
  final _key = GlobalKey<AnimatedListState>();
  final _items = <TodayItem>[];
  Set<String> _dismissed = {};
  bool _loading = true;
  int _gen = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(TodayFeed old) {
    super.didUpdateWidget(old);
    if (old.reload != widget.reload) _load();
  }

  Future<void> _load() async {
    final gen = ++_gen;
    _dismissed = await _loadDismissed();
    if (!mounted) return;
    final all = await _build(widget.dash, widget.tips, context);
    if (!mounted || gen != _gen) return;
    final fresh = all.where((e) => !_dismissed.contains(e.id)).toList();
    // Replace the list without animation on a (re)load, then let new rows rise in.
    setState(() {
      _items
        ..clear()
        ..addAll(fresh);
      _loading = false;
    });
  }

  void _remove(TodayItem it, {bool animate = true, bool dismiss = true}) {
    final i = _items.indexOf(it);
    if (i < 0) return;
    _items.removeAt(i);
    if (dismiss) {
      _dismissed.add(it.id);
      _saveDismissed(_dismissed);
    }
    _key.currentState?.removeItem(
      i,
      (context, a) => animate ? _Collapse(animation: a, child: _Card(item: it, onPrimary: () {}, onSecondary: () {})) : const SizedBox.shrink(),
      duration: animate ? const Duration(milliseconds: 380) : Duration.zero,
    );
    if (_items.isEmpty) setState(() {});
  }

  Future<bool> _runPrimary(TodayItem it) async {
    final c = context;
    final ask = it.confirm;
    if (ask != null) {
      final ok = await confirmSheet(c, title: ask.$1, body: ask.$2, action: ask.$3);
      if (!ok || !c.mounted) return false;
    }
    tap();
    final done = await it.onPrimary?.call(c) ?? false;
    if (done) success();
    return done;
  }

  Future<void> _button(TodayItem it, bool primary) async {
    final done = primary ? await _runPrimary(it) : (await it.onSecondary?.call(context) ?? false);
    if (done && mounted) _remove(it);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Padding(padding: const EdgeInsets.symmetric(vertical: 18), child: Text('Checking what needs you today...', style: T.small));
    }
    if (_items.isEmpty) return const _AllCaughtUp();
    return AnimatedList(
      key: _key,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      padding: EdgeInsets.zero,
      initialItemCount: _items.length,
      itemBuilder: (context, i, a) {
        if (i >= _items.length) return const SizedBox.shrink();
        final it = _items[i];
        return Stagger(
          index: i.clamp(0, 6),
          child: Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Dismissible(
              key: ValueKey(it.id),
              background: _Swipe(color: it.color, icon: it.primaryIcon, label: it.primary, alignEnd: false),
              secondaryBackground: _Swipe(color: C.muted, icon: Icons.snooze_rounded, label: 'Not today', alignEnd: true),
              confirmDismiss: (dir) async {
                if (dir == DismissDirection.endToStart) {
                  tick();
                  return true;
                }
                final done = await _runPrimary(it);
                return done && !it.keepOnPrimary;
              },
              onDismissed: (dir) => _remove(it, animate: false, dismiss: true),
              child: _Card(item: it, onPrimary: () => _button(it, true), onSecondary: () => _button(it, false)),
            ),
          ),
        );
      },
    );
  }
}

class _Collapse extends StatelessWidget {
  const _Collapse({required this.animation, required this.child});
  final Animation<double> animation;
  final Widget child;
  @override
  Widget build(BuildContext context) {
    final curved = CurvedAnimation(parent: animation, curve: Curves.easeInOutCubic);
    return SizeTransition(
      sizeFactor: curved,
      child: FadeTransition(opacity: curved, child: SlideTransition(position: Tween(begin: const Offset(0.4, 0), end: Offset.zero).animate(curved), child: Padding(padding: const EdgeInsets.only(bottom: 10), child: child))),
    );
  }
}

class _Swipe extends StatelessWidget {
  const _Swipe({required this.color, required this.icon, required this.label, required this.alignEnd});
  final Color color;
  final IconData icon;
  final String label;
  final bool alignEnd;
  @override
  Widget build(BuildContext context) => Container(
        alignment: alignEnd ? Alignment.centerRight : Alignment.centerLeft,
        padding: const EdgeInsets.symmetric(horizontal: 22),
        decoration: BoxDecoration(color: color.withValues(alpha: 0.16), borderRadius: BorderRadius.circular(R.md)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (!alignEnd) Icon(icon, color: color),
          if (!alignEnd) const SizedBox(width: 8),
          Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w700)),
          if (alignEnd) const SizedBox(width: 8),
          if (alignEnd) Icon(icon, color: color),
        ]),
      );
}

class _Card extends StatelessWidget {
  const _Card({required this.item, required this.onPrimary, required this.onSecondary});
  final TodayItem item;
  final VoidCallback onPrimary, onSecondary;
  @override
  Widget build(BuildContext context) {
    final it = item;
    return GlassCard(
      radius: R.md,
      padding: const EdgeInsets.all(14),
      onTap: it.onOpen,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(color: it.color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(14)),
            child: Icon(it.icon, color: it.color, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(it.title, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15.5)),
              const SizedBox(height: 2),
              Text(it.detail, maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
            ]),
          ),
        ]),
        const SizedBox(height: 12),
        Row(children: [
          _Btn(label: it.primary, icon: it.primaryIcon, color: it.color, filled: true, onTap: onPrimary),
          if (it.secondary != null) ...[const SizedBox(width: 8), _Btn(label: it.secondary!, color: it.color, filled: false, onTap: onSecondary)],
        ]),
      ]),
    );
  }
}

class _Btn extends StatelessWidget {
  const _Btn({required this.label, required this.color, required this.filled, required this.onTap, this.icon});
  final String label;
  final IconData? icon;
  final Color color;
  final bool filled;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        haptic: false,
        scale: 0.94,
        onTap: onTap,
        child: Container(
          height: 38,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(color: filled ? color.withValues(alpha: 0.16) : Colors.transparent, borderRadius: BorderRadius.circular(99), border: filled ? null : Border.all(color: C.line)),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            if (icon != null) ...[Icon(icon, size: 17, color: color), const SizedBox(width: 6)],
            Text(label, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5, color: filled ? color : C.muted)),
          ]),
        ),
      );
}

/// A calm illustration (rising sun over hills, drawn with a painter) for an empty feed.
class _AllCaughtUp extends StatelessWidget {
  const _AllCaughtUp();
  @override
  Widget build(BuildContext context) => GlassCard(
        padding: const EdgeInsets.fromLTRB(20, 18, 20, 22),
        child: Column(children: [
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: 1),
            duration: const Duration(milliseconds: 1100),
            curve: Curves.easeOutCubic,
            builder: (_, v, _) => SizedBox(height: 120, width: double.infinity, child: CustomPaint(painter: _CaughtUpPainter(v, C.warn, C.good, C.primary, C.line))),
          ),
          const SizedBox(height: 8),
          Text('All caught up', style: T.h2),
          const SizedBox(height: 4),
          Text('Nothing needs you right now. Saige keeps looking and will list new things here.', textAlign: TextAlign.center, style: T.small),
        ]),
      );
}

class _CaughtUpPainter extends CustomPainter {
  _CaughtUpPainter(this.t, this.sun, this.hill, this.accent, this.line);
  final double t;
  final Color sun, hill, accent, line;
  @override
  void paint(Canvas canvas, Size s) {
    final cx = s.width / 2;
    final base = s.height - 6;
    final sunY = base - 30 - 26 * t;
    canvas.drawCircle(Offset(cx, sunY), 30 + 4 * math.sin(t * math.pi), Paint()..color = sun.withValues(alpha: 0.18));
    canvas.drawCircle(Offset(cx, sunY), 20, Paint()..color = sun.withValues(alpha: 0.9));
    final rays = Paint()
      ..color = sun.withValues(alpha: 0.5 * t)
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;
    for (var i = 0; i < 9; i++) {
      final a = math.pi + math.pi * (i + 0.5) / 9;
      canvas.drawLine(Offset(cx + math.cos(a) * 36, sunY + math.sin(a) * 36), Offset(cx + math.cos(a) * 46, sunY + math.sin(a) * 46), rays);
    }
    Path hillPath(double dx, double h, double w) => Path()
      ..moveTo(cx + dx - w, base)
      ..quadraticBezierTo(cx + dx, base - h * t, cx + dx + w, base)
      ..close();
    canvas.drawPath(hillPath(-70, 62, 110), Paint()..color = hill.withValues(alpha: 0.3));
    canvas.drawPath(hillPath(64, 50, 100), Paint()..color = accent.withValues(alpha: 0.25));
    canvas.drawPath(hillPath(0, 40, 130), Paint()..color = hill.withValues(alpha: 0.55));
    canvas.drawLine(Offset(cx - 150, base), Offset(cx + 150, base), Paint()..color = line);
    // A check mark that draws itself on the sun.
    final p = Path()
      ..moveTo(cx - 8, sunY)
      ..lineTo(cx - 2, sunY + 6)
      ..lineTo(cx + 9, sunY - 6);
    final m = p.computeMetrics().first;
    canvas.drawPath(m.extractPath(0, m.length * Curves.easeOut.transform(((t - 0.4) / 0.6).clamp(0.0, 1.0))), Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round);
  }

  @override
  bool shouldRepaint(_CaughtUpPainter o) => o.t != t || o.sun != sun;
}
