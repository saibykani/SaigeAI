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
import '../reply/reply_screen.dart';
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
    await _approve(a); // tapping Approve is the approval; a 5 second Undo bar comes first
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

  static bool _isOk(String msg) => msg.startsWith('Sent') || msg.startsWith('Emailed') || msg.startsWith('Open') || msg.startsWith('Approved');

  Future<void> _approve(Map a) async {
    final key = '${a['type']}:${a['id']}';
    setState(() => _busy.add(key));
    var msg = '';
    final out = await sendWithUndo(context, label: 'Sending ${a['title']}...', send: () async {
      msg = await Pulse.I.approve('${a['type']}', '${a['id']}');
      return _isOk(msg) ? null : msg;
    });
    if (!mounted) return;
    setState(() => _busy.remove(key));
    if (out.undone) return toast(context, 'Not sent. It is still waiting here.');
    if (out.sent) Confetti.burst(context);
    toast(context, out.sent ? msg : '${out.error}', error: !out.sent);
  }

  /// Sends everything waiting, under one Undo window. Each item still goes through the normal send path, so caps, pauses and
  /// the truth guard apply item by item; the summary says what was held back and why.
  Future<void> _sendAll(List<Map> list) async {
    final keys = [for (final a in list) '${a['type']}:${a['id']}'];
    setState(() => _busy.addAll(keys));
    var sent = 0;
    final problems = <String>[];
    final out = await sendWithUndo(context, label: 'Sending ${list.length} ${list.length == 1 ? 'item' : 'items'}...', send: () async {
      for (final a in list) {
        final m = await Pulse.I.approve('${a['type']}', '${a['id']}');
        if (_isOk(m)) {
          sent++;
        } else {
          problems.add(m);
        }
      }
      return null;
    });
    if (!mounted) return;
    setState(() => _busy.removeAll(keys));
    if (out.undone) return toast(context, 'Not sent. Everything is still waiting here.');
    if (sent > 0) Confetti.burst(context);
    toast(context, 'Sent $sent of ${list.length}.${problems.isEmpty ? '' : ' ${problems.first}'}', error: sent == 0);
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
                      Text('Tap Send to send. You get 5 seconds to undo. Open a draft to edit it first.', style: T.small),
                      const SizedBox(height: 18),
                      SectionTitle('Waiting for you${approvals.isEmpty ? '' : ' · ${approvals.length}'}',
                          trailing: approvals.length < 2 ? null : Pressable(onTap: () => _sendAll(approvals), child: Pill('Send all (${approvals.length})', color: C.primary, filled: true))),
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
                              onTap: () => pushDepth(context, (_) => ReplyScreen(replyId: '${r['id']}')),
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
          Expanded(child: PrimaryButton(label: email ? 'Edit & send' : 'Send', busy: _busy.contains(key), onTap: () => _primary(a))),
        ]),
      ]),
    );
  }
}
