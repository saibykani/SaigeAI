import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/pulse.dart';
import '../../core/theme.dart';
import '../../core/widgets/confetti.dart';
import '../../core/widgets/ui.dart';
import '../../core/api.dart';
import '../../core/session.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../inbox/inbox_screen.dart';
import '../jobchat/email_draft.dart';

/// The single place for everything waiting for the user: recruiter email drafts and application emails, plus recent replies.
/// Open a draft to edit it, then Send (a confirm sheet shows the recipient first). Sending is the user's approval and goes
/// through the normal endpoints, so the truth guard, pauses and daily caps still apply.
class ApprovalsScreen extends StatefulWidget {
  const ApprovalsScreen({super.key});
  @override
  State<ApprovalsScreen> createState() => _ApprovalsScreenState();
}

class _ApprovalsScreenState extends State<ApprovalsScreen> {
  final _busy = <String>{};
  final _skipped = <String>{};

  @override
  void initState() {
    super.initState();
    Pulse.I.check();
  }

  /// Outreach: open the editable draft (review, edit, confirm, send). Applications: confirm, then approve.
  Future<void> _primary(Map a) async {
    final key = '${a['type']}:${a['id']}';
    if (a['type'] == 'outreach') {
      setState(() => _busy.add(key));
      EmailDraft? d;
      try {
        d = await loadOutreachDraft('${a['id']}');
      } on ApiException catch (e) {
        if (mounted) toast(context, e.message, error: true);
      }
      if (!mounted) return;
      setState(() => _busy.remove(key));
      if (d == null) return toast(context, 'That draft is no longer waiting.', error: true);
      final done = await openDraftSheet(context, d, discard: () => _discard(a, ask: true));
      if (done) {
        setState(() => _skipped.add(key));
        Pulse.I.check();
      }
      return;
    }
    final ok = await confirmSheet(
      context,
      title: 'Send this application?',
      body: '${a['subject'] ?? 'Email your resume'} from your Gmail, with your resume attached.'
          ' ${a['title']}${a['company'] != null ? ' at ${a['company']}' : ''}',
      action: 'Send now',
    );
    if (ok) await _approve(a);
  }

  /// Discards an unsent draft (outreach is cancelled, an application is withdrawn). Returns true when it was discarded.
  Future<bool> _discard(Map a, {bool ask = false}) async {
    if (!await confirmSheet(context, title: 'Discard this draft?', body: 'It will not be sent.', action: 'Discard', danger: true)) return false;
    try {
      if (a['type'] == 'outreach') {
        await Session.I.api.post('/outreach/${a['id']}/outcome/cancelled');
      } else {
        await Session.I.api.post('/applications/${a['id']}/reject');
      }
      if (mounted) {
        setState(() => _skipped.add('${a['type']}:${a['id']}'));
        toast(context, 'Draft discarded');
      }
      Pulse.I.check();
      return true;
    } catch (e) {
      if (mounted) toast(context, friendly(e), error: true);
      return false;
    }
  }

  Future<void> _approve(Map a) async {
    final key = '${a['type']}:${a['id']}';
    setState(() => _busy.add(key));
    final msg = await Pulse.I.approve('${a['type']}', '${a['id']}');
    if (!mounted) return;
    setState(() => _busy.remove(key));
    final ok = msg.startsWith('Sent') || msg.startsWith('Emailed') || msg.startsWith('Open') || msg.startsWith('Approved');
    if (ok) Confetti.burst(context);
    toast(context, msg, error: !ok);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        body: SafeArea(
          child: Stack(children: [
            ValueListenableBuilder<Map<String, dynamic>>(
              valueListenable: Pulse.I.data,
              builder: (context, d, _) {
                final approvals = (d['approvals'] as List? ?? []).cast<Map>().where((a) => !_skipped.contains('${a['type']}:${a['id']}')).toList();
                final replies = (d['replies'] as List? ?? []).cast<Map>();
                return LogoRefreshView(onRefresh: Pulse.I.check, slivers: [
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 64, 20, 120),
                    sliver: SliverList.list(children: [
                      Text('Drafts & approvals', style: T.display),
                      const SizedBox(height: 4),
                      Text('Open a draft to edit it. Nothing is sent until you tap Send and confirm.', style: T.small),
                      const SizedBox(height: 18),
                      SectionTitle('Waiting for you${approvals.isEmpty ? '' : ' · ${approvals.length}'}'),
                      const SizedBox(height: 8),
                      if (approvals.isEmpty)
                        const Padding(padding: EdgeInsets.symmetric(vertical: 24), child: EmptyState(icon: Icons.task_alt_rounded, title: 'All clear', body: 'Applications and recruiter emails that are ready to send will appear here.'))
                      else
                        for (final (i, a) in approvals.indexed) Padding(padding: const EdgeInsets.only(bottom: 10), child: Stagger(index: i, child: _approvalCard(a))),
                      const SizedBox(height: 18),
                      SectionTitle('Replies · last 3 days'),
                      const SizedBox(height: 8),
                      if (replies.isEmpty)
                        Padding(padding: const EdgeInsets.symmetric(vertical: 16), child: Text('No new replies yet. Saige checks your mail every few minutes.', style: T.small))
                      else
                        for (final r in replies)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: GlassCard(
                              radius: R.md,
                              padding: const EdgeInsets.all(16),
                              onTap: () => pushDepth(context, (_) => const InboxScreen()),
                              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Icon(r['status'] == 'bounced' ? Icons.error_outline_rounded : Icons.reply_rounded, color: r['status'] == 'bounced' ? C.bad : C.good),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                    Text(r['status'] == 'bounced' ? 'Bounced: ${r['to'] ?? ''}' : '${r['company'] ?? r['to'] ?? 'Reply'}', style: const TextStyle(fontWeight: FontWeight.w600)),
                                    if ('${r['snippet'] ?? r['subject'] ?? ''}'.isNotEmpty)
                                      Padding(padding: const EdgeInsets.only(top: 3), child: Text('${r['snippet'] ?? r['subject']}', style: T.small, maxLines: 3, overflow: TextOverflow.ellipsis)),
                                    if (r['at'] != null) Padding(padding: const EdgeInsets.only(top: 6), child: Text(timeAgo('${r['at']}'), style: T.label)),
                                  ]),
                                ),
                              ]),
                            ),
                          ),
                    ]),
                  ),
                ]);
              },
            ),
            Positioned(left: 12, top: 8, child: Pressable(onTap: () => Navigator.of(context).maybePop(), child: Container(width: 46, height: 46, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: const Icon(Icons.arrow_back_rounded)))),
          ]),
        ),
      );

  Widget _approvalCard(Map a) {
    final key = '${a['type']}:${a['id']}';
    final email = a['type'] == 'outreach';
    return GlassCard(
      radius: R.md,
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(email ? Icons.mail_outline_rounded : Icons.work_outline_rounded, color: C.primary),
          const SizedBox(width: 10),
          Expanded(child: Text('${a['title']}', style: const TextStyle(fontWeight: FontWeight.w600))),
          Pill(email ? 'Email' : 'Application'),
        ]),
        if (a['company'] != null) Padding(padding: const EdgeInsets.only(top: 4, left: 34), child: Text('${a['company']}', style: T.small)),
        if (a['subject'] != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text('${a['subject']}', style: const TextStyle(fontWeight: FontWeight.w500))),
        if ('${a['preview'] ?? ''}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 4), child: Text('${a['preview']}', style: T.small, maxLines: 4, overflow: TextOverflow.ellipsis)),
        const SizedBox(height: 12),
        Row(children: [
          Pressable(
            onTap: () => _discard(a),
            child: Container(width: 56, height: 56, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: Icon(Icons.delete_outline_rounded, color: C.bad, size: 21)),
          ),
          const SizedBox(width: 10),
          Expanded(child: PrimaryButton(label: 'Not now', ghost: true, onTap: () => setState(() => _skipped.add(key)))),
          const SizedBox(width: 10),
          Expanded(child: PrimaryButton(label: email ? 'Edit & send' : 'Approve', busy: _busy.contains(key), onTap: () => _primary(a))),
        ]),
      ]),
    );
  }
}
