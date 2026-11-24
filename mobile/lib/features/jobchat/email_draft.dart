import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/confetti.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

/// An email the user can edit and send. Two backends:
/// - `outreach`: a recruiter outreach draft (`/outreach/{id}`), sent with `/outreach/{id}/send?approve=true`.
/// - `apply`: an application email built by ATS Studio, sent with `/studio/apply/send` with the resume attached.
/// Nothing leaves the phone until the user taps Send and confirms.
class EmailDraft {
  EmailDraft({required this.kind, this.id, required this.to, required this.subject, required this.body, this.resumeId, this.from, this.company, this.attachResume = false, this.suggestions = const []});

  final String kind; // 'outreach' | 'apply'
  final String? id; // outreach id
  String to;
  String subject;
  String body;
  final String? resumeId;
  final String? from; // the connected Gmail address, when the backend told us
  final String? company;
  final bool attachResume;
  final List<String> suggestions; // other addresses found in the job post
  bool sent = false;

  bool get isOutreach => kind == 'outreach';
  bool get resumeAttached => isOutreach ? attachResume : resumeId != null;

  factory EmailDraft.fromOutreach(Map<String, dynamic> o, {String? to}) => EmailDraft(
        kind: 'outreach',
        id: '${o['id']}',
        to: to ?? _mailFrom('${o['mailto'] ?? ''}'),
        subject: '${o['subject'] ?? ''}',
        body: '${o['body'] ?? ''}',
        company: o['company'] as String?,
        attachResume: o['attach_resume'] == true,
      );

  factory EmailDraft.fromApply(Map<String, dynamic> r, {String? company}) => EmailDraft(
        kind: 'apply',
        to: '${r['to'] ?? ''}',
        subject: '${r['subject'] ?? ''}',
        body: '${r['body'] ?? ''}',
        resumeId: '${r['id']}',
        from: r['gmail'] as String?,
        company: company,
        suggestions: [for (final e in (r['emails_found'] as List? ?? const [])) '$e'],
      );
}

String _mailFrom(String mailto) {
  final m = RegExp(r'^mailto:([^?]+)').firstMatch(mailto);
  return m == null ? '' : Uri.decodeComponent(m.group(1)!);
}

final _emailOk = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
bool validEmail(String s) => _emailOk.hasMatch(s.trim());

/// Friendly text for the ways a send can be refused: caps, pauses, no Gmail, truth guard, blocked company.
String sendErrorText(Object e) {
  if (e is! ApiException) return 'Could not send. Try again.';
  final m = e.message;
  final low = m.toLowerCase();
  switch (e.status) {
    case 423:
      return 'Sending is paused. Resume it in Settings, Agent, then try again.';
    case 429:
      if (low.contains('company') || low.contains('this week')) return m; // "already contacted 3 people at X this week"
      return m.toLowerCase().contains('limit') ? m : 'You hit today\'s sending limit. Try again tomorrow.';
    case 409:
      if (low.contains('gmail')) return 'Connect Gmail first: Settings, Integrations, Gmail (App Password). Then send again.';
      return m;
    case 422:
      return 'Saige blocked this: the text claims something that is not in your verified profile. Edit it and try again.';
    case 502:
      return 'Gmail would not send it: $m';
  }
  return e.offline ? 'You are offline. Connect and try again.' : m;
}

/// "Send to x@y.com from your Gmail?" confirmation. Returns true when the user confirms.
Future<bool> confirmSend(BuildContext context, EmailDraft d) => confirmSheet(
      context,
      title: 'Send to ${d.to.trim()}?',
      body: 'From ${d.from ?? 'your Gmail'}.'
          '${d.resumeAttached ? ' Your resume is attached.' : ''}\n\nSubject: ${d.subject.trim()}\n\nThis goes out as soon as you confirm.',
      action: 'Send now',
    );

/// Sends [d] after the user confirmed. Returns null on success or the friendly error text.
Future<String?> sendDraft(EmailDraft d) async {
  final api = Session.I.api;
  try {
    if (d.isOutreach) {
      await api.put('/outreach/${d.id}', data: {'subject': d.subject.trim(), 'body': d.body.trim()});
      await api.post('/outreach/${d.id}/send', query: {'approve': true});
    } else {
      await api.post('/studio/apply/send', data: {
        'resume_id': d.resumeId,
        'to': d.to.trim(),
        'subject': d.subject.trim(),
        'body': d.body.trim(),
        'format': 'pdf',
      });
    }
    d.sent = true;
    return null;
  } catch (e) {
    return sendErrorText(e);
  }
}

/// Editable email with Copy and Send. Used in the job chat and the Drafts screen.
class EmailDraftCard extends StatefulWidget {
  const EmailDraftCard({super.key, required this.draft, this.onSent, this.onDiscard, this.compact = false});
  final EmailDraft draft;
  final VoidCallback? onSent;
  final VoidCallback? onDiscard;
  final bool compact;

  @override
  State<EmailDraftCard> createState() => _EmailDraftCardState();
}

class _EmailDraftCardState extends State<EmailDraftCard> {
  late final _to = TextEditingController(text: widget.draft.to);
  late final _subject = TextEditingController(text: widget.draft.subject);
  late final _body = TextEditingController(text: widget.draft.body);
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _to.dispose();
    _subject.dispose();
    _body.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final d = widget.draft;
    d
      ..to = _to.text
      ..subject = _subject.text
      ..body = _body.text;
    if (!validEmail(d.to)) return toast(context, 'Add a valid recipient email first.', error: true);
    if (d.subject.trim().length < 3) return toast(context, 'Add a subject first.', error: true);
    if (d.body.trim().length < 20) return toast(context, 'The message is too short to send.', error: true);
    FocusScope.of(context).unfocus();
    if (!await confirmSend(context, d)) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final err = await sendDraft(d);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _error = err;
    });
    if (err == null) {
      Confetti.burst(context);
      toast(context, 'Sent to ${d.to.trim()}');
      widget.onSent?.call();
    } else {
      thump();
      toast(context, err, error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.draft;
    if (d.sent) {
      return Row(children: [
        Icon(Icons.check_circle_rounded, color: C.good),
        const SizedBox(width: 10),
        Expanded(child: Text('Sent to ${d.to}${d.resumeAttached ? ' with your resume' : ''}.', style: T.body)),
      ]);
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (d.isOutreach)
        _readOnlyTo(d)
      else ...[
        LabeledField(label: 'To', controller: _to, hint: 'hr@company.com', keyboard: TextInputType.emailAddress),
        if (d.suggestions.length > 1) ...[
          const SizedBox(height: 8),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final s in d.suggestions) Pressable(onTap: () => setState(() => _to.text = s), child: Pill(s, color: C.text)),
          ]),
        ],
      ],
      const SizedBox(height: 12),
      LabeledField(label: 'Subject', controller: _subject),
      const SizedBox(height: 12),
      LabeledField(label: 'Message', controller: _body, lines: widget.compact ? 8 : 12),
      const SizedBox(height: 10),
      Row(children: [
        Icon(d.resumeAttached ? Icons.attach_file_rounded : Icons.info_outline_rounded, size: 16, color: C.muted),
        const SizedBox(width: 6),
        Expanded(child: Text(d.resumeAttached ? 'Your resume (PDF) is attached.' : 'No resume attached to this message.', style: T.small)),
      ]),
      if (_error != null) ...[
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: C.bad.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(R.sm)),
          child: Text(_error!, style: T.small.copyWith(color: C.text)),
        ),
      ],
      const SizedBox(height: 14),
      Row(children: [
        Pressable(
          onTap: () => copyText(context, 'Subject: ${_subject.text}\n\n${_body.text}', done: 'Email copied'),
          child: Container(width: 56, height: 56, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: Icon(Icons.copy_rounded, color: C.text, size: 20)),
        ),
        const SizedBox(width: 10),
        if (widget.onDiscard != null) ...[
          Pressable(
            onTap: widget.onDiscard,
            child: Container(width: 56, height: 56, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: Icon(Icons.delete_outline_rounded, color: C.bad, size: 21)),
          ),
          const SizedBox(width: 10),
        ],
        Expanded(child: PrimaryButton(label: 'Send', icon: Icons.send_rounded, busy: _busy, onTap: _send)),
      ]),
    ]);
  }

  Widget _readOnlyTo(EmailDraft d) => Row(children: [
        Text('TO  ', style: T.label),
        Expanded(child: SelectableText(d.to.isEmpty ? 'No email on this contact' : d.to, style: T.body.copyWith(fontWeight: FontWeight.w600))),
      ]);
}

/// Loads one unsent outreach draft with its recipient (the Approvals list only carries a preview).
Future<EmailDraft?> loadOutreachDraft(String id) async {
  final list = asList(await Session.I.api.get('/outreach', query: {'status': 'draft'}));
  for (final o in list) {
    if ('${o['id']}' == id) return EmailDraft.fromOutreach(o, to: _contactEmail(o));
  }
  return null;
}

String _contactEmail(Map<String, dynamic> o) => _mailFrom('${o['mailto'] ?? ''}');

/// Opens [d] in a bottom sheet (edit, send, discard). Returns true if it was sent or discarded.
Future<bool> openDraftSheet(BuildContext context, EmailDraft d, {Future<bool> Function()? discard, String title = 'Review and send'}) async {
  final done = await showSheet<bool>(
    context,
    (c) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(title, style: T.h2),
      const SizedBox(height: 4),
      Text('Nothing is sent until you tap Send and confirm.', style: T.small),
      const SizedBox(height: 16),
      EmailDraftCard(
        draft: d,
        onSent: () => Navigator.pop(c, true),
        onDiscard: discard == null
            ? null
            : () async {
                if (await discard() && c.mounted) Navigator.pop(c, true);
              },
      ),
    ]),
  );
  return done == true;
}
