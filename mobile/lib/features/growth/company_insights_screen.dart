import 'package:material_ui/material_ui.dart';

import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/motion.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

/// Your own reply and interview rates per company and per source, with a plain tip for each.
class CompanyInsightsScreen extends StatefulWidget {
  const CompanyInsightsScreen({super.key});
  @override
  State<CompanyInsightsScreen> createState() => _CompanyInsightsScreenState();
}

class _CompanyInsightsScreenState extends State<CompanyInsightsScreen> {
  String _days = 'all';
  late final Resource<Map<String, dynamic>> _r = Resource(() async => asMap(await Session.I.api.get('/analytics/companies', query: {if (_days != 'all') 'days': int.parse(_days)})));
  String? _open;

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

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Company insights',
        subtitle: 'What your applications really did',
        child: Column(children: [
          const SizedBox(height: 6),
          ChipRow(options: const ['all', '30', '90', '180'], labels: const {'all': 'All time', '30': '30 days', '90': '90 days', '180': '180 days'}, value: _days, onChanged: (v) {
            setState(() => _days = v);
            _r.data = null;
            _r.load();
          }),
          Expanded(
            child: ResourceView<Map<String, dynamic>>(
              resource: _r,
              builder: (context, d) {
                final o = asMap(d['overall']);
                final cos = asList(d['companies']);
                final srcs = asList(d['sources']);
                if (((o['applied'] as num?) ?? 0) == 0) return const EmptyState(icon: Icons.insights_rounded, title: 'No applications yet', body: 'Once you apply, you will see which companies and sources reply to you, and how fast.');
                final best = d['best_source'] == null ? null : asMap(d['best_source']);
                final worst = d['worst_source'] == null ? null : asMap(d['worst_source']);
                return LogoRefreshView(onRefresh: _r.load, slivers: [
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
                    sliver: SliverList.list(children: [
                      Stagger(
                        index: 0,
                        child: GlassCard(
                          child: Row(children: [
                            ScoreRing(score: (o['reply_rate'] as num?) ?? 0, size: 104, label: 'REPLY'),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text('${o['applied']} applied', style: T.h2),
                                const SizedBox(height: 4),
                                Text('${o['replied']} replied  ·  ${o['interviews']} interviews  ·  ${o['offers']} offers', style: T.small),
                                const SizedBox(height: 4),
                                Text(o['median_response_days'] == null ? 'Response time: not enough replies' : 'Median reply: ${num0(o['median_response_days'])} days', style: T.small),
                              ]),
                            ),
                          ]),
                        ),
                      ),
                      if (best != null || worst != null) ...[
                        const SizedBox(height: 12),
                        Row(children: [
                          if (best != null) Expanded(child: _Source('Best source', best, C.good)),
                          if (best != null && worst != null) const SizedBox(width: 12),
                          if (worst != null) Expanded(child: _Source('Weakest source', worst, C.warn)),
                        ]),
                      ],
                      if (d['enough_data'] != true) Padding(padding: EdgeInsets.only(top: 12), child: Text('Fewer than a handful of applications so far: treat these numbers as early signals.', style: T.small)),
                      const SectionTitle('By company'),
                      for (final (i, c) in cos.indexed)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: Stagger(
                            index: i % 8,
                            child: GlassCard(
                              radius: R.md,
                              padding: const EdgeInsets.all(14),
                              onTap: () => setState(() => _open = _open == '${c['label']}' ? null : '${c['label']}'),
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Row(children: [
                                  Expanded(child: Text('${c['label']}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15.5))),
                                  Text('${c['applied']} applied', style: T.small),
                                ]),
                                const SizedBox(height: 10),
                                BarFill(value: ((c['reply_rate'] as num?) ?? 0) / 100, color: scoreColor((c['reply_rate'] as num?) ?? 0)),
                                const SizedBox(height: 6),
                                Text('Reply ${c['reply_rate'] ?? '--'}%  ·  Interview ${c['interview_rate'] ?? '--'}%', style: T.small),
                                AnimatedSize(
                                  duration: const Duration(milliseconds: 280),
                                  curve: Curves.easeOutCubic,
                                  alignment: Alignment.topCenter,
                                  child: _open != '${c['label']}'
                                      ? const SizedBox(width: double.infinity)
                                      : Padding(
                                          padding: const EdgeInsets.only(top: 10),
                                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                            Wrap(spacing: 6, runSpacing: 6, children: [
                                              Pill('${c['replied']} replied'),
                                              Pill('${c['interviews']} interviews', color: C.good),
                                              if (((c['rejections'] as num?) ?? 0) > 0) Pill('${c['rejections']} rejected', color: C.bad),
                                              if (((c['ghosted'] as num?) ?? 0) > 0) Pill('${c['ghosted']} silent', color: C.warn),
                                              if (((c['outreach_sent'] as num?) ?? 0) > 0) Pill('${c['outreach_replied']}/${c['outreach_sent']} outreach replied'),
                                              if (c['median_response_days'] != null) Pill('median ${num0(c['median_response_days'])}d'),
                                            ]),
                                            const SizedBox(height: 10),
                                            Text('${c['tip'] ?? ''}', style: const TextStyle(fontSize: 13.5, height: 1.4)),
                                          ]),
                                        ),
                                ),
                              ]),
                            ),
                          ),
                        ),
                      const SectionTitle('By source'),
                      for (final (i, s) in srcs.indexed)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: Stagger(
                            index: i % 8,
                            child: GlassCard(
                              radius: R.md,
                              padding: const EdgeInsets.all(14),
                              child: Row(children: [
                                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${s['label']}', style: const TextStyle(fontWeight: FontWeight.w600)), Text('${s['applied']} applied  ·  ${s['interviews']} interviews', style: T.small)])),
                                Text(s['reply_rate'] == null ? '--' : '${s['reply_rate']}%', style: T.h2.copyWith(color: scoreColor(s['reply_rate'] as num?))),
                              ]),
                            ),
                          ),
                        ),
                    ]),
                  ),
                ]);
              },
            ),
          ),
        ]),
      );
}

class _Source extends StatelessWidget {
  const _Source(this.title, this.s, this.color);
  final String title;
  final Map<String, dynamic> s;
  final Color color;
  @override
  Widget build(BuildContext context) => GlassCard(
        radius: R.md,
        padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title.toUpperCase(), style: T.label.copyWith(color: color)),
          const SizedBox(height: 6),
          Text('${s['label']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
          Text('${s['reply_rate']}% reply', style: T.small),
        ]),
      );
}
