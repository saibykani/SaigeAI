import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/pulse.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/ui.dart';
import '../inbox/inbox_screen.dart';
import '../jobchat/email_draft.dart';
import 'reply_logic.dart';

/// Reply assistant: the recruiter's message and the reply Saige drafted from your verified profile (auto-reply drafts).
/// You edit it and tap Send (the approval); a 5 second Undo bar comes first, and the
/// normal send path applies the truth guard, pauses and daily caps. "Not now" leaves the draft waiting in Drafts & approvals.
class ReplyScreen extends StatefulWidget {
  const ReplyScreen({super.key, required this.replyId});

  /// The sent-email id carried by the pulse notification (`reply:<id>`).
  final String replyId;
  @override
  State<ReplyScreen> createState() => _ReplyScreenState();
}

class _Loaded {
  _Loaded(this.reply, this.message, this.draft, this.validation);
  final Map<String, dynamic> reply;
  final Map<String, dynamic>? message; // the recruiter's email (inbox record), when it can be found
  final EmailDraft? draft;
  final Map<String, dynamic> validation;
}

class _ReplyScreenState extends State<ReplyScreen> {
  late final _r = Resource<_Loaded>(_load);

  @override
  void initState() {
    super.initState();
    _r.load();
  }

  @override
  void dispose() {
    _r.dispose();
    super.dispose();
  }

  Future<_Loaded> _load() async {
    final api = Session.I.api;
    final since = DateTime.now().toUtc().subtract(const Duration(days: 30)).toIso8601String();
    final pulse = asMap(await api.get('/mobile/pulse', query: {'since': since}));
    final reply = asList(pulse['replies']).where((e) => '${e['id']}' == widget.replyId).firstOrNull;
    if (reply == null) return _Loaded({}, null, null, {});
    Map<String, dynamic>? message;
    EmailDraft? draft;
    Map<String, dynamic> validation = {};
    try {
      final emails = asList(await api.get('/emails', query: {'limit': 150}));
      message = emails.where((e) => '${e['id']}' == '${reply['email_id']}').firstOrNull;
    } catch (_) {}
    try {
      final drafts = asList(await api.get('/outreach', query: {'status': 'draft'}));
      final m = matchReplyDraft(drafts, reply);
      if (m != null) {
        draft = EmailDraft.fromOutreach(m);
        validation = asMap(m['validation']);
      }
    } catch (_) {}
    return _Loaded(reply, message, draft, validation);
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Reply',
        subtitle: 'Review, edit, then send',
        child: ResourceView<_Loaded>(
          resource: _r,
          builder: (context, d) {
            if (d.reply.isEmpty) {
              return const EmptyState(icon: Icons.mark_email_read_rounded, title: 'Reply not found', body: 'It may be older than 30 days or already handled. Open Drafts and approvals to see what is waiting.');
            }
            final r = d.reply;
            final m = d.message;
            final bounced = r['status'] == 'bounced';
            final who = '${r['company'] ?? r['to'] ?? 'Recruiter'}';
            final text = '${m?['snippet'] ?? r['snippet'] ?? ''}'.trim();
            return RefreshIndicatorList(onRefresh: _r.load, children: [
              GlassCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    IconBadge(bounced ? Icons.report_gmailerrorred_rounded : Icons.mark_email_unread_rounded, bounced ? C.bad : C.good),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(who, style: T.h2.copyWith(fontSize: 17)),
                        Text('${m?['sender'] ?? r['to'] ?? ''}  ·  ${timeAgo('${r['at']}')}', style: T.small, maxLines: 1, overflow: TextOverflow.ellipsis),
                      ]),
                    ),
                    if ('${r['category'] ?? ''}'.isNotEmpty) Pill(prettyStatus('${r['category']}'), color: C.primary, filled: true),
                  ]),
                  const SizedBox(height: 14),
                  Text('${m?['subject'] ?? r['subject'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 6),
                  Text(bounced ? 'Your email to ${r['to'] ?? 'this contact'} could not be delivered.' : (text.isEmpty ? 'No preview available.' : text), style: T.body),
                  const SizedBox(height: 12),
                  Pressable(
                    onTap: () => pushDepth(context, (_) => const InboxScreen()),
                    child: Text('Read the full email in Inbox', style: TextStyle(color: C.primary, fontWeight: FontWeight.w700)),
                  ),
                ]),
              ),
              const SectionTitle('Your reply'),
              if (bounced)
                GlassCard(child: Text('The address bounced, so there is nothing to reply to. Check the recruiter\'s email in Recruiters.', style: T.small))
              else if (d.draft == null)
                GlassCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('No reply draft yet', style: T.h2.copyWith(fontSize: 16)),
                    const SizedBox(height: 6),
                    Text(
                        'Saige drafts a reply when a recruiter emails you and Auto-reply is on. This one has no draft waiting. Reply from Inbox for now.',
                        style: T.small),
                    const SizedBox(height: 14),
                    PrimaryButton(label: 'Open Inbox', icon: Icons.inbox_rounded, ghost: true, onTap: () => pushDepth(context, (_) => const InboxScreen())),
                  ]),
                )
              else ...[
                if (d.validation['status'] != null && d.validation['status'] != 'PASSED')
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: GlassCard(color: C.bad.withValues(alpha: 0.12), child: Text('This draft mentions something Saige could not verify in your profile. Edit it before sending.', style: T.small.copyWith(color: C.text))),
                  ),
                GlassCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    EmailDraftCard(
                      draft: d.draft!,
                      onSent: () {
                        Pulse.I.check();
                        Navigator.of(context).maybePop();
                      },
                      onDiscard: null,
                    ),
                    const SizedBox(height: 10),
                    PrimaryButton(label: 'Not now', ghost: true, onTap: () => Navigator.of(context).maybePop()),
                  ]),
                ),
              ],
            ]);
          },
        ),
      );
}
