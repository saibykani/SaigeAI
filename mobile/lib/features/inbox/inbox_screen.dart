import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api.dart';
import '../../core/config.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

const _cats = [
  'all',
  'Interview Invitation',
  'Offer',
  'Recruiter Outreach',
  'Recruiter Reply',
  'Application Confirmation',
  'Assessment',
  'Coding Test',
  'Interview Reschedule',
  'Rejection',
  'Follow-up',
  'Other',
];

Color _catColor(String c) => switch (c) {
      'Offer' || 'Interview Invitation' => C.good,
      'Rejection' => C.bad,
      'Assessment' || 'Coding Test' || 'Interview Reschedule' => C.warn,
      'Recruiter Outreach' || 'Recruiter Reply' => C.primary,
      _ => C.muted,
    };

/// Job mail from Gmail, sorted by what it means. Saige only reads; it never sends from here.
class InboxScreen extends StatefulWidget {
  const InboxScreen({super.key});
  @override
  State<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends State<InboxScreen> {
  String _cat = 'all';
  bool _syncing = false;
  final _status = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/integrations')));
  late final Resource<List<Map<String, dynamic>>> _mail = Resource(() async => asList(await Session.I.api.get('/emails', query: {'limit': 150, if (_cat != 'all') 'category': _cat})));

  @override
  void initState() {
    super.initState();
    _status.load();
    _mail.load();
  }

  @override
  void dispose() {
    _status.dispose();
    _mail.dispose();
    super.dispose();
  }

  Future<void> _sync() async {
    setState(() => _syncing = true);
    try {
      final r = asMap(await Session.I.api.post('/emails/sync'));
      success();
      await Future.wait([_status.load(), _mail.load()]);
      if (mounted) toast(context, 'Inbox synced${r['imported'] != null ? ': ${r['imported']} new' : ''}');
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _syncing = false);
  }

  void _setCat(String c) {
    _cat = c;
    _mail.data = null;
    _mail.load();
    setState(() {});
  }

  Future<void> _openWeb() async {
    final base = AppConfig.baseUrl.replaceAll(RegExp(r'/api/?$'), '');
    await launchUrl(Uri.parse('$base/integrations'), mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Inbox',
        subtitle: 'Gmail, read-only',
        child: ListenableBuilder(
          listenable: _status,
          builder: (context, _) {
            final s = _status.data;
            if (s == null) return _status.error != null ? ErrorState(error: _status.error!, onRetry: _status.load) : const LoadingState();
            final g = asMap(s['gmail']);
            if (g['connected'] != true) {
              return EmptyState(
                icon: Icons.mail_outline_rounded,
                title: 'Connect Gmail',
                body: 'Saige reads job mail only (read-only) and sorts interviews, offers and rejections for you. Google asks for consent on the web.',
                action: 'Open Integrations',
                onAction: _openWeb,
              );
            }
            return Column(children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 4, 20, 12),
                child: GlassCard(
                  radius: R.md,
                  padding: const EdgeInsets.all(14),
                  child: Row(children: [
                    Icon(Icons.mark_email_read_rounded, color: C.good),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${g['email'] ?? 'Gmail'}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                        Text(g['last_sync_at'] == null ? 'Not synced yet' : 'Synced ${timeAgo('${g['last_sync_at']}')}', style: T.small),
                      ]),
                    ),
                    SizedBox(width: 108, child: PrimaryButton(label: 'Sync', icon: Icons.sync_rounded, busy: _syncing, onTap: _sync)),
                  ]),
                ),
              ),
              ChipRow(options: _cats, labels: const {'all': 'All mail'}, value: _cat, onChanged: _setCat),
              const SizedBox(height: 8),
              Expanded(
                child: ResourceView<List<Map<String, dynamic>>>(
                  resource: _mail,
                  builder: (context, l) {
                    if (l.isEmpty) {
                      return EmptyState(icon: Icons.inbox_outlined, title: _cat == 'all' ? 'No job mail yet' : 'Nothing in $_cat', body: 'Tap Sync to pull in the latest from Gmail.', action: 'Sync now', onAction: _sync);
                    }
                    return LogoRefreshView(onRefresh: () async {
                      await _mail.load();
                    }, slivers: [
                      SliverPadding(
                        padding: const EdgeInsets.fromLTRB(20, 4, 20, 0),
                        sliver: SliverList.builder(
                          itemCount: l.length,
                          itemBuilder: (context, i) => Padding(padding: const EdgeInsets.only(bottom: 10), child: Stagger(index: i % 8, child: _MailCard(l[i]))),
                        ),
                      ),
                    ]);
                  },
                ),
              ),
            ]);
          },
        ),
      );
}

class _MailCard extends StatefulWidget {
  const _MailCard(this.m);
  final Map<String, dynamic> m;
  @override
  State<_MailCard> createState() => _MailCardState();
}

class _MailCardState extends State<_MailCard> {
  bool _open = false;
  @override
  Widget build(BuildContext context) {
    final m = widget.m;
    final cat = '${m['category'] ?? 'Other'}';
    final ex = asMap(m['extracted']);
    final sender = '${m['sender'] ?? ''}'.replaceAll(RegExp(r'<.*>'), '').trim();
    return GlassCard(
      radius: R.md,
      padding: const EdgeInsets.all(14),
      onTap: () => setState(() => _open = !_open),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(width: 9, height: 9, decoration: BoxDecoration(color: _catColor(cat), shape: BoxShape.circle)),
          const SizedBox(width: 8),
          Expanded(child: Text(sender.isEmpty ? '${m['sender']}' : sender, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600))),
          Text(timeAgo('${m['received_at']}'), style: T.small),
        ]),
        const SizedBox(height: 6),
        Text('${m['subject']}', maxLines: _open ? 4 : 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 14.5)),
        AnimatedSize(
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOutCubic,
          alignment: Alignment.topCenter,
          child: _open
              ? Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${m['snippet'] ?? ''}', style: T.small),
                    if (ex.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Wrap(spacing: 6, runSpacing: 6, children: [
                        for (final k in ['company', 'role', 'interview_date', 'interview_time']) if ('${ex[k] ?? ''}'.isNotEmpty) Pill('${ex[k]}'),
                      ]),
                    ],
                  ]),
                )
              : const SizedBox(width: double.infinity),
        ),
        const SizedBox(height: 10),
        Pill(cat, color: _catColor(cat), filled: true),
      ]),
    );
  }
}
