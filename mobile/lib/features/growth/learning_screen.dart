import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/confetti.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

/// Skill gaps from your saved jobs and target roles, with free resources and a weekly plan.
class LearningScreen extends StatefulWidget {
  const LearningScreen({super.key});
  @override
  State<LearningScreen> createState() => _LearningScreenState();
}

class _LearningScreenState extends State<LearningScreen> {
  final _r = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/learning')));
  String? _open;

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

  Future<void> _call(Future<dynamic> Function() f) async {
    try {
      _r.set(asMap(await f()));
      tick();
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
  }

  Future<void> _confirm(Map<String, dynamic> s) async {
    final ok = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: C.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(R.lg))),
      builder: (context) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Add ${s['name']} to your profile?', style: T.h2),
          const SizedBox(height: 8),
          Text('Only if you have really learned or used it. Saige never adds skills you have not confirmed.', style: T.small),
          const SizedBox(height: 18),
          PrimaryButton(label: 'Yes, I have really used it', onTap: () => Navigator.pop(context, true)),
          const SizedBox(height: 8),
          PrimaryButton(label: 'Not yet', ghost: true, onTap: () => Navigator.pop(context, false)),
        ]),
      ),
    );
    if (ok != true) return;
    try {
      await Session.I.api.post('/learning/skills/${s['key']}/confirm', data: {'name': '${s['name']}', 'confirmed': true});
      success();
      if (mounted) Confetti.burst(context);
      await _r.load();
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
  }

  Future<void> _hours(int cur) async {
    var v = cur;
    final res = await showModalBottomSheet<int>(
      context: context,
      backgroundColor: C.surface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(R.lg))),
      builder: (context) => StatefulBuilder(
        builder: (context, set) => Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text('Hours per week', style: T.h2),
            Slider(value: v.toDouble(), min: 1, max: 40, divisions: 39, label: '$v h', activeColor: C.primary, onChanged: (x) => set(() => v = x.round())),
            Center(child: Text('$v hours', style: T.h1)),
            const SizedBox(height: 16),
            PrimaryButton(label: 'Save', onTap: () => Navigator.pop(context, v)),
          ]),
        ),
      ),
    );
    if (res != null) await _call(() => Session.I.api.put('/learning/settings', data: {'hours_per_week': res}));
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Learning path',
        subtitle: 'Close real skill gaps',
        child: ResourceView<Map<String, dynamic>>(
          resource: _r,
          builder: (context, d) {
            final skills = asList(d['skills']);
            final plan = asList(d['plan']);
            final sum = asMap(d['summary']);
            final hpw = (d['hours_per_week'] as num?)?.toInt() ?? 6;
            if (skills.isEmpty) return const EmptyState(icon: Icons.school_outlined, title: 'No gaps found', body: 'Save a few jobs or set a target role. Saige finds the skills they ask for that your profile does not list.');
            return LogoRefreshView(onRefresh: _r.load, slivers: [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 6, 20, 0),
                sliver: SliverList.list(children: [
                  Stagger(
                    index: 0,
                    child: GlassCard(
                      child: Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
                        _Num('${sum['hours_left'] ?? 0}h', 'To go'),
                        _Num('${sum['in_progress'] ?? 0}', 'In progress'),
                        _Num('${sum['done'] ?? 0}', 'Done'),
                        Pressable(onTap: () => _hours(hpw), child: _Num('${hpw}h', 'Per week', accent: true)),
                      ]),
                    ),
                  ),
                  if (plan.isNotEmpty) ...[
                    const SectionTitle('Your weekly plan'),
                    SizedBox(
                      height: 128,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        clipBehavior: Clip.none,
                        physics: const BouncingScrollPhysics(),
                        itemCount: plan.length,
                        separatorBuilder: (_, _) => const SizedBox(width: 10),
                        itemBuilder: (context, i) => Stagger(
                          index: i,
                          dx: 24,
                          child: Container(
                            width: 170,
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(color: C.surface, borderRadius: BorderRadius.circular(R.md), border: Border.all(color: i == 0 ? C.primary : C.line)),
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text('WEEK ${plan[i]['week']}', style: T.label.copyWith(color: i == 0 ? C.primary : C.muted)),
                              const SizedBox(height: 8),
                              for (final it in asList(plan[i]['items']).take(3)) Text('${it['skill']}  ${it['hours']}h', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5)),
                            ]),
                          ),
                        ),
                      ),
                    ),
                  ],
                  const SectionTitle('Skills to learn'),
                  for (final (i, s) in skills.indexed)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Stagger(index: i % 8, child: _SkillCard(skill: s, open: _open == s['key'], onToggle: () => setState(() => _open = _open == s['key'] ? null : '${s['key']}'), onStatus: (st) => _call(() => Session.I.api.put('/learning/skills/${s['key']}', data: {'status': st, 'name': '${s['name']}'})), onResource: (rid, done) => _call(() => Session.I.api.put('/learning/resources', data: {'skill': '${s['key']}', 'resource_id': rid, 'done': done, 'name': '${s['name']}'})), onConfirm: () => _confirm(s))),
                    ),
                ]),
              ),
            ]);
          },
        ),
      );
}

class _Num extends StatelessWidget {
  const _Num(this.v, this.l, {this.accent = false});
  final String v;
  final String l;
  final bool accent;
  @override
  Widget build(BuildContext context) => Column(children: [Text(v, style: T.h1.copyWith(color: accent ? C.primary : C.text)), Text(l, style: T.small)]);
}

class _SkillCard extends StatelessWidget {
  const _SkillCard({required this.skill, required this.open, required this.onToggle, required this.onStatus, required this.onResource, required this.onConfirm});
  final Map<String, dynamic> skill;
  final bool open;
  final VoidCallback onToggle;
  final void Function(String) onStatus;
  final void Function(String, bool) onResource;
  final VoidCallback onConfirm;

  @override
  Widget build(BuildContext context) {
    final st = '${skill['status']}';
    final pct = (skill['progress'] as num?)?.toDouble() ?? 0;
    final res = asList(skill['resources']);
    final color = st == 'done' ? C.good : st == 'in_progress' ? C.warn : C.muted;
    return GlassCard(
      radius: R.md,
      padding: const EdgeInsets.all(16),
      onTap: onToggle,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text('${skill['name']}', style: T.h2.copyWith(fontSize: 17))),
          Pill(prettyStatus(st), color: color, filled: true),
        ]),
        const SizedBox(height: 4),
        Text('${skill['jobs'] ?? 0} of your jobs ask for this  ·  about ${skill['hours']}h', style: T.small),
        const SizedBox(height: 12),
        BarFill(value: pct / 100, color: color),
        AnimatedSize(
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOutCubic,
          alignment: Alignment.topCenter,
          child: !open
              ? const SizedBox(width: double.infinity)
              : Padding(
                  padding: const EdgeInsets.only(top: 14),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    for (final r in res)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Row(children: [
                          Pressable(
                            onTap: () => onResource('${r['id']}', r['done'] != true),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 220),
                              width: 26,
                              height: 26,
                              decoration: BoxDecoration(shape: BoxShape.circle, color: r['done'] == true ? C.good : Colors.transparent, border: Border.all(color: r['done'] == true ? C.good : C.muted, width: 1.5)),
                              child: r['done'] == true ? const Icon(Icons.check_rounded, size: 16, color: Colors.white) : null,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Pressable(
                              onTap: () => launchUrl(Uri.parse('${r['url']}'), mode: LaunchMode.externalApplication),
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text('${r['title']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 14)),
                                Text('${r['provider']}  ·  ${r['hours']}h', style: T.small),
                              ]),
                            ),
                          ),
                          Icon(Icons.open_in_new_rounded, size: 16, color: C.muted),
                        ]),
                      ),
                    const SizedBox(height: 4),
                    Row(children: [
                      if (st != 'in_progress' && st != 'done') Expanded(child: PrimaryButton(label: 'Start', ghost: true, onTap: () => onStatus('in_progress'))),
                      if (st == 'in_progress') Expanded(child: PrimaryButton(label: 'Mark finished', ghost: true, onTap: () => onStatus('done'))),
                      if (st == 'done' && skill['confirmed'] != true) Expanded(child: PrimaryButton(label: 'Add to my profile', onTap: onConfirm)),
                      if (st == 'done' && skill['confirmed'] == true) Expanded(child: Center(child: Pill('On your profile', color: C.good, filled: true))),
                    ]),
                  ]),
                ),
        ),
      ]),
    );
  }
}
