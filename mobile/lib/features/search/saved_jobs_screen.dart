import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../jobs/job_detail_screen.dart';

/// Every job in your account with filters: status, search text, minimum match, sort.
class SavedJobsScreen extends StatefulWidget {
  const SavedJobsScreen({super.key});
  @override
  State<SavedJobsScreen> createState() => _SavedJobsScreenState();
}

class _SavedJobsScreenState extends State<SavedJobsScreen> {
  final _q = TextEditingController();
  String _status = 'all';
  String _sort = 'score';
  String _min = '0';
  late final Resource<Map<String, dynamic>> _r = Resource(() async => asMap(await Session.I.api.get('/jobs', query: {
        'limit': 100,
        'sort': _sort,
        if (_status != 'all') 'status': _status,
        if (_q.text.trim().isNotEmpty) 'q': _q.text.trim(),
        if (_min != '0') 'min_score': int.parse(_min),
      })));

  @override
  void initState() {
    super.initState();
    _r.load();
  }

  @override
  void dispose() {
    _q.dispose();
    _r.dispose();
    super.dispose();
  }

  void _reload() {
    _r.data = null;
    _r.load();
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Saved jobs',
        subtitle: 'Filter everything you tracked',
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 10),
            child: TextField(
              controller: _q,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _reload(),
              decoration: InputDecoration(hintText: 'Search title or company', prefixIcon: Icon(Icons.search_rounded, color: C.muted), contentPadding: EdgeInsets.symmetric(vertical: 14)),
            ),
          ),
          ChipRow(options: const ['all', 'new', 'saved', 'shortlisted', 'archived', 'rejected'], labels: const {'all': 'All', 'new': 'New', 'saved': 'Saved', 'shortlisted': 'Shortlisted', 'archived': 'Archived', 'rejected': 'Rejected'}, value: _status, onChanged: (v) {
            _status = v;
            _reload();
          }),
          const SizedBox(height: 8),
          ChipRow(options: const ['0', '50', '65', '80'], labels: const {'0': 'Any match', '50': '50%+', '65': '65%+', '80': '80%+'}, value: _min, onChanged: (v) {
            _min = v;
            _reload();
          }),
          const SizedBox(height: 8),
          ChipRow(options: const ['score', 'recent'], labels: const {'score': 'Best match', 'recent': 'Most recent'}, value: _sort, onChanged: (v) {
            _sort = v;
            _reload();
          }),
          const SizedBox(height: 6),
          Expanded(
            child: ResourceView<Map<String, dynamic>>(
              resource: _r,
              builder: (context, d) {
                final l = asList(d['items']);
                if (l.isEmpty) return const EmptyState(icon: Icons.bookmark_border_rounded, title: 'No jobs here', body: 'Change the filters, or find new jobs and save them.');
                return RefreshIndicatorList(onRefresh: _r.load, children: [
                  for (final (i, j) in l.indexed)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Stagger(
                        index: i % 8,
                        child: GlassCard(
                          radius: R.md,
                          padding: const EdgeInsets.all(14),
                          onTap: () => pushDepth(context, (_) => JobDetailScreen(jobId: '${j['id']}', heroTag: 'sj-${j['id']}')),
                          child: Row(children: [
                            Expanded(
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text('${j['title']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
                                Text('${j['company']}${j['location'] != null ? '  ·  ${j['location']}' : ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
                                const SizedBox(height: 8),
                                Pill(prettyStatus('${j['status'] ?? ''}'), color: C.muted),
                              ]),
                            ),
                            const SizedBox(width: 12),
                            if (j['score'] != null)
                              DotRing(size: 50, dots: 16, progress: (j['score'] as num) / 100, color: scoreColor(j['score'] as num), child: Text('${j['score']}', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: scoreColor(j['score'] as num)))),
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
}

/// A bouncing list with the Saige logo pull-to-refresh.
class RefreshIndicatorList extends StatelessWidget {
  const RefreshIndicatorList({super.key, required this.onRefresh, required this.children});
  final Future<void> Function() onRefresh;
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => LogoRefreshView(onRefresh: onRefresh, slivers: [
        SliverPadding(padding: const EdgeInsets.fromLTRB(20, 4, 20, 0), sliver: SliverList.list(children: children)),
      ]);
}
