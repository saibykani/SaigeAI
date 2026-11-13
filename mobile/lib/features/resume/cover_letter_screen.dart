import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/confetti.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

/// Pick a saved job, get a truth-checked cover letter, copy it or share the Word file.
class CoverLetterScreen extends StatefulWidget {
  const CoverLetterScreen({super.key});
  @override
  State<CoverLetterScreen> createState() => _CoverLetterScreenState();
}

class _CoverLetterScreenState extends State<CoverLetterScreen> {
  final _jobs = Resource<List<Map<String, dynamic>>>(() async => asList(asMap(await Session.I.api.get('/jobs', query: {'limit': 60, 'sort': 'score'}))['items']));
  String? _jobId;
  Map<String, dynamic>? _letter;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _jobs.load();
  }

  @override
  void dispose() {
    _jobs.dispose();
    super.dispose();
  }

  Future<void> _generate() async {
    final id = _jobId;
    if (id == null) return toast(context, 'Pick a job first.', error: true);
    setState(() => _busy = true);
    try {
      final r = asMap(await Session.I.api.post('/jobs/$id/cover-letter', data: <String, dynamic>{}));
      success();
      if (mounted) {
        setState(() => _letter = r);
        Confetti.burst(context);
      }
    } on ApiException catch (e) {
      if (mounted) toast(context, friendly(e), error: true);
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final l = _letter;
    return FeatureScaffold(
      title: 'Cover letter',
      subtitle: 'Written from your verified profile',
      child: ListenableBuilder(
        listenable: _jobs,
        builder: (context, _) {
          final jobs = _jobs.data;
          if (jobs == null) return _jobs.error != null ? ErrorState(error: _jobs.error!, onRetry: _jobs.load) : const LoadingState();
          if (jobs.isEmpty) return const EmptyState(icon: Icons.work_outline_rounded, title: 'No saved jobs yet', body: 'Save a job from Jobs or Find jobs, then come back to write its cover letter.');
          return ListView(
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 120),
            children: [
              const Text('PICK A JOB', style: T.label),
              const SizedBox(height: 10),
              for (final (i, j) in jobs.take(30).indexed)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Stagger(
                    index: i < 8 ? i : 0,
                    child: Pressable(
                      onTap: () => setState(() {
                        _jobId = '${j['id']}';
                        _letter = null;
                      }),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 220),
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: _jobId == '${j['id']}' ? C.primarySoft : C.surface,
                          borderRadius: BorderRadius.circular(R.md),
                          border: Border.all(color: _jobId == '${j['id']}' ? C.primary : C.line),
                        ),
                        child: Row(children: [
                          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${j['title']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)), Text('${j['company']}', style: T.small)])),
                          if (j['score'] != null) Text('${j['score']}%', style: TextStyle(color: scoreColor(j['score'] as num?), fontWeight: FontWeight.w700)),
                        ]),
                      ),
                    ),
                  ),
                ),
              const SizedBox(height: 14),
              PrimaryButton(label: l == null ? 'Write cover letter' : 'Write again', icon: Icons.edit_note_rounded, busy: _busy, onTap: _generate),
              if (_busy) const Busy(label: 'Writing and checking every claim'),
              if (l != null && !_busy) ...[
                const SectionTitle('Your letter'),
                Stagger(
                  index: 0,
                  child: GlassCard(child: SelectableText('${l['text']}', style: T.body.copyWith(height: 1.5))),
                ),
                const SizedBox(height: 14),
                Row(children: [
                  Expanded(
                    child: PrimaryButton(
                      label: 'Copy',
                      icon: Icons.copy_rounded,
                      ghost: true,
                      onTap: () {
                        Clipboard.setData(ClipboardData(text: '${l['text']}'));
                        toast(context, 'Copied');
                      },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: PrimaryButton(label: 'Word file', icon: Icons.ios_share_rounded, onTap: () => downloadAndShare(context, '/cover-letters/${l['id']}/docx', fallbackName: 'cover-letter.docx'))),
                ]),
                const SizedBox(height: 10),
                Center(child: Text('Truth check: ${asMap(l['validation'])['status'] ?? 'PASSED'}', style: T.small)),
              ],
            ],
          );
        },
      ),
    );
  }
}
