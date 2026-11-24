import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../jobchat/job_chat_screen.dart';
import '../jobchat/job_context.dart';
import '../resume/studio_screen.dart';

/// Job Match Radar: today's best-fit jobs from the feed and career portals, ranked by the verified-profile match.
class RadarScreen extends StatefulWidget {
  const RadarScreen({super.key});
  @override
  State<RadarScreen> createState() => _RadarScreenState();
}

class _RadarScreenState extends State<RadarScreen> {
  final _r = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/radar', query: {'top': 20})));
  String? _open;
  bool _sending = false;

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

  Future<void> _digest() async {
    setState(() => _sending = true);
    final r = await guarded(context, () async => asMap(await Session.I.api.post('/radar/digest/test')));
    if (!mounted) return;
    setState(() => _sending = false);
    if (r == null) return;
    final sent = (r['sent'] as num?)?.toInt() ?? 0;
    if (sent > 0) {
      toast(context, 'Sent your top $sent matches to ${r['to']}');
    } else {
      toast(context, '${r['error'] ?? r['reason'] ?? r['skipped'] ?? 'Nothing to send yet'}', error: r['error'] != null);
    }
  }

  /// Career-portal jobs let the backend load the full description; feed jobs only have a summary, so the chat starts from
  /// what the radar knows (skills, location) and the user can paste the full post for a deeper check.
  void _ask(Map<String, dynamic> j) {
    final matched = (j['matched_skills'] as List? ?? const []).map((e) => '$e').toList();
    final missing = (j['missing_skills'] as List? ?? const []).map((e) => '$e').toList();
    final careers = j['origin'] == 'careers';
    final text = '${j['title']} at ${j['company']}. ${j['location'] ?? ''}\n'
        '${matched.isEmpty ? '' : 'Skills asked for that you have: ${matched.join(', ')}.\n'}'
        '${missing.isEmpty ? '' : 'Skills asked for that you do not list: ${missing.join(', ')}.\n'}';
    openJobChat(
      context,
      job: JobContext(
        title: '${j['title']}',
        company: '${j['company']}',
        location: j['location'] as String?,
        link: '${j['url'] ?? ''}'.isEmpty ? null : '${j['url']}',
        text: text,
        careerJobId: careers ? '${j['id']}' : null,
        score: j['score'] as num?,
      ),
    );
  }

  Color _fit(num s) => s >= 75 ? C.good : s >= 55 ? C.warn : C.muted;

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Match Radar',
        subtitle: 'Your best-fit jobs today',
        child: ResourceView<Map<String, dynamic>>(
          resource: _r,
          builder: (context, d) {
            final items = asList(d['items']);
            return RefreshIndicatorList(onRefresh: _r.load, children: [
              if (items.isEmpty)
                const SizedBox(height: 360, child: EmptyState(icon: Icons.radar_rounded, title: 'No matches yet', body: 'Open Jobs for you or Career portals once so Saige can score jobs against your profile.'))
              else ...[
                Text('${d['total'] ?? items.length} jobs scored against your verified profile. Nothing is applied for you.', style: T.small),
                const SizedBox(height: 12),
                for (var i = 0; i < items.length; i++) Stagger(index: i % 8, child: _card(items[i])),
                const SizedBox(height: 8),
                PrimaryButton(label: 'Email me the top 5', icon: Icons.mail_rounded, ghost: true, busy: _sending, onTap: _digest),
              ],
            ]);
          },
        ),
      );

  Widget _card(Map<String, dynamic> j) {
    final id = '${j['id']}';
    final open = _open == id;
    final score = (j['score'] as num?) ?? 0;
    final color = _fit(score);
    final matched = (j['matched_skills'] as List? ?? const []).map((e) => '$e').toList();
    final missing = (j['missing_skills'] as List? ?? const []).map((e) => '$e').toList();
    final reasons = (j['reasons'] as List? ?? const []).map((e) => '$e').toList();
    final url = '${j['url'] ?? ''}';
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: GlassCard(
        onTap: () {
          tick();
          setState(() => _open = open ? null : id);
        },
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              width: 54,
              height: 54,
              alignment: Alignment.center,
              decoration: BoxDecoration(shape: BoxShape.circle, color: color.withValues(alpha: 0.15)),
              child: Text('${score.round()}', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800, color: color)),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${j['title']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: T.h2.copyWith(fontSize: 16.5)),
                const SizedBox(height: 2),
                Text([j['company'], j['location']].where((e) => e != null && '$e'.isNotEmpty).join('  ·  '), maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
              ]),
            ),
            Icon(open ? Icons.expand_less_rounded : Icons.expand_more_rounded, color: C.muted),
          ]),
          if (!open && reasons.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(reasons.first, maxLines: 2, overflow: TextOverflow.ellipsis, style: T.small),
          ],
          AnimatedSize(
            duration: const Duration(milliseconds: 280),
            curve: Curves.easeOutCubic,
            alignment: Alignment.topCenter,
            child: !open
                ? const SizedBox(width: double.infinity)
                : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const SizedBox(height: 14),
                    if (reasons.isNotEmpty) ...[Text('WHY YOU FIT', style: T.label), const SizedBox(height: 8), for (final r in reasons) Dot(r, C.good)],
                    if (matched.isNotEmpty) Wrap(spacing: 6, runSpacing: 6, children: [for (final s in matched) Pill(s, color: C.good, filled: true)]),
                    if (missing.isNotEmpty) ...[
                      const SizedBox(height: 14),
                      Text('MISSING SKILLS', style: T.label),
                      const SizedBox(height: 8),
                      Wrap(spacing: 6, runSpacing: 6, children: [for (final s in missing) Pill(s, color: C.warn)]),
                    ],
                    const SizedBox(height: 16),
                    PrimaryButton(label: 'Ask Saige about this job', icon: Icons.auto_awesome_rounded, onTap: () => _ask(j)),
                    const SizedBox(height: 10),
                    Row(children: [
                      Expanded(
                        child: PrimaryButton(
                          label: 'ATS resume',
                          icon: Icons.description_rounded,
                          onTap: () => pushDepth(context, (_) => StudioScreen(initialTitle: '${j['title']}', initialCompany: '${j['company']}')),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(child: PrimaryButton(label: 'Open job', icon: Icons.open_in_new_rounded, ghost: true, onTap: url.isEmpty ? null : () => openUrl(context, url))),
                    ]),
                  ]),
          ),
        ]),
      ),
    );
  }
}
