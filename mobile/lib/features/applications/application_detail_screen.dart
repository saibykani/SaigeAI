import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/confetti.dart';
import '../../core/widgets/ui.dart';
import 'applications_screen.dart' show approvable;

class ApplicationDetailScreen extends StatefulWidget {
  const ApplicationDetailScreen({super.key, required this.appId, this.heroTag});
  final String appId;
  final String? heroTag;
  @override
  State<ApplicationDetailScreen> createState() => _ApplicationDetailScreenState();
}

class _ApplicationDetailScreenState extends State<ApplicationDetailScreen> {
  late final Resource<Map<String, dynamic>> _app = Resource(() async => asMap(await Session.I.api.get('/applications/${widget.appId}')));
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _app.load();
  }

  @override
  void dispose() {
    _app.dispose();
    super.dispose();
  }

  Future<void> _do(String path, String ok, {Object? body, bool celebrate = false}) async {
    setState(() => _busy = true);
    try {
      await Session.I.api.post('/applications/${widget.appId}/$path', data: body);
      if (mounted) {
        if (celebrate) Confetti.burst(context);
        toast(context, ok);
      }
      await _app.load();
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        body: SafeArea(
          child: Stack(children: [
            ResourceView<Map<String, dynamic>>(
              resource: _app,
              builder: (context, a) {
                final events = asList(a['events']).reversed.toList();
                final ints = asList(a['interviews']);
                final answers = asList(a['answers']);
                final status = '${a['status']}';
                return ListView(
                  physics: const BouncingScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(20, 64, 20, 140),
                  children: [
                    Stagger(index: 0, child: Text('${a['role']}', style: T.h1)),
                    const SizedBox(height: 6),
                    Text('${a['company']}', style: const TextStyle(fontSize: 16, color: C.muted)),
                    const SizedBox(height: 14),
                    Row(children: [
                      Pill(prettyStatus(status), color: status == 'OFFER' ? C.good : C.primary, filled: true),
                      const SizedBox(width: 10),
                      if (a['match_score'] != null) Hero(tag: widget.heroTag ?? 'x', child: Material(color: Colors.transparent, child: Text('${a['match_score']}% match', style: TextStyle(color: scoreColor(a['match_score'] as num?), fontWeight: FontWeight.w700)))),
                    ]),
                    if (approvable.contains(status)) ...[
                      const SizedBox(height: 14),
                      const GlassCard(
                        color: C.primarySoft,
                        padding: EdgeInsets.all(14),
                        child: Row(children: [Icon(Icons.shield_outlined, color: C.primary), SizedBox(width: 12), Expanded(child: Text('Waiting for you. Saige never sends an application without your approval.', style: T.small))]),
                      ),
                    ],
                    if (ints.isNotEmpty) ...[
                      const SectionTitle('Interviews'),
                      for (final i in ints) Padding(padding: const EdgeInsets.only(bottom: 8), child: GlassCard(radius: R.md, padding: const EdgeInsets.all(14), child: Row(children: [const Icon(Icons.event_rounded, color: C.primary), const SizedBox(width: 12), Expanded(child: Text('${i['round'] ?? 'Interview'}  ·  ${_when(i['scheduled_at'])}', style: const TextStyle(fontWeight: FontWeight.w600)))]))),
                    ],
                    if (answers.any((x) => x['status'] == 'REVIEW_REQUIRED')) ...[
                      const SectionTitle('Answers to review'),
                      const GlassCard(child: Text('Some application answers are low confidence. Review them on the web app before approving.', style: T.small)),
                    ],
                    const SectionTitle('Timeline'),
                    if (events.isEmpty) const GlassCard(child: Text('No events yet.', style: T.small)) else _Timeline(events: events),
                  ],
                );
              },
            ),
            Positioned(left: 12, top: 8, child: Pressable(onTap: () => Navigator.of(context).maybePop(), child: Container(width: 46, height: 46, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: const Icon(Icons.arrow_back_rounded)))),
            ListenableBuilder(
              listenable: _app,
              builder: (context, _) {
                final s = '${_app.data?['status']}';
                if (_app.data == null) return const SizedBox.shrink();
                return Positioned(
                  left: 16,
                  right: 16,
                  bottom: 16,
                  child: approvable.contains(s)
                      ? Row(children: [
                          Expanded(child: PrimaryButton(label: 'Dismiss', ghost: true, onTap: _busy ? null : () => _do('reject', 'Dismissed'))),
                          const SizedBox(width: 12),
                          Expanded(flex: 2, child: PrimaryButton(label: 'Approve and apply', icon: Icons.check_rounded, busy: _busy, onTap: () => _do('approve', 'Approved', celebrate: true))),
                        ])
                      : s == 'APPLYING' || s == 'DISCOVERED'
                          ? const SizedBox.shrink()
                          : Row(children: [
                              if (s == 'INTERVIEW_SCHEDULED' || s == 'OFFER' || s == 'APPLIED') Expanded(child: PrimaryButton(label: 'Mark applied', ghost: true, onTap: s == 'APPLIED' ? null : () => _do('mark-applied', 'Marked as applied'))),
                            ]),
                );
              },
            ),
          ]),
        ),
      );

  String _when(dynamic iso) {
    final d = DateTime.tryParse('$iso')?.toLocal();
    return d == null ? '' : '${d.day}/${d.month} ${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';
  }
}

class _Timeline extends StatelessWidget {
  const _Timeline({required this.events});
  final List<Map<String, dynamic>> events;
  @override
  Widget build(BuildContext context) => Column(children: [
        for (final (i, e) in events.indexed)
          Stagger(
            index: i,
            dx: -20,
            child: IntrinsicHeight(
              child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                SizedBox(
                  width: 28,
                  child: Column(children: [
                    Container(width: 12, height: 12, margin: const EdgeInsets.only(top: 5), decoration: BoxDecoration(shape: BoxShape.circle, color: i == 0 ? C.primary : C.surface3, border: Border.all(color: i == 0 ? C.primary : C.muted, width: 1.5))),
                    if (i != events.length - 1) Expanded(child: Container(width: 2, color: C.line)),
                  ]),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 18),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(e['to'] != null ? prettyStatus('${e['to']}') : prettyStatus('${e['type']}'), style: const TextStyle(fontWeight: FontWeight.w600)),
                      if (e['note'] != null) Text('${e['note']}', style: T.small),
                      Text(timeAgo('${e['at']}'), style: T.small),
                    ]),
                  ),
                ),
              ]),
            ),
          ),
      ]);
}
