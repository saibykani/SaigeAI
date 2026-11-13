import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../applications/application_detail_screen.dart';

/// Weekly goals, follow-ups for silent applications, and salary insight from real postings.
class GrowthScreen extends StatefulWidget {
  const GrowthScreen({super.key, this.initial = 'goals'});
  final String initial;
  @override
  State<GrowthScreen> createState() => _GrowthScreenState();
}

class _GrowthScreenState extends State<GrowthScreen> {
  late String _tab = widget.initial;

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Growth',
        subtitle: 'Goals, follow-ups, salary',
        child: Column(children: [
          const SizedBox(height: 6),
          ChipRow(options: const ['goals', 'followups', 'salary'], labels: const {'goals': 'Weekly goals', 'followups': 'Follow-ups', 'salary': 'Salary insight'}, value: _tab, onChanged: (v) => setState(() => _tab = v)),
          const SizedBox(height: 8),
          Expanded(
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 320),
              switchInCurve: Curves.easeOutCubic,
              transitionBuilder: (c, a) => FadeTransition(opacity: a, child: SlideTransition(position: Tween(begin: const Offset(0.05, 0), end: Offset.zero).animate(a), child: c)),
              child: switch (_tab) {
                'goals' => const _Goals(key: ValueKey('g')),
                'followups' => const _Followups(key: ValueKey('f')),
                _ => const _Salary(key: ValueKey('s')),
              },
            ),
          ),
        ]),
      );
}

// ---------------------------------------------------------------- goals

class _Goals extends StatefulWidget {
  const _Goals({super.key});
  @override
  State<_Goals> createState() => _GoalsState();
}

class _GoalsState extends State<_Goals> {
  final _r = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/growth/goals')));

  @override
  void initState() {
    super.initState();
    _r.load();
  }

  @override
  void dispose() {
    _r.dispose();
    super.dispose();
  }

  Future<void> _edit(List<Map<String, dynamic>> goals) async {
    final t = {for (final g in goals) '${g['key']}': (g['target'] as num).toInt()};
    final saved = await showModalBottomSheet<Map<String, int>>(
      context: context,
      isScrollControlled: true,
      backgroundColor: C.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(R.lg))),
      builder: (context) => _TargetSheet(goals: goals, targets: t),
    );
    if (saved == null) return;
    try {
      final r = asMap(await Session.I.api.put('/growth/goals', data: saved));
      _r.set(r);
      success();
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
  }

  @override
  Widget build(BuildContext context) => ResourceView<Map<String, dynamic>>(
        resource: _r,
        builder: (context, d) {
          final goals = asList(d['goals']);
          final done = goals.where((g) => (g['pct'] as num) >= 100).length;
          final learn = asMap(d['learning']);
          return LogoRefreshView(onRefresh: _r.load, slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 6, 20, 0),
              sliver: SliverList.list(children: [
                Stagger(index: 0, child: Text('Week of ${d['week_of']}', style: T.small)),
                const SizedBox(height: 10),
                GridView.count(
                  crossAxisCount: 2,
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  childAspectRatio: 0.92,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  children: [
                    for (final (i, g) in goals.indexed)
                      Stagger(
                        index: i,
                        child: GlassCard(
                          padding: const EdgeInsets.all(14),
                          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                            ScoreRing(score: g['pct'] as num, size: 92, dots: 28),
                            const SizedBox(height: 10),
                            Text('${g['label']}', textAlign: TextAlign.center, maxLines: 2, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5)),
                            Text('${g['done']} of ${g['target']}', style: T.small),
                          ]),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 14),
                Row(children: [
                  Expanded(child: PrimaryButton(label: 'Set targets', icon: Icons.tune_rounded, ghost: true, onTap: () => _edit(goals))),
                ]),
                if (done == goals.length && goals.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 12), child: Center(child: Pill('All goals hit this week', color: C.good, filled: true))),
                if (learn.isNotEmpty) ...[
                  const SectionTitle('Learning'),
                  GlassCard(
                    child: Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
                      _Stat('${learn['in_progress'] ?? 0}', 'In progress'),
                      _Stat('${learn['done'] ?? 0}', 'Finished'),
                      _Stat('${learn['confirmed'] ?? 0}', 'Confirmed'),
                    ]),
                  ),
                ],
              ]),
            ),
          ]);
        },
      );
}

class _Stat extends StatelessWidget {
  const _Stat(this.v, this.l);
  final String v;
  final String l;
  @override
  Widget build(BuildContext context) => Column(children: [Text(v, style: T.h1), Text(l, style: T.small)]);
}

class _TargetSheet extends StatefulWidget {
  const _TargetSheet({required this.goals, required this.targets});
  final List<Map<String, dynamic>> goals;
  final Map<String, int> targets;
  @override
  State<_TargetSheet> createState() => _TargetSheetState();
}

class _TargetSheetState extends State<_TargetSheet> {
  late final Map<String, int> _t = {...widget.targets};
  static const _max = {'applications': 200, 'outreach': 70, 'resumes': 100, 'prep': 50};

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(20, 24, 20, 24 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Weekly targets', style: T.h2),
          const SizedBox(height: 14),
          for (final g in widget.goals)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(children: [
                Expanded(child: Text('${g['label']}', style: const TextStyle(fontWeight: FontWeight.w600))),
                _Step(Icons.remove_rounded, () => setState(() => _t['${g['key']}'] = ((_t['${g['key']}'] ?? 0) - 1).clamp(0, _max['${g['key']}'] ?? 50))),
                SizedBox(width: 48, child: Center(child: Text('${_t['${g['key']}']}', style: T.h2))),
                _Step(Icons.add_rounded, () => setState(() => _t['${g['key']}'] = ((_t['${g['key']}'] ?? 0) + 1).clamp(0, _max['${g['key']}'] ?? 50))),
              ]),
            ),
          const SizedBox(height: 16),
          PrimaryButton(label: 'Save', onTap: () => Navigator.pop(context, _t)),
        ]),
      );
}

class _Step extends StatelessWidget {
  const _Step(this.icon, this.onTap);
  final IconData icon;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: onTap,
        child: Container(width: 40, height: 40, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface3, border: Border.all(color: C.line)), child: Icon(icon, size: 20)),
      );
}

// ---------------------------------------------------------------- follow-ups

class _Followups extends StatefulWidget {
  const _Followups({super.key});
  @override
  State<_Followups> createState() => _FollowupsState();
}

class _FollowupsState extends State<_Followups> {
  final _r = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/growth/ghosting')));

  @override
  void initState() {
    super.initState();
    _r.load();
  }

  @override
  void dispose() {
    _r.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ResourceView<List<Map<String, dynamic>>>(
        resource: _r,
        builder: (context, l) {
          if (l.isEmpty) return const EmptyState(icon: Icons.celebration_rounded, title: 'No one is ghosting you', body: 'Applications with no reply for 10+ days show up here with a nudge to follow up.');
          return LogoRefreshView(onRefresh: _r.load, slivers: [
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 6, 20, 0),
              sliver: SliverList.builder(
                itemCount: l.length,
                itemBuilder: (context, i) {
                  final a = l[i];
                  final days = (a['silent_days'] as num).toInt();
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Stagger(
                      index: i % 8,
                      child: GlassCard(
                        radius: R.md,
                        padding: const EdgeInsets.all(16),
                        onTap: () => pushDepth(context, (_) => ApplicationDetailScreen(appId: '${a['id']}')),
                        child: Row(children: [
                          Container(
                            width: 56,
                            height: 56,
                            decoration: BoxDecoration(shape: BoxShape.circle, color: (days > 20 ? C.bad : C.warn).withValues(alpha: 0.14), border: Border.all(color: days > 20 ? C.bad : C.warn)),
                            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [Text('$days', style: T.h2.copyWith(color: days > 20 ? C.bad : C.warn)), Text('days', style: TextStyle(fontSize: 10, color: C.muted))]),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text('${a['title']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                              Text('${a['company']}', style: T.small),
                              const SizedBox(height: 4),
                              Text('${a['suggestion']}', style: TextStyle(fontSize: 13, color: C.text)),
                            ]),
                          ),
                          Icon(Icons.chevron_right_rounded, color: C.muted),
                        ]),
                      ),
                    ),
                  );
                },
              ),
            ),
          ]);
        },
      );
}

// ---------------------------------------------------------------- salary

class _Salary extends StatefulWidget {
  const _Salary({super.key});
  @override
  State<_Salary> createState() => _SalaryState();
}

class _SalaryState extends State<_Salary> {
  final _role = TextEditingController();
  late final Resource<Map<String, dynamic>> _r = Resource(() async => asMap(await Session.I.api.get('/growth/salary', query: {if (_role.text.trim().isNotEmpty) 'role': _role.text.trim()})));

  @override
  void initState() {
    super.initState();
    _r.load();
  }

  @override
  void dispose() {
    _role.dispose();
    _r.dispose();
    super.dispose();
  }

  void _go() {
    FocusScope.of(context).unfocus();
    _r.data = null;
    _r.load();
  }

  Future<void> _open(String u) => launchUrl(Uri.parse(u), mode: LaunchMode.externalApplication).then((_) {});

  @override
  Widget build(BuildContext context) => ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 6, 20, 120),
        children: [
          TextField(
            controller: _role,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _go(),
            decoration: InputDecoration(hintText: 'Role (blank uses yours)', prefixIcon: Icon(Icons.search_rounded, color: C.muted), suffixIcon: IconButton(icon: Icon(Icons.arrow_forward_rounded, color: C.primary), onPressed: _go)),
          ),
          const SizedBox(height: 16),
          ListenableBuilder(
            listenable: _r,
            builder: (context, _) {
              final d = _r.data;
              if (d == null) return _r.error != null ? ErrorState(error: _r.error!, onRetry: _r.load) : const Busy();
              final o = d['overall'] == null ? null : asMap(d['overall']);
              final cos = asList(d['companies']);
              if (o == null) {
                return Column(children: [
                  const SizedBox(height: 40),
                  const EmptyState(icon: Icons.payments_outlined, title: 'No pay data yet', body: 'Saige only uses salaries listed in real INR postings it has found. Scan career portals, or check the sites below.'),
                  for (final r in asList(d['research']).take(6)) _Links('${r['company']}', asList(r['links']), _open),
                ]);
              }
              final mx = (o['max'] as num).toDouble();
              final mn = (o['min'] as num).toDouble();
              return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Stagger(
                  index: 0,
                  child: GlassCard(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('${d['role']}  ·  ${d['currency']}', style: T.small),
                      const SizedBox(height: 6),
                      Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                        CountUp(value: (o['median'] as num).toDouble(), style: T.display),
                        const SizedBox(width: 8),
                        Padding(padding: EdgeInsets.only(bottom: 6), child: Text('median LPA', style: T.small)),
                      ]),
                      const SizedBox(height: 14),
                      _Range(min: mn, max: mx, median: (o['median'] as num).toDouble(), you: (d['expected_ctc'] as num?)?.toDouble()),
                      const SizedBox(height: 12),
                      Text('${num0(o['min'])} to ${num0(o['max'])} LPA across ${o['postings']} postings', style: T.small),
                      if (d['verdict'] != null) ...[const SizedBox(height: 8), Text('Your expected CTC is ${d['verdict']}.', style: TextStyle(color: C.text, fontSize: 14))],
                    ]),
                  ),
                ),
                const SectionTitle('By company'),
                for (final (i, c) in cos.indexed)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Stagger(
                      index: i % 8,
                      child: GlassCard(
                        radius: R.md,
                        padding: const EdgeInsets.all(14),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Row(children: [
                            Expanded(child: Text('${c['company']}', style: const TextStyle(fontWeight: FontWeight.w600))),
                            Text('${num0(c['median'])} LPA', style: T.h2.copyWith(color: C.good)),
                          ]),
                          Text('${num0(c['min'])} to ${num0(c['max'])}  ·  ${c['postings']} posting${(c['postings'] as num) > 1 ? 's' : ''}', style: T.small),
                          const SizedBox(height: 8),
                          Wrap(spacing: 8, children: [for (final l in asList(c['links'])) Pressable(onTap: () => _open('${l['url']}'), child: Pill('${l['label']}', color: C.primary))]),
                        ]),
                      ),
                    ),
                  ),
                Padding(padding: EdgeInsets.only(top: 6), child: Text('Only INR salaries from real postings. No scraping of salary sites; the links open them for you.', style: T.small)),
              ]);
            },
          ),
        ],
      );
}

class _Links extends StatelessWidget {
  const _Links(this.company, this.links, this.open);
  final String company;
  final List<Map<String, dynamic>> links;
  final Future<void> Function(String) open;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: GlassCard(
          radius: R.md,
          padding: const EdgeInsets.all(14),
          child: Row(children: [
            Expanded(child: Text(company, style: const TextStyle(fontWeight: FontWeight.w600))),
            for (final l in links) Padding(padding: const EdgeInsets.only(left: 8), child: Pressable(onTap: () => open('${l['url']}'), child: Pill('${l['label']}', color: C.primary))),
          ]),
        ),
      );
}

class _Range extends StatelessWidget {
  const _Range({required this.min, required this.max, required this.median, this.you});
  final double min;
  final double max;
  final double median;
  final double? you;
  @override
  Widget build(BuildContext context) {
    final span = (max - min) <= 0 ? 1.0 : max - min;
    double pos(double v) => ((v - min) / span).clamp(0.0, 1.0);
    return LayoutBuilder(
      builder: (context, c) => SizedBox(
        height: 30,
        child: TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: const Duration(milliseconds: 900),
          curve: const SpringCurve(damping: 9, freq: 2.4),
          builder: (context, t, _) => Stack(clipBehavior: Clip.none, children: [
            Positioned(left: 0, right: 0, top: 11, child: Container(height: 8, decoration: BoxDecoration(color: C.surface3, borderRadius: BorderRadius.circular(9)))),
            Positioned(left: 0, top: 11, width: c.maxWidth * pos(median) * t, child: Container(height: 8, decoration: BoxDecoration(color: C.good.withValues(alpha: 0.7), borderRadius: BorderRadius.circular(9)))),
            Positioned(left: c.maxWidth * pos(median) * t - 7, top: 8, child: Container(width: 14, height: 14, decoration: BoxDecoration(color: C.good, shape: BoxShape.circle))),
            if (you != null) Positioned(left: c.maxWidth * pos(you!) * t - 2, top: 0, child: Container(width: 4, height: 30, decoration: BoxDecoration(color: C.primary, borderRadius: BorderRadius.circular(3)))),
          ]),
        ),
      ),
    );
  }
}
