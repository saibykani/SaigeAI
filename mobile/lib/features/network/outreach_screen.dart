import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

Color _statusColor(String s) => switch (s) { 'replied' => C.good, 'sent' => C.blue, 'approved' => C.violet, 'draft' => C.warn, 'bounced' => C.bad, _ => C.muted };

/// Outreach drafts and sent messages, plus follow-ups that are due. Sending always needs your approval
/// and respects the daily cap (10/day by default).
class OutreachScreen extends StatefulWidget {
  const OutreachScreen({super.key, this.initial = 'draft'});
  final String initial;
  @override
  State<OutreachScreen> createState() => _OutreachScreenState();
}

class _OutreachScreenState extends State<OutreachScreen> {
  late String _tab = widget.initial;
  final _list = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/outreach')));
  final _stats = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/outreach/stats')));

  @override
  void initState() {
    super.initState();
    _list.load();
    _stats.load();
  }

  @override
  void dispose() {
    _list.dispose();
    _stats.dispose();
    super.dispose();
  }

  Future<void> _reload() => Future.wait([_list.load(), _stats.load()]);

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Outreach',
        subtitle: 'Drafts, sent messages and follow-ups',
        child: Column(children: [
          ChipRow(options: const ['draft', 'sent', 'followups'], labels: const {'draft': 'Drafts', 'sent': 'Sent', 'followups': 'Follow-ups'}, value: _tab, onChanged: (v) => setState(() => _tab = v)),
          const SizedBox(height: 8),
          Expanded(
            child: ListenableBuilder(
              listenable: Listenable.merge([_list, _stats]),
              builder: (context, _) {
                if (_list.data == null || _stats.data == null) {
                  if (_list.error != null) return ErrorState(error: _list.error!, onRetry: _reload);
                  return const LoadingState();
                }
                final stats = _stats.data!;
                if (_tab == 'followups') return _followups(asList(stats['followups_due']), asList(_list.data));
                final all = _list.data!;
                final l = all.where((o) => _tab == 'draft' ? (o['status'] == 'draft' || o['status'] == 'approved') : !(o['status'] == 'draft' || o['status'] == 'approved' || o['status'] == 'cancelled')).toList();
                if (l.isEmpty) return EmptyState(icon: _tab == 'draft' ? Icons.drafts_rounded : Icons.outbox_rounded, title: _tab == 'draft' ? 'No drafts' : 'Nothing sent yet', body: _tab == 'draft' ? 'Open a recruiter and draft a truthful message. You approve it before anything is sent.' : 'Messages you approve and send appear here with their outcome.');
                return RefreshIndicatorList(onRefresh: _reload, children: [
                  Padding(padding: const EdgeInsets.only(bottom: 10), child: Text('${stats['sent_today']} of ${stats['daily_limit']} sent today  ·  ${stats['remaining_today']} left', style: T.small)),
                  for (final (i, o) in l.indexed)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Stagger(
                        index: i % 8,
                        child: GlassCard(
                          radius: R.md,
                          padding: const EdgeInsets.all(14),
                          onTap: () => showSheet<void>(context, (c) => OutreachDetail(item: o, remaining: (stats['remaining_today'] as num?)?.toInt(), canSend: stats['can_send_from_saige'] == true, onChanged: _reload)),
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Row(children: [Expanded(child: Text('${o['contact_name'] ?? 'Contact'}  ·  ${o['company'] ?? ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600))), Pill(prettyStatus('${o['status']}'), color: _statusColor('${o['status']}'), filled: true)]),
                            const SizedBox(height: 4),
                            Text('${o['subject']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
                            const SizedBox(height: 6),
                            Text('${o['body']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: T.small.copyWith(color: C.text.withValues(alpha: 0.7))),
                          ]),
                        ),
                      ),
                    ),
                ]);
              },
            ),
          ),
        ]),
      );

  Widget _followups(List<Map<String, dynamic>> due, List<Map<String, dynamic>> all) {
    if (due.isEmpty) return const EmptyState(icon: Icons.mark_email_read_rounded, title: 'No follow-ups due', body: 'Saige schedules polite follow-ups after you send, and stops if they reply.');
    return RefreshIndicatorList(onRefresh: _reload, children: [
      for (final (i, f) in due.indexed)
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Stagger(
            index: i % 8,
            child: GlassCard(
              radius: R.md,
              padding: const EdgeInsets.all(14),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${f['contact_name'] ?? 'Contact'}  ·  ${f['company'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w600)),
                Text('Follow-up ${f['sequence']}  ·  ${f['subject']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
                const SizedBox(height: 12),
                Row(children: [
                  Expanded(
                    child: PrimaryButton(
                      label: 'Draft follow-up',
                      onTap: () async {
                        final r = await guarded(context, () => Session.I.api.post('/outreach/draft', data: {'contact_id': f['contact_id'], 'kind': 'followup', 'parent_id': f['outreach_id']}));
                        if (r == null || !mounted) return;
                        success();
                        await _reload();
                        if (mounted) await showSheet<void>(context, (c) => OutreachDetail(item: asMap(r), canSend: _stats.data?['can_send_from_saige'] == true, remaining: (_stats.data?['remaining_today'] as num?)?.toInt(), onChanged: _reload));
                      },
                    ),
                  ),
                  const SizedBox(width: 8),
                  PrimaryButton(
                    label: 'Done',
                    ghost: true,
                    expand: false,
                    onTap: () async {
                      await guarded(context, () => Session.I.api.post('/outreach/followups/${f['followup_id']}/done'));
                      await _reload();
                    },
                  ),
                ]),
              ]),
            ),
          ),
        ),
    ]);
  }
}

/// Edit, approve and send one message. Sending is an explicit approval and is blocked at the daily cap.
class OutreachDetail extends StatefulWidget {
  const OutreachDetail({super.key, required this.item, this.remaining, this.canSend = true, required this.onChanged});
  final Map<String, dynamic> item;
  final int? remaining;
  final bool canSend;
  final VoidCallback onChanged;
  @override
  State<OutreachDetail> createState() => _OutreachDetailState();
}

class _OutreachDetailState extends State<OutreachDetail> {
  late final _subject = TextEditingController(text: '${widget.item['subject']}');
  late final _body = TextEditingController(text: '${widget.item['body']}');
  bool _busy = false;

  Map<String, dynamic> get o => widget.item;
  bool get _editable => o['status'] == 'draft' || o['status'] == 'approved';
  bool get _linkedin => o['kind'] == 'linkedin_note' || o['channel_hint'] == 'linkedin';

  @override
  void dispose() {
    _subject.dispose();
    _body.dispose();
    super.dispose();
  }

  Future<bool> _save() async {
    final r = await guarded(context, () => Session.I.api.put('/outreach/${o['id']}', data: {'subject': _subject.text.trim(), 'body': _body.text.trim()}));
    return r != null;
  }

  Future<void> _send() async {
    final lim = widget.remaining;
    if (lim != null && lim <= 0) {
      toast(context, 'Daily outreach limit reached. Try again tomorrow.', error: true);
      return;
    }
    final ok = await confirmSheet(context, title: 'Approve and send?', body: 'This sends the email from your Gmail to ${o['contact_name'] ?? 'the contact'}. It passed the truth guard against your verified profile. ${lim != null ? '$lim sends left today.' : ''}', action: 'Approve and send');
    if (!ok || !mounted) return;
    setState(() => _busy = true);
    if (!await _save()) {
      setState(() => _busy = false);
      return;
    }
    if (!mounted) return;
    final r = await guarded(context, () => Session.I.api.post('/outreach/${o['id']}/send', query: {'approve': true}), ok: 'Sent');
    if (!mounted) return;
    setState(() => _busy = false);
    if (r != null) {
      success();
      widget.onChanged();
      Navigator.pop(context);
    }
  }

  Future<void> _markSent() async {
    final r = await guarded(context, () => Session.I.api.post('/outreach/${o['id']}/mark-sent'), ok: 'Marked as sent');
    if (r != null && mounted) {
      widget.onChanged();
      Navigator.pop(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final v = o['validation'] == null ? null : asMap(o['validation']);
    final blocked = v != null && v['status'] != 'PASSED';
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [Expanded(child: Text('${o['contact_name'] ?? 'Message'}', style: T.h2)), Pill(prettyStatus('${o['status']}'), color: _statusColor('${o['status']}'), filled: true)]),
      const SizedBox(height: 4),
      Text('${o['company'] ?? ''}  ·  ${_linkedin ? 'LinkedIn note' : 'Email'}', style: T.small),
      const SizedBox(height: 14),
      if (blocked) ...[
        GlassCard(color: C.bad.withValues(alpha: 0.1), radius: R.md, padding: const EdgeInsets.all(12), child: Text('The truth guard flagged claims that are not in your verified profile. Edit the message before sending.', style: TextStyle(color: C.bad, fontSize: 13))),
        const SizedBox(height: 12),
      ] else if (v != null) ...[
        Row(children: [Icon(Icons.verified_rounded, size: 18, color: C.good), const SizedBox(width: 6), Text('Truth guard passed', style: TextStyle(color: C.good, fontWeight: FontWeight.w600, fontSize: 13))]),
        const SizedBox(height: 12),
      ],
      if (!_linkedin) ...[LabeledField(label: 'Subject', controller: _subject), const SizedBox(height: 12)],
      _editable ? LabeledField(label: 'Message', controller: _body, lines: 9) : SelectableText('${o['body']}', style: T.body),
      const SizedBox(height: 16),
      if (_editable) ...[
        if (_linkedin) ...[
          PrimaryButton(label: 'Copy note', icon: Icons.copy_rounded, onTap: () => copyText(context, _body.text, done: 'Copied. Paste it in LinkedIn.')),
          const SizedBox(height: 8),
          PrimaryButton(label: 'I sent it on LinkedIn', ghost: true, onTap: _markSent),
        ] else ...[
          PrimaryButton(label: widget.canSend ? 'Approve and send' : 'Connect Gmail on web to send', icon: Icons.send_rounded, busy: _busy, onTap: blocked ? null : (widget.canSend ? _send : () => openUrl(context, webUrl('/integrations'))) ),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(child: PrimaryButton(label: 'Save edits', ghost: true, onTap: () async {
              if (await _save() && mounted) {
                toast(this.context, 'Saved');
                widget.onChanged();
              }
            })),
            const SizedBox(width: 8),
            if (o['gmail_compose'] != null) Expanded(child: PrimaryButton(label: 'Open in Gmail', ghost: true, onTap: () => openUrl(context, '${o['gmail_compose']}'))),
          ]),
        ],
      ] else if (o['status'] == 'sent') ...[
        PrimaryButton(label: 'They replied', ghost: true, onTap: () async {
          await guarded(context, () => Session.I.api.post('/outreach/${o['id']}/outcome/replied'), ok: 'Marked replied');
          widget.onChanged();
          if (mounted) Navigator.pop(this.context);
        }),
      ],
    ]);
  }
}
