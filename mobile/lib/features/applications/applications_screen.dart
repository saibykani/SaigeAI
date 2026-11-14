import 'package:material_ui/material_ui.dart';

import '../shell/app_drawer.dart';
import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/confetti.dart';
import '../../core/widgets/ui.dart';
import '../interviews/interviews_screen.dart';
import 'application_detail_screen.dart';

const approvable = {'SHORTLISTED', 'READY_TO_APPLY', 'APPROVAL_REQUIRED', 'APPLICATION_FAILED'};

const _stages = <(String, Set<String>, IconData)>[
  ('To approve', {'DISCOVERED', 'SHORTLISTED', 'READY_TO_APPLY', 'APPROVAL_REQUIRED', 'APPLICATION_FAILED'}, Icons.gavel_rounded),
  ('Applied', {'APPLYING', 'APPLIED', 'RECRUITER_CONTACTED', 'RECRUITER_REPLIED'}, Icons.send_rounded),
  ('Screening', {'SCREENING', 'ASSESSMENT'}, Icons.fact_check_outlined),
  ('Interview', {'INTERVIEW_SCHEDULED', 'INTERVIEW_COMPLETED'}, Icons.event_available_rounded),
  ('Offer', {'OFFER'}, Icons.emoji_events_rounded),
  ('Closed', {'REJECTED', 'WITHDRAWN', 'CLOSED'}, Icons.inventory_2_outlined),
];

final _celebrated = <String>{};

class ApplicationsScreen extends StatefulWidget {
  const ApplicationsScreen({super.key});
  @override
  State<ApplicationsScreen> createState() => _ApplicationsScreenState();
}

class _ApplicationsScreenState extends State<ApplicationsScreen> {
  final _apps = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/applications')));
  final _pages = PageController(viewportFraction: 0.9);
  final _page = ValueNotifier<double>(0);

  @override
  void initState() {
    super.initState();
    _pages.addListener(() => _page.value = _pages.hasClients ? (_pages.page ?? 0) : 0);
    _apps.load().then((_) => _celebrate());
  }

  void _celebrate() {
    final offers = (_apps.data ?? const []).where((a) => a['status'] == 'OFFER' && _celebrated.add('${a['id']}'));
    if (offers.isNotEmpty && mounted) Confetti.burst(context, count: 110);
  }

  @override
  void dispose() {
    _apps.dispose();
    _pages.dispose();
    _page.dispose();
    super.dispose();
  }

  Future<void> _decide(Map<String, dynamic> a, bool approve) async {
    final list = [...?_apps.data];
    try {
      if (approve) {
        await Session.I.api.post('/applications/${a['id']}/approve');
        if (mounted) {
          Confetti.burst(context);
          toast(context, 'Approved: ${a['company']}');
        }
      } else {
        await Session.I.api.post('/applications/${a['id']}/reject');
        if (mounted) toast(context, 'Dismissed ${a['company']}');
      }
      await _apps.load();
    } on ApiException catch (e) {
      _apps.set(list);
      if (mounted) toast(context, e.message, error: true);
    }
  }

  @override
  Widget build(BuildContext context) => SafeArea(
        bottom: false,
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 4),
            child: Row(children: [
              const MenuButton(),
              Expanded(child: Text('Pipeline', style: T.display)),
              Pressable(
                onTap: () => pushDepth(context, (_) => const InterviewsScreen()),
                child: Container(height: 44, padding: const EdgeInsets.symmetric(horizontal: 14), decoration: BoxDecoration(color: C.surface2, borderRadius: BorderRadius.circular(99), border: Border.all(color: C.line)), child: const Row(children: [Icon(Icons.event_rounded, size: 18), SizedBox(width: 6), Text('Interviews', style: TextStyle(fontWeight: FontWeight.w600))])),
              ),
            ]),
          ),
          Expanded(
            child: ResourceView<List<Map<String, dynamic>>>(
              resource: _apps,
              builder: (context, all) {
                final cols = [for (final s in _stages) all.where((a) => s.$2.contains(a['status'])).toList()];
                if (all.isEmpty) return const EmptyState(icon: Icons.view_kanban_outlined, title: 'No applications yet', body: 'Open a job and tap Apply. It lands here and waits for your approval.');
                return Column(children: [
                  _StageBar(counts: [for (final c in cols) c.length], page: _page, onTap: (i) => _pages.animateToPage(i, duration: const Duration(milliseconds: 500), curve: Curves.easeOutCubic)),
                  Expanded(
                    child: PageView.builder(
                      controller: _pages,
                      physics: const BouncingScrollPhysics(),
                      itemCount: _stages.length,
                      itemBuilder: (context, i) => AnimatedBuilder(
                        animation: _page,
                        builder: (context, child) {
                          final d = (_page.value - i).abs().clamp(0.0, 1.0);
                          return Transform.scale(scale: 1 - 0.06 * d, child: Opacity(opacity: 1 - 0.4 * d, child: child));
                        },
                        child: _Column(stage: _stages[i], apps: cols[i], onRefresh: _apps.load, onDecide: _decide, onChanged: _apps.load),
                      ),
                    ),
                  ),
                ]);
              },
            ),
          ),
        ]),
      );
}

class _StageBar extends StatelessWidget {
  const _StageBar({required this.counts, required this.page, required this.onTap});
  final List<int> counts;
  final ValueNotifier<double> page;
  final ValueChanged<int> onTap;
  @override
  Widget build(BuildContext context) => SizedBox(
        height: 52,
        child: ValueListenableBuilder<double>(
          valueListenable: page,
          builder: (context, p, _) => ListView.builder(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: _stages.length,
            itemBuilder: (context, i) {
              final on = (1 - (p - i).abs()).clamp(0.0, 1.0);
              return Pressable(
                onTap: () => onTap(i),
                scale: 0.93,
                child: Container(
                  margin: const EdgeInsets.only(right: 8, top: 6, bottom: 6),
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: Color.lerp(C.surface2, C.primary, on),
                    borderRadius: BorderRadius.circular(99),
                    border: Border.all(color: Color.lerp(C.line, C.primary, on)!),
                  ),
                  child: Row(children: [
                    Text(_stages[i].$1, style: TextStyle(fontWeight: FontWeight.w600, color: Color.lerp(C.muted, C.onPrimary, on))),
                    const SizedBox(width: 8),
                    Text('${counts[i]}', style: TextStyle(fontWeight: FontWeight.w700, color: Color.lerp(C.muted, C.onPrimary, on))),
                  ]),
                ),
              );
            },
          ),
        ),
      );
}

class _Column extends StatelessWidget {
  const _Column({required this.stage, required this.apps, required this.onRefresh, required this.onDecide, required this.onChanged});
  final (String, Set<String>, IconData) stage;
  final List<Map<String, dynamic>> apps;
  final Future<void> Function() onRefresh;
  final Future<void> Function(Map<String, dynamic>, bool) onDecide;
  final VoidCallback onChanged;
  @override
  Widget build(BuildContext context) {
    final queue = stage.$1 == 'To approve';
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6),
      child: LogoRefreshView(onRefresh: onRefresh, slivers: [
        if (apps.isEmpty)
          SliverFillRemaining(hasScrollBody: false, child: EmptyState(icon: stage.$3, title: 'Nothing in ${stage.$1.toLowerCase()}', body: queue ? 'Applications you prepare wait here for your approval.' : 'Cards move here as the status changes.'))
        else ...[
          if (queue) SliverToBoxAdapter(child: Padding(padding: EdgeInsets.fromLTRB(6, 4, 6, 12), child: Text('Swipe right to approve and send, left to dismiss. Nothing goes out until you do.', style: T.small))),
          SliverList.separated(
            itemCount: apps.length,
            separatorBuilder: (_, _) => const SizedBox(height: 10),
            itemBuilder: (context, i) {
              final a = apps[i];
              final card = Stagger(index: i, child: _AppCard(a: a, onChanged: onChanged));
              if (!queue || !approvable.contains(a['status'])) return card;
              return _SwipeApprove(key: ValueKey(a['id']), onApprove: () => onDecide(a, true), onDismiss: () => onDecide(a, false), child: card);
            },
          ),
        ],
      ]),
    );
  }
}

class _SwipeApprove extends StatelessWidget {
  const _SwipeApprove({super.key, required this.child, required this.onApprove, required this.onDismiss});
  final Widget child;
  final VoidCallback onApprove;
  final VoidCallback onDismiss;
  @override
  Widget build(BuildContext context) => Dismissible(
        key: key!,
        confirmDismiss: (dir) async {
          if (dir == DismissDirection.startToEnd) {
            onApprove();
          } else {
            onDismiss();
          }
          return false; // list reloads from the server after the action
        },
        onUpdate: (d) {
          if (d.reached && !d.previousReached) tick();
        },
        background: _swipeBg(Alignment.centerLeft, C.good, Icons.check_rounded, 'Approve'),
        secondaryBackground: _swipeBg(Alignment.centerRight, C.bad, Icons.close_rounded, 'Dismiss'),
        child: child,
      );

  Widget _swipeBg(Alignment al, Color c, IconData i, String t) => Container(
        alignment: al,
        padding: const EdgeInsets.symmetric(horizontal: 26),
        decoration: BoxDecoration(color: c.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(R.md)),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [Icon(i, color: c, size: 30), Text(t, style: TextStyle(color: c, fontWeight: FontWeight.w700))]),
      );
}

class _AppCard extends StatelessWidget {
  const _AppCard({required this.a, required this.onChanged});
  final Map<String, dynamic> a;
  final VoidCallback onChanged;
  @override
  Widget build(BuildContext context) {
    final s = a['match_score'] as num?;
    return GlassCard(
      radius: R.md,
      padding: const EdgeInsets.all(16),
      onTap: () async {
        await pushDepth(context, (_) => ApplicationDetailScreen(appId: '${a['id']}', heroTag: 'app-${a['id']}'));
        onChanged();
      },
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${a['role']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15.5)),
            const SizedBox(height: 3),
            Text('${a['company']}', style: T.small),
            const SizedBox(height: 10),
            Row(children: [Pill(prettyStatus('${a['status']}'), color: a['status'] == 'OFFER' ? C.good : C.muted, filled: true), const SizedBox(width: 8), Text(timeAgo('${a['updated_at']}'), style: T.small)]),
          ]),
        ),
        if (s != null) Hero(tag: 'app-${a['id']}', child: Material(color: Colors.transparent, child: Text('$s%', style: T.h2.copyWith(color: scoreColor(s))))),
      ]),
    );
  }
}
