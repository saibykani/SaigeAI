import 'dart:async';

import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/ui.dart';
import '../interviews/interviews_screen.dart';
import '../jobs/job_detail_screen.dart';
import '../notifications/notifications_screen.dart';
import '../shell/shell.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _dash = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/analytics/dashboard')));
  final _tips = Resource<List<Map<String, dynamic>>>(() async {
    final r = await Session.I.api.get('/suggestions');
    return asList(r is Map ? r['items'] ?? r['suggestions'] : r);
  });

  @override
  void initState() {
    super.initState();
    _dash.load();
    _tips.load();
  }

  Future<void> _refresh() async {
    await Future.wait([_dash.load(), _tips.load(), Session.I.refreshUnread()]);
  }

  @override
  void dispose() {
    _dash.dispose();
    _tips.dispose();
    super.dispose();
  }

  String get _greet {
    final h = DateTime.now().hour;
    return h < 5 ? 'Late night' : h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  }

  @override
  Widget build(BuildContext context) => SafeArea(
        bottom: false,
        child: ResourceView<Map<String, dynamic>>(
          resource: _dash,
          builder: (context, d) {
            final today = asMap(d['today']);
            final totals = asMap(d['totals']);
            final health = asMap(d['health']);
            final action = asMap(d['action_required']);
            final profile = asMap(d['profile']);
            final ints = asList(d['upcoming_interviews']);
            final matches = asList(d['high_match_jobs']);
            final comp = (profile['completeness'] as num?)?.toDouble() ?? 0;
            final approvals = (action['applications_need_approval'] as num?)?.toInt() ?? 0;
            final followups = (action['followups_due'] as num?)?.toInt() ?? 0;
            return LogoRefreshView(onRefresh: _refresh, slivers: [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
                sliver: SliverList.list(children: [
                  Stagger(
                    index: 0,
                    child: Row(children: [
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(_greet, style: T.small),
                          Text(Session.I.firstName, style: T.display),
                        ]),
                      ),
                      _Bell(onTap: () => pushDepth(context, (_) => const NotificationsScreen())),
                    ]),
                  ),
                  const SizedBox(height: 22),
                  Stagger(
                    index: 1,
                    child: GlassCard(
                      child: Row(children: [
                        DotRing(
                          size: 118,
                          dots: 36,
                          progress: comp / 100,
                          child: Column(mainAxisSize: MainAxisSize.min, children: [
                            CountUp(value: comp, suffix: '%', style: T.h1),
                            const Text('PROFILE', style: T.label),
                          ]),
                        ),
                        const SizedBox(width: 20),
                        Expanded(
                          child: Column(children: [
                            _Stat('Applied', totals['applications_sent'], C.text),
                            const SizedBox(height: 14),
                            _Stat('Interviews', totals['interviews'], C.warn),
                            const SizedBox(height: 14),
                            _Stat('Strong matches', totals['strong_matches'], C.good),
                          ]),
                        ),
                      ]),
                    ),
                  ),
                  if (approvals > 0 || followups > 0) ...[
                    const SizedBox(height: 14),
                    Stagger(
                      index: 2,
                      child: GlassCard(
                        onTap: () => ShellNav.go(2),
                        color: C.primarySoft,
                        border: C.primary.withValues(alpha: 0.5),
                        padding: const EdgeInsets.all(16),
                        child: Row(children: [
                          const Icon(Icons.bolt_rounded, color: C.primary),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              [if (approvals > 0) '$approvals application${approvals == 1 ? '' : 's'} waiting for your approval', if (followups > 0) '$followups follow-up${followups == 1 ? '' : 's'} due'].join(' · '),
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                          ),
                          const Icon(Icons.chevron_right_rounded, color: C.muted),
                        ]),
                      ),
                    ),
                  ],
                  const SizedBox(height: 14),
                  Stagger(
                    index: 3,
                    child: Row(children: [
                      Expanded(child: _Mini('Jobs today', today['jobs_found'], Icons.travel_explore_rounded)),
                      const SizedBox(width: 10),
                      Expanded(child: _Mini('Replies', today['replies'], Icons.mark_email_read_outlined)),
                      const SizedBox(width: 10),
                      Expanded(child: _Mini('Response', health['response_rate'], Icons.speed_rounded, suffix: '%')),
                    ]),
                  ),
                  const SectionTitle('Next interview'),
                  Stagger(index: 4, child: ints.isEmpty ? _NoInterview() : _NextInterview(i: ints.first)),
                  if (matches.isNotEmpty) ...[
                    const SectionTitle('Best matches for you'),
                  ],
                ]),
              ),
              if (matches.isNotEmpty)
                SliverToBoxAdapter(
                  child: SizedBox(
                    height: 150,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      physics: const BouncingScrollPhysics(),
                      itemCount: matches.length,
                      separatorBuilder: (_, _) => const SizedBox(width: 12),
                      itemBuilder: (context, i) => Stagger(index: i, dx: 40, child: _MatchTile(m: matches[i])),
                    ),
                  ),
                ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 0),
                sliver: SliverList.list(children: [
                  const SectionTitle('Coach tips'),
                  ListenableBuilder(
                    listenable: _tips,
                    builder: (context, _) {
                      final tips = (_tips.data ?? const []).take(4).toList();
                      if (tips.isEmpty) {
                        return GlassCard(child: Text(_tips.loading ? 'Finding what would help most...' : 'Your profile looks solid. Tips appear here as you apply.', style: T.small));
                      }
                      return Column(children: [for (final (i, t) in tips.indexed) Stagger(index: i, child: Padding(padding: const EdgeInsets.only(bottom: 10), child: _Tip(t: t)))]);
                    },
                  ),
                  const SizedBox(height: 10),
                  GlassCard(
                    onTap: () => pushDepth(context, (_) => const InterviewsScreen()),
                    child: const Row(children: [
                      Icon(Icons.event_available_rounded, color: C.primary),
                      SizedBox(width: 12),
                      Expanded(child: Text('Interviews and invites from your inbox', style: TextStyle(fontWeight: FontWeight.w600))),
                      Icon(Icons.chevron_right_rounded, color: C.muted),
                    ]),
                  ),
                ]),
              ),
            ]);
          },
        ),
      );
}

class _Bell extends StatelessWidget {
  const _Bell({required this.onTap});
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: onTap,
        child: Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)),
          child: ValueListenableBuilder<int>(
            valueListenable: Session.I.unread,
            builder: (context, n, _) => Stack(alignment: Alignment.center, clipBehavior: Clip.none, children: [
              const Icon(Icons.notifications_none_rounded),
              if (n > 0)
                Positioned(
                  right: 8,
                  top: 8,
                  child: TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0, end: 1),
                    duration: const Duration(milliseconds: 600),
                    curve: springy,
                    builder: (_, v, child) => Transform.scale(scale: v.clamp(0.0, 1.6), child: child),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                      decoration: BoxDecoration(color: C.primary, borderRadius: BorderRadius.circular(99)),
                      child: Text(n > 9 ? '9+' : '$n', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: Colors.white)),
                    ),
                  ),
                ),
            ]),
          ),
        ),
      );
}

class _Stat extends StatelessWidget {
  const _Stat(this.label, this.value, this.color);
  final String label;
  final dynamic value;
  final Color color;
  @override
  Widget build(BuildContext context) => Row(children: [
        Container(width: 4, height: 28, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
        const SizedBox(width: 12),
        CountUp(value: (value as num?) ?? 0, style: T.h1),
        const SizedBox(width: 10),
        Expanded(child: Text(label, style: T.small, maxLines: 1, overflow: TextOverflow.ellipsis)),
      ]);
}

class _Mini extends StatelessWidget {
  const _Mini(this.label, this.value, this.icon, {this.suffix = ''});
  final String label;
  final dynamic value;
  final IconData icon;
  final String suffix;
  @override
  Widget build(BuildContext context) => GlassCard(
        padding: const EdgeInsets.all(14),
        radius: R.md,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(icon, size: 20, color: C.muted),
          const SizedBox(height: 10),
          value == null ? const Text('--', style: T.h1) : CountUp(value: value as num, suffix: suffix, style: T.h1),
          Text(label, style: T.small),
        ]),
      );
}

class _NoInterview extends StatelessWidget {
  @override
  Widget build(BuildContext context) => const GlassCard(
        child: Row(children: [
          Icon(Icons.event_busy_rounded, color: C.muted),
          SizedBox(width: 12),
          Expanded(child: Text('No interview scheduled. When a recruiter invites you, it shows up here with a live countdown.', style: T.small)),
        ]),
      );
}

class _NextInterview extends StatefulWidget {
  const _NextInterview({required this.i});
  final Map<String, dynamic> i;
  @override
  State<_NextInterview> createState() => _NextInterviewState();
}

class _NextInterviewState extends State<_NextInterview> {
  Timer? _t;
  final _now = ValueNotifier(DateTime.now());

  @override
  void initState() {
    super.initState();
    _t = Timer.periodic(const Duration(seconds: 1), (_) => _now.value = DateTime.now());
  }

  @override
  void dispose() {
    _t?.cancel();
    _now.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final at = DateTime.tryParse('${widget.i['scheduled_at']}')?.toLocal();
    final url = widget.i['meeting_url'] as String?;
    return GlassCard(
      onTap: () => pushDepth(context, (_) => const InterviewsScreen()),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${widget.i['company'] ?? ''}', style: T.h2),
        Text('${widget.i['role'] ?? ''}  ·  ${widget.i['round'] ?? 'Interview'}', style: T.small),
        const SizedBox(height: 16),
        if (at != null)
          ValueListenableBuilder<DateTime>(
            valueListenable: _now,
            builder: (context, now, _) {
              final d = at.difference(now);
              final neg = d.isNegative;
              final a = d.abs();
              return Row(children: [
                _Unit(neg ? 0 : a.inDays, 'DAYS'),
                _Unit(neg ? 0 : a.inHours % 24, 'HRS'),
                _Unit(neg ? 0 : a.inMinutes % 60, 'MIN'),
                _Unit(neg ? 0 : a.inSeconds % 60, 'SEC'),
              ]);
            },
          ),
        if (url != null && url.isNotEmpty) ...[
          const SizedBox(height: 16),
          PrimaryButton(label: 'Join meeting', icon: Icons.videocam_rounded, onTap: () => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication)),
        ],
      ]),
    );
  }
}

class _Unit extends StatelessWidget {
  const _Unit(this.v, this.label);
  final int v;
  final String label;
  @override
  Widget build(BuildContext context) => Expanded(
        child: Column(children: [
          Text(v.toString().padLeft(2, '0'), style: T.display.copyWith(fontFeatures: const [FontFeature.tabularFigures()])),
          Text(label, style: T.label),
        ]),
      );
}

class _MatchTile extends StatelessWidget {
  const _MatchTile({required this.m});
  final Map<String, dynamic> m;
  @override
  Widget build(BuildContext context) {
    final s = m['score'] as num?;
    return SizedBox(
      width: 220,
      child: GlassCard(
        onTap: () => pushDepth(context, (_) => JobDetailScreen(jobId: '${m['id']}', heroTag: 'home-${m['id']}')),
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Hero(tag: 'home-${m['id']}', child: Text('${s ?? '--'}%', style: T.h1.copyWith(color: scoreColor(s)))),
            const Spacer(),
            const Icon(Icons.north_east_rounded, size: 18, color: C.muted),
          ]),
          const Spacer(),
          Text('${m['title']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
          const SizedBox(height: 2),
          Text('${m['company']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
        ]),
      ),
    );
  }
}

class _Tip extends StatelessWidget {
  const _Tip({required this.t});
  final Map<String, dynamic> t;
  @override
  Widget build(BuildContext context) => GlassCard(
        padding: const EdgeInsets.all(16),
        radius: R.md,
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Icon(Icons.lightbulb_outline_rounded, color: C.warn, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${t['title'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w600)),
              if ('${t['why'] ?? ''}'.isNotEmpty) ...[const SizedBox(height: 4), Text('${t['why']}', style: T.small, maxLines: 3, overflow: TextOverflow.ellipsis)],
            ]),
          ),
        ]),
      );
}
