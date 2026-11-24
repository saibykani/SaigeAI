import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../jobchat/email_draft.dart';
import '../jobchat/job_chat_screen.dart';
import '../jobchat/job_context.dart';
import 'quick_apply_logic.dart';
import 'quick_apply_store.dart';

/// Applications prepared by Quick apply, waiting for the user. Review opens the editable email with the resume attached;
/// Send asks for confirmation first. Jobs with no email get "Open job" and a resume download instead.
class ReadyTrayScreen extends StatefulWidget {
  const ReadyTrayScreen({super.key});
  @override
  State<ReadyTrayScreen> createState() => _ReadyTrayScreenState();
}

class _ReadyTrayScreenState extends State<ReadyTrayScreen> {
  final _store = QuickApplyStore.I;
  final _busy = <String>{};

  @override
  void initState() {
    super.initState();
    _store.load();
  }

  Future<void> _review(ReadyItem it) async {
    final d = EmailDraft(
      kind: 'apply',
      to: it.to,
      subject: it.subject,
      body: it.body,
      resumeId: it.resumeId,
      from: it.from,
      company: it.company,
      suggestions: it.suggestions,
    );
    var discarded = false;
    final done = await openDraftSheet(
      context,
      d,
      title: '${it.title} at ${it.company}',
      discard: () async {
        final ok = await confirmSheet(context, title: 'Discard this application?', body: 'The prepared resume and email for ${it.company} are removed from this list.', action: 'Discard', danger: true);
        discarded = ok;
        return ok;
      },
    );
    if (done) {
      await _store.remove(it.jobId, discarded: discarded && !d.sent);
      if (mounted && d.sent) toast(context, 'Application sent to ${d.to.trim()}');
    }
  }

  /// Sends every ready email (address + resume present) under one Undo window. Each goes through the normal send path, so
  /// the daily cap, pauses and the truth guard apply per item; what could not be sent stays in the tray with the reason.
  Future<void> _sendAll(List<ReadyItem> ready) async {
    var sent = 0;
    final problems = <String>[];
    final out = await sendWithUndo(context, label: 'Sending ${ready.length} ${ready.length == 1 ? 'application' : 'applications'}...', send: () async {
      for (final it in ready) {
        final d = EmailDraft(kind: 'apply', to: it.to, subject: it.subject, body: it.body, resumeId: it.resumeId, from: it.from, company: it.company);
        final err = await sendDraft(d);
        if (err == null) {
          sent++;
          await _store.remove(it.jobId);
        } else {
          problems.add('${it.company}: $err');
          if (err.contains('limit') || err.contains('paused') || err.contains('Connect Gmail')) break; // the rest would fail the same way
        }
      }
      return null;
    });
    if (!mounted) return;
    if (out.undone) return toast(context, 'Not sent. Everything is still here.');
    if (sent > 0) success();
    toast(context, 'Sent $sent of ${ready.length}.${problems.isEmpty ? '' : ' ${problems.first}'}', error: sent == 0);
  }

  Future<void> _discard(ReadyItem it) async {
    final ok = await confirmSheet(context, title: 'Discard this application?', body: 'The prepared resume and email for ${it.company} are removed from this list.', action: 'Discard', danger: true);
    if (ok) await _store.remove(it.jobId, discarded: true);
  }

  void _finishInChat(ReadyItem it) => openJobChat(
        context,
        job: JobContext(
          title: it.title,
          company: it.company,
          location: it.location,
          link: it.url.isEmpty ? null : it.url,
          text: it.jdText,
          careerJobId: it.careerJobId,
          score: it.score,
          emails: it.suggestions,
        ),
      );

  Future<void> _download(ReadyItem it) async {
    setState(() => _busy.add(it.jobId));
    await downloadAndShare(context, '/studio/resumes/${it.resumeId}/download', query: {'format': 'pdf'}, fallbackName: 'resume.pdf');
    if (mounted) setState(() => _busy.remove(it.jobId));
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Ready to send',
        subtitle: 'Review each one, then send',
        child: ValueListenableBuilder<List<ReadyItem>>(
          valueListenable: _store.tray,
          builder: (context, items, _) {
            if (items.isEmpty) {
              return const EmptyState(icon: Icons.outbox_rounded, title: 'Nothing waiting', body: 'Swipe right on a match in Quick apply and the resume and email show up here for your review.');
            }
            return ListView(physics: const BouncingScrollPhysics(), padding: const EdgeInsets.fromLTRB(20, 4, 20, 120), children: [
              Text('Nothing here has been sent. Tap Send on one, or Send all. You get 5 seconds to undo.', style: T.small),
              const SizedBox(height: 12),
              if (items.where((e) => e.state == 'ready' && e.hasResume).length > 1) ...[
                PrimaryButton(label: 'Send all (${items.where((e) => e.state == 'ready' && e.hasResume).length})', icon: Icons.send_rounded, onTap: () => _sendAll([for (final e in items) if (e.state == 'ready' && e.hasResume) e])),
                const SizedBox(height: 12),
              ],
              for (final (i, it) in items.indexed) Stagger(index: i % 8, child: _card(it)),
            ]);
          },
        ),
      );

  Widget _card(ReadyItem it) {
    final state = it.state;
    final (label, color) = switch (state) {
      'ready' => ('Ready', C.good),
      'needs_details' => ('Needs details', C.warn),
      _ => ('No email found', C.warn),
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(it.title, maxLines: 2, overflow: TextOverflow.ellipsis, style: T.h2.copyWith(fontSize: 17)),
                Text(it.company, style: T.small),
              ]),
            ),
            Pill(label, color: color, filled: true),
          ]),
          const SizedBox(height: 10),
          Text(
            switch (state) {
              'ready' => 'To ${it.to}${it.hasResume ? '  ·  resume attached' : ''}',
              'needs_details' => 'Saige needs a few facts for this post before it can write the email. They are saved to your profile.',
              _ => 'This post lists no application email. Open the job to apply there, or download the tailored resume.',
            },
            style: T.small,
          ),
          const SizedBox(height: 14),
          if (state == 'needs_details')
            PrimaryButton(label: 'Finish in Saige chat', icon: Icons.auto_awesome_rounded, onTap: () => _finishInChat(it))
          else if (state == 'ready')
            PrimaryButton(label: 'Review and send', icon: Icons.send_rounded, onTap: () => _review(it))
          else ...[
            Row(children: [
              Expanded(child: PrimaryButton(label: 'Open job', icon: Icons.open_in_new_rounded, onTap: it.url.isEmpty ? null : () => openUrl(context, it.url))),
              const SizedBox(width: 10),
              Expanded(child: PrimaryButton(label: 'Resume', icon: Icons.download_rounded, ghost: true, busy: _busy.contains(it.jobId), onTap: it.hasResume ? () => _download(it) : null)),
            ]),
            const SizedBox(height: 10),
            PrimaryButton(label: 'Add an email and review', icon: Icons.edit_rounded, ghost: true, onTap: it.hasResume ? () => _review(it) : null),
          ],
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: Pressable(
              onTap: () => _discard(it),
              child: Padding(padding: const EdgeInsets.all(8), child: Text('Discard', style: TextStyle(color: C.bad, fontWeight: FontWeight.w700))),
            ),
          ),
        ]),
      ),
    );
  }
}
