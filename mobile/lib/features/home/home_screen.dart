import 'package:material_ui/material_ui.dart';

import '../shell/app_drawer.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/ui.dart';
import '../notifications/notifications_screen.dart';
import '../shell/shell.dart';
import '../mock/mock_setup_screen.dart';
import '../resume/ats_coach_screen.dart';
import '../search/find_jobs_screen.dart';
import 'today_feed.dart';

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

  int _n = 0;

  @override
  void initState() {
    super.initState();
    _dash.load();
    _tips.load();
  }

  Future<void> _refresh() async {
    await Future.wait([_dash.load(), _tips.load(), Session.I.refreshUnread()]);
    if (mounted) setState(() => _n++);
  }

  @override
  void dispose() {
    _dash.dispose();
    _tips.dispose();
    super.dispose();
  }

  String _summary(int interviews, int matches, int approvals) {
    final bits = [
      if (interviews > 0) '$interviews interview${interviews == 1 ? '' : 's'} coming up',
      if (matches > 0) '$matches strong match${matches == 1 ? '' : 'es'}',
      if (approvals > 0) '$approvals to approve',
    ];
    return bits.isEmpty ? 'Here is your search at a glance.' : bits.join(' · ');
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
            final totals = asMap(d['totals']);
            final action = asMap(d['action_required']);
            final profile = asMap(d['profile']);
            final ints = asList(d['upcoming_interviews']);
            final matches = asList(d['high_match_jobs']);
            final comp = (profile['completeness'] as num?)?.toDouble() ?? 0;
            final approvals = (action['applications_need_approval'] as num?)?.toInt() ?? 0;
            return LogoRefreshView(onRefresh: _refresh, slivers: [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
                sliver: SliverList.list(children: [
                  Stagger(
                    index: 0,
                    child: Row(children: [
                      const MenuButton(),
                      const Spacer(),
                      _Bell(onTap: () => pushDepth(context, (_) => const NotificationsScreen())),
                    ]),
                  ),
                  const SizedBox(height: 10),
                  Stagger(
                    index: 1,
                    child: _Hero(
                      greet: _greet,
                      name: Session.I.firstName,
                      summary: _summary(ints.length, matches.length, approvals),
                      completeness: comp,
                      applied: totals['applications_sent'],
                      interviews: totals['interviews'],
                      strong: totals['strong_matches'],
                    ),
                  ),
                  const SizedBox(height: 18),
                  Stagger(
                    index: 2,
                    child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                      _Action('Find jobs', Icons.travel_explore_rounded, C.blue, () => pushDepth(context, (_) => const FindJobsScreen())),
                      _Action('ATS resume', Icons.description_rounded, C.good, () => pushDepth(context, (_) => const AtsCoachScreen())),
                      _Action('Mock interview', Icons.record_voice_over_rounded, C.violet, () => pushDepth(context, (_) => const MockSetupScreen())),
                      _Action('Ask Saige', Icons.auto_awesome_rounded, C.warn, () => ShellNav.go(3)),
                    ]),
                  ),
                  const SectionTitle('Today'),
                  ListenableBuilder(
                    listenable: _tips,
                    builder: (context, _) => TodayFeed(key: ValueKey('${_tips.data?.length}-$_n'), dash: d, tips: _tips.data ?? const []),
                  ),
                  const SizedBox(height: 24),
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

const _months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const _days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

/// The elegant top card: today's date, greeting, a one-line summary and the profile ring with three key numbers.
class _Hero extends StatelessWidget {
  const _Hero({required this.greet, required this.name, required this.summary, required this.completeness,
      required this.applied, required this.interviews, required this.strong});
  final String greet, name, summary;
  final double completeness;
  final dynamic applied, interviews, strong;

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final date = '${_days[now.weekday - 1]}, ${now.day} ${_months[now.month - 1]}';
    return Container(
      padding: const EdgeInsets.fromLTRB(22, 22, 22, 20),
      decoration: BoxDecoration(
        color: C.primarySoft,
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: C.primary.withValues(alpha: 0.12)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(date.toUpperCase(), style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 1.1, color: C.primary)),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('$greet,', style: TextStyle(fontSize: 17, color: C.muted, fontWeight: FontWeight.w500)),
              Text(name.isEmpty ? 'there' : name,
                  style: TextStyle(fontSize: 34, height: 1.1, fontWeight: FontWeight.w700, letterSpacing: -1, color: C.text)),
              const SizedBox(height: 8),
              Text(summary, style: TextStyle(fontSize: 14.5, color: C.text.withValues(alpha: 0.75), height: 1.35)),
            ]),
          ),
          const SizedBox(width: 12),
          DotRing(
            size: 96,
            dots: 30,
            progress: completeness / 100,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              CountUp(value: completeness, suffix: '%', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: C.text)),
              Text('PROFILE', style: T.label),
            ]),
          ),
        ]),
        const SizedBox(height: 18),
        Container(
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(color: C.surface, borderRadius: BorderRadius.circular(18), boxShadow: C.shadow),
          child: Row(children: [
            _HeroStat('Applied', applied, C.blue),
            Container(width: 1, height: 30, color: C.line),
            _HeroStat('Interviews', interviews, C.warn),
            Container(width: 1, height: 30, color: C.line),
            _HeroStat('Strong matches', strong, C.good),
          ]),
        ),
      ]),
    );
  }
}

class _HeroStat extends StatelessWidget {
  const _HeroStat(this.label, this.value, this.color);
  final String label;
  final dynamic value;
  final Color color;
  @override
  Widget build(BuildContext context) => Expanded(
        child: Column(children: [
          CountUp(value: (value as num?) ?? 0, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: color)),
          const SizedBox(height: 2),
          Text(label, style: T.small, maxLines: 1, overflow: TextOverflow.ellipsis),
        ]),
      );
}

/// Google-style round quick action: tinted rounded icon + label.
class _Action extends StatelessWidget {
  const _Action(this.label, this.icon, this.color, this.onTap);
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: onTap,
        scale: 0.92,
        child: SizedBox(
          width: 78,
          child: Column(children: [
            Container(
              width: 58,
              height: 58,
              decoration: BoxDecoration(color: color.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(20)),
              child: Icon(icon, color: color, size: 26),
            ),
            const SizedBox(height: 8),
            Text(label, textAlign: TextAlign.center, maxLines: 2, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: C.text)),
          ]),
        ),
      );
}
