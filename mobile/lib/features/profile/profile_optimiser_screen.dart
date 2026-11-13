import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../search/saved_jobs_screen.dart' show RefreshIndicatorList;

/// LinkedIn and Naukri have no profile-edit API, so Saige prepares truthful, copy-ready changes.
/// You copy each one into the site yourself, then mark it applied.
class ProfileOptimiserScreen extends StatefulWidget {
  const ProfileOptimiserScreen({super.key});
  @override
  State<ProfileOptimiserScreen> createState() => _ProfileOptimiserScreenState();
}

class _ProfileOptimiserScreenState extends State<ProfileOptimiserScreen> {
  String _platform = 'linkedin';
  final _ov = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/profile-sync/overview')));
  late final Resource<List<Map<String, dynamic>>> _changes = Resource(() async => asList(await Session.I.api.get('/profile-changes', query: {'platform': _platform})));
  bool _running = false;

  @override
  void initState() {
    super.initState();
    _ov.load();
    _changes.load();
  }

  @override
  void dispose() {
    _ov.dispose();
    _changes.dispose();
    super.dispose();
  }

  Future<void> _refresh() => Future.wait([_ov.load(), _changes.load()]);

  Future<void> _run() async {
    setState(() => _running = true);
    final r = await guarded(context, () => Session.I.api.post('/profile-sync/run'), ok: 'Analysis finished');
    if (!mounted) return;
    setState(() => _running = false);
    if (r != null) {
      success();
      await _refresh();
    }
  }

  Future<void> _act(Map<String, dynamic> c, String action, {String? ok}) async {
    final r = await guarded(context, () => Session.I.api.post('/profile-changes/${c['id']}/$action'), ok: ok);
    if (r != null) {
      tick();
      await _refresh();
    }
  }

  Color _col(String s) => switch (s) { 'USER_APPROVED' => C.good, 'APPLIED' => C.good, 'USER_REJECTED' => C.muted, _ => C.warn };
  String _label(Map<String, dynamic> c) => c['applied_at'] != null ? 'Applied' : switch ('${c['approval_status']}') { 'USER_APPROVED' => 'Ready to copy', 'USER_REJECTED' => 'Rejected', _ => 'Needs review' };

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Profile optimiser',
        subtitle: 'Copy-ready edits for LinkedIn and Naukri',
        child: Column(children: [
          ChipRow(options: const ['linkedin', 'naukri', 'resume'], labels: const {'linkedin': 'LinkedIn', 'naukri': 'Naukri', 'resume': 'Resume'}, value: _platform, onChanged: (v) {
            setState(() => _platform = v);
            _changes.data = null;
            _changes.load();
          }),
          const SizedBox(height: 8),
          Expanded(
            child: ListenableBuilder(
              listenable: Listenable.merge([_ov, _changes]),
              builder: (context, _) {
                if (_changes.data == null) return _changes.error != null ? ErrorState(error: _changes.error!, onRetry: _refresh) : const LoadingState();
                final o = _ov.data == null ? <String, dynamic>{} : asMap(_ov.data![_platform]);
                final l = _changes.data!;
                return RefreshIndicatorList(onRefresh: _refresh, children: [
                  if (o['completeness'] != null)
                    Stagger(
                      index: 0,
                      child: GlassCard(
                        child: Row(children: [
                          ScoreRing(score: (o['completeness'] as num?) ?? 0, size: 92, label: 'COMPLETE'),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text('Keyword match ${o['keyword_alignment'] ?? '--'}%', style: const TextStyle(fontWeight: FontWeight.w700)),
                              const SizedBox(height: 4),
                              if ((o['missing_fields'] as List?)?.isNotEmpty ?? false) Text('Missing: ${(o['missing_fields'] as List).take(4).join(', ')}', style: T.small),
                              if ((o['skills_to_add'] as List?)?.isNotEmpty ?? false) Text('Skills to add: ${(o['skills_to_add'] as List).take(4).join(', ')}', style: T.small),
                            ]),
                          ),
                        ]),
                      ),
                    ),
                  const SizedBox(height: 12),
                  PrimaryButton(label: 'Analyse my profiles', icon: Icons.auto_fix_high_rounded, busy: _running, onTap: _run),
                  const SizedBox(height: 14),
                  if (l.isEmpty)
                    const EmptyState(icon: Icons.task_alt_rounded, title: 'No suggestions', body: 'Run the analysis. Every suggestion is checked against your verified profile first.')
                  else
                    for (final (i, c) in l.indexed)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Stagger(index: i % 8 + 1, child: _ChangeCard(change: c, label: _label(c), color: _col('${c['approval_status']}'), onAct: _act)),
                      ),
                ]);
              },
            ),
          ),
        ]),
      );
}

class _ChangeCard extends StatelessWidget {
  const _ChangeCard({required this.change, required this.label, required this.color, required this.onAct});
  final Map<String, dynamic> change;
  final String label;
  final Color color;
  final Future<void> Function(Map<String, dynamic>, String, {String? ok}) onAct;

  String _s(dynamic v) => v == null ? '' : (v is List ? v.join(', ') : '$v');

  @override
  Widget build(BuildContext context) {
    final applied = change['applied_at'] != null;
    final rejected = change['approval_status'] == 'USER_REJECTED';
    final approved = change['approval_status'] == 'USER_APPROVED';
    return GlassCard(
      radius: R.md,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Expanded(child: Text(prettyStatus('${change['field']}'.replaceAll('.', '_')), style: const TextStyle(fontWeight: FontWeight.w700))), Pill(label, color: color, filled: true)]),
        if (_s(change['reason']).isNotEmpty) ...[const SizedBox(height: 4), Text(_s(change['reason']), style: T.small)],
        if (_s(change['before']).isNotEmpty) ...[
          const SizedBox(height: 10),
          Text('NOW', style: T.label),
          const SizedBox(height: 4),
          Text(_s(change['before']), maxLines: 3, overflow: TextOverflow.ellipsis, style: T.small),
        ],
        const SizedBox(height: 10),
        Text('SUGGESTED', style: T.label),
        const SizedBox(height: 4),
        Container(width: double.infinity, padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: C.good.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(R.sm)), child: SelectableText(_s(change['after']), style: T.body.copyWith(fontSize: 14))),
        const SizedBox(height: 12),
        if (!applied && !rejected)
          Wrap(spacing: 8, runSpacing: 8, children: [
            PrimaryButton(label: 'Copy', icon: Icons.copy_rounded, expand: false, onTap: () => copyText(context, _s(change['after']), done: 'Copied. Paste it into the site.')),
            if (!approved) PrimaryButton(label: 'Approve', ghost: true, expand: false, onTap: () => onAct(change, 'approve', ok: 'Approved')),
            if (approved) PrimaryButton(label: 'I applied it', ghost: true, expand: false, onTap: () => onAct(change, 'applied', ok: 'Marked as applied')),
            PrimaryButton(label: 'Reject', ghost: true, expand: false, onTap: () => onAct(change, 'reject')),
          ]),
      ]),
    );
  }
}
