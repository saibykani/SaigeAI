import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/ui.dart';
import 'debrief_screen.dart';
import 'interview_day_screen.dart';

class InterviewsScreen extends StatefulWidget {
  const InterviewsScreen({super.key});
  @override
  State<InterviewsScreen> createState() => _InterviewsScreenState();
}

class _InterviewsScreenState extends State<InterviewsScreen> {
  final _upcoming = Resource<List<Map<String, dynamic>>>(() async => asList(asMap(await Session.I.api.get('/interviews'))['upcoming']));
  final _mails = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/emails/interviews')));
  bool _syncing = false;

  @override
  void initState() {
    super.initState();
    _upcoming.load();
    _mails.load();
  }

  @override
  void dispose() {
    _upcoming.dispose();
    _mails.dispose();
    super.dispose();
  }

  Future<void> _sync() async {
    setState(() => _syncing = true);
    try {
      await Session.I.api.post('/emails/sync-interviews');
      await Future.wait([_mails.load(), _upcoming.load()]);
      if (mounted) toast(context, 'Inbox scanned for interview mail');
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _syncing = false);
  }

  Future<void> _refresh() => Future.wait([_upcoming.load(), _mails.load()]);

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        body: SafeArea(
          child: Stack(children: [
            ListenableBuilder(
              listenable: Listenable.merge([_upcoming, _mails]),
              builder: (context, _) {
                final up = _upcoming.data ?? const [];
                final mails = _mails.data ?? const [];
                final loading = _upcoming.data == null && _mails.data == null && _upcoming.error == null;
                if (loading) return const LoadingState();
                return LogoRefreshView(onRefresh: _refresh, slivers: [
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 64, 20, 0),
                    sliver: SliverList.list(children: [
                      Text('Interviews', style: T.display),
                      const SizedBox(height: 14),
                      PrimaryButton(label: 'Scan inbox for interview mail', icon: Icons.mark_email_unread_outlined, busy: _syncing, ghost: true, onTap: _sync),
                      if (_upcoming.error != null && up.isEmpty && mails.isEmpty) ...[const SizedBox(height: 20), ErrorState(error: _upcoming.error!, onRetry: _refresh)],
                      const SectionTitle('Upcoming'),
                      if (up.isEmpty) GlassCard(child: Text('Nothing scheduled yet.', style: T.small)),
                      for (final (i, x) in up.indexed) Padding(padding: const EdgeInsets.only(bottom: 10), child: Stagger(index: i, child: _Upcoming(i: x))),
                      const SectionTitle('From your inbox'),
                      if (mails.isEmpty) GlassCard(child: Text('No interview emails found. Connect Gmail on the web app, then scan.', style: T.small)),
                      for (final (i, m) in mails.indexed) Padding(padding: const EdgeInsets.only(bottom: 10), child: Stagger(index: i, child: _Mail(m: m))),
                    ]),
                  ),
                ]);
              },
            ),
            Positioned(left: 12, top: 8, child: Pressable(onTap: () => Navigator.of(context).maybePop(), child: Container(width: 46, height: 46, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: const Icon(Icons.arrow_back_rounded)))),
            if (_syncing) Positioned(right: 20, top: 16, child: DotRing(size: 30, dots: 12)),
          ]),
        ),
      );
}

Future<void> _open(String? url) async {
  if (url == null || url.isEmpty) return;
  final u = Uri.tryParse(url);
  if (u != null) await launchUrl(u, mode: LaunchMode.externalApplication);
}

class _Upcoming extends StatelessWidget {
  const _Upcoming({required this.i});
  final Map<String, dynamic> i;
  @override
  Widget build(BuildContext context) {
    final d = DateTime.tryParse('${i['scheduled_at']}')?.toLocal();
    final url = i['meeting_url'] as String?;
    return GlassCard(
      radius: R.md,
      padding: const EdgeInsets.all(16),
      child: Row(children: [
        Container(
          width: 56,
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(color: C.primarySoft, borderRadius: BorderRadius.circular(R.sm)),
          child: Column(children: [Text(d == null ? '--' : '${d.day}', style: T.h1), Text(d == null ? '' : _mon[d.month - 1], style: T.label)]),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${i['company'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
            Text('${i['role'] ?? ''}  ·  ${i['round'] ?? 'Interview'}', style: T.small, maxLines: 1, overflow: TextOverflow.ellipsis),
            if (d != null) Text('${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}', style: T.small),
          ]),
        ),
        Column(spacing: 8, children: [
          Pressable(onTap: () => pushDepth(context, (_) => InterviewDayScreen(interviewId: '${i['id']}')), child: Container(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10), decoration: BoxDecoration(color: C.primarySoft, borderRadius: BorderRadius.circular(99)), child: Text('Prepare', style: TextStyle(color: C.primary, fontWeight: FontWeight.w700)))),
          if (d != null && d.isBefore(DateTime.now())) Pressable(onTap: () => pushDepth(context, (_) => DebriefScreen(interview: i)), child: Container(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10), decoration: BoxDecoration(color: C.primarySoft, borderRadius: BorderRadius.circular(99)), child: Text('Debrief', style: TextStyle(color: C.primary, fontWeight: FontWeight.w700)))),
          if (url != null && url.isNotEmpty) Pressable(onTap: () => _open(url), child: Container(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10), decoration: BoxDecoration(color: C.primary, borderRadius: BorderRadius.circular(99)), child: Text('Join', style: TextStyle(color: C.onPrimary, fontWeight: FontWeight.w700)))),
        ]),
      ]),
    );
  }
}

const _mon = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

class _Mail extends StatelessWidget {
  const _Mail({required this.m});
  final Map<String, dynamic> m;
  @override
  Widget build(BuildContext context) {
    final x = asMap(m['extracted']);
    final link = (x['meeting_url'] ?? x['link'] ?? x['url']) as String?;
    return GlassCard(
      radius: R.md,
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Pill(prettyStatus('${m['category']}'), color: C.primary, filled: true), const Spacer(), Text(timeAgo('${m['received_at']}'), style: T.small)]),
        const SizedBox(height: 10),
        Text('${m['subject']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        Text('${m['sender']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
        if (x['interview_date'] != null || x['round'] != null) ...[const SizedBox(height: 8), Text([if (x['round'] != null) '${x['round']}', if (x['interview_date'] != null) '${x['interview_date']}'].join('  ·  '), style: TextStyle(color: C.warn, fontSize: 13))],
        const SizedBox(height: 10),
        Row(spacing: 8, children: [
          Pressable(onTap: () => pushDepth(context, (_) => InterviewDayScreen(emailId: '${m['id']}')), child: Pill('Prepare', color: C.primary, filled: true)),
          if (link != null && link.isNotEmpty) Pressable(onTap: () => _open(link), child: Pill('Join link', color: C.good, filled: true)),
        ]),
      ]),
    );
  }
}
