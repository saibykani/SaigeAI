import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

/// Admin console: platform KPIs and the user list with role change and enable/disable.
class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key});
  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  String _tab = 'overview';
  String _role = '';
  final _q = TextEditingController();
  final _ov = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/admin/overview')));
  late final Resource<List<Map<String, dynamic>>> _users = Resource(() async => asList(await Session.I.api.get('/admin/users', query: {'q': _q.text.trim(), 'role': _role})));

  @override
  void initState() {
    super.initState();
    _ov.load();
    _users.load();
  }

  @override
  void dispose() {
    _q.dispose();
    _ov.dispose();
    _users.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Admin',
        subtitle: 'Platform overview and users',
        child: Column(children: [
          ChipRow(options: const ['overview', 'users'], labels: const {'overview': 'Overview', 'users': 'Users'}, value: _tab, onChanged: (v) => setState(() => _tab = v)),
          const SizedBox(height: 8),
          Expanded(child: _tab == 'overview' ? _overview() : _usersTab()),
        ]),
      );

  Widget _overview() => ResourceView<Map<String, dynamic>>(
        resource: _ov,
        builder: (context, d) {
          final k = asMap(d['kpis']);
          final tiles = <(String, String, Color)>[
            ('Users', '${k['total_users']}', C.blue),
            ('Job seekers', '${k['jobseekers']}', C.good),
            ('Recruiters', '${k['recruiters']}', C.violet),
            ('Admins', '${k['admins']}', C.warn),
            ('New (7d)', '${k['new_7d']}', C.teal),
            ('Active (24h)', '${k['active_24h']}', C.lime),
            ('Applications', '${k['applications']}', C.blue),
            ('Resumes', '${k['resumes']}', C.warn),
            ('Portfolios', '${k['portfolios_published']}', C.violet),
            ('Agent runs (30d)', '${k['agent_runs_30d']}', C.good),
          ];
          final signups = asList(d['signups']);
          final maxS = signups.fold<num>(1, (m, e) => (e['count'] as num) > m ? e['count'] as num : m);
          return RefreshIndicatorList(onRefresh: _ov.load, children: [
            GridView.count(
              crossAxisCount: 2,
              mainAxisSpacing: 10,
              crossAxisSpacing: 10,
              childAspectRatio: 1.7,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              children: [
                for (final (i, t) in tiles.indexed)
                  Stagger(
                    index: i ~/ 2,
                    child: Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(color: Color.alphaBlend(t.$3.withValues(alpha: C.dark ? 0.14 : 0.1), C.surface), borderRadius: BorderRadius.circular(R.md)),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [Text(t.$1, style: T.small), CountUp(value: num.tryParse(t.$2) ?? 0, style: T.h1.copyWith(color: t.$3))]),
                    ),
                  ),
              ],
            ),
            const SectionTitle('Signups, last 30 days'),
            GlassCard(
              child: SizedBox(
                height: 90,
                child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                  for (final s in signups)
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 1),
                        child: TweenAnimationBuilder<double>(
                          tween: Tween(begin: 0, end: ((s['count'] as num) / maxS).toDouble()),
                          duration: const Duration(milliseconds: 800),
                          curve: Curves.easeOutCubic,
                          builder: (_, v, _) => FractionallySizedBox(heightFactor: v.clamp(0.04, 1.0), child: Container(decoration: BoxDecoration(color: C.primary.withValues(alpha: 0.85), borderRadius: BorderRadius.circular(3)))),
                        ),
                      ),
                    ),
                ]),
              ),
            ),
          ]);
        },
      );

  Widget _usersTab() => Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
          child: TextField(
            controller: _q,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _users.load(),
            decoration: InputDecoration(hintText: 'Search name or email', prefixIcon: Icon(Icons.search_rounded, color: C.muted), contentPadding: const EdgeInsets.symmetric(vertical: 14)),
          ),
        ),
        ChipRow(options: const ['', 'jobseeker', 'recruiter', 'admin'], labels: const {'': 'All', 'jobseeker': 'Job seekers', 'recruiter': 'Recruiters', 'admin': 'Admins'}, value: _role, onChanged: (v) {
          _role = v;
          _users.load();
        }),
        const SizedBox(height: 6),
        Expanded(
          child: ResourceView<List<Map<String, dynamic>>>(
            resource: _users,
            builder: (context, l) {
              if (l.isEmpty) return const EmptyState(icon: Icons.group_off_rounded, title: 'No users match', body: 'Try a different search or role.');
              return RefreshIndicatorList(onRefresh: _users.load, children: [
                for (final (i, u) in l.indexed)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Stagger(
                      index: i % 8,
                      child: GlassCard(
                        radius: R.md,
                        padding: const EdgeInsets.all(14),
                        onTap: u['is_super_admin'] == true ? null : () => _edit(u),
                        child: Row(children: [
                          CircleAvatar(radius: 20, backgroundColor: C.primarySoft, child: Text(('${u['name']}'.isEmpty ? '${u['email']}' : '${u['name']}')[0].toUpperCase(), style: TextStyle(color: C.primary, fontWeight: FontWeight.w700))),
                          const SizedBox(width: 12),
                          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${u['name']}'.isEmpty ? '${u['email']}' : '${u['name']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)), Text('${u['email']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small), Text('${u['resumes']} resumes  ·  ${u['applications']} applications', style: T.small)])),
                          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                            Pill(u['is_super_admin'] == true ? 'Super admin' : prettyStatus('${u['role']}'), color: u['role'] == 'admin' ? C.warn : C.blue, filled: true),
                            if (u['is_active'] == false) Padding(padding: const EdgeInsets.only(top: 4), child: Pill('Disabled', color: C.bad)),
                          ]),
                        ]),
                      ),
                    ),
                  ),
              ]);
            },
          ),
        ),
      ]);

  Future<void> _edit(Map<String, dynamic> u) async {
    await showSheet<void>(
      context,
      (ctx) => StatefulBuilder(builder: (ctx, set) {
        Future<void> patch(Map<String, dynamic> body, String ok) async {
          final r = await guarded(ctx, () => Session.I.api.request('PATCH', '/admin/users/${u['id']}', data: body), ok: ok);
          if (r != null) {
            success();
            if (ctx.mounted) Navigator.pop(ctx);
            _users.load();
          }
        }

        final active = u['is_active'] != false;
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('${u['name']}'.isEmpty ? '${u['email']}' : '${u['name']}', style: T.h2),
          Text('${u['email']}', style: T.small),
          const SizedBox(height: 16),
          Text('ROLE', style: T.label),
          const SizedBox(height: 8),
          ChipRow(padding: 0, options: const ['jobseeker', 'recruiter', 'admin'], labels: const {'jobseeker': 'Job seeker', 'recruiter': 'Recruiter', 'admin': 'Admin'}, value: '${u['role']}', onChanged: (v) {
            if (v != u['role']) patch({'role': v}, 'Role changed');
          }),
          const SizedBox(height: 18),
          PrimaryButton(
            label: active ? 'Disable account' : 'Enable account',
            ghost: true,
            onTap: () async {
              if (active && !await confirmSheet(ctx, title: 'Disable this account?', body: 'They are signed out everywhere and cannot sign in until you enable them again.', action: 'Disable', danger: true)) return;
              await patch({'is_active': !active}, active ? 'Account disabled' : 'Account enabled');
            },
          ),
        ]);
      }),
    );
  }
}
