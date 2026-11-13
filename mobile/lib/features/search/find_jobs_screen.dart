import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import 'open_job_card.dart';

/// Search every enabled job API for a role and location, scored against the verified profile.
class FindJobsScreen extends StatefulWidget {
  const FindJobsScreen({super.key});
  @override
  State<FindJobsScreen> createState() => _FindJobsScreenState();
}

class _FindJobsScreenState extends State<FindJobsScreen> {
  final _q = TextEditingController();
  final _loc = TextEditingController();
  List<Map<String, dynamic>>? _results;
  Map<String, dynamic> _meta = {};
  bool _busy = false;
  ApiException? _error;
  String _sort = 'match';

  @override
  void dispose() {
    _q.dispose();
    _loc.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = asMap(await Session.I.api.post('/jobs/discover', data: {
        if (_q.text.trim().isNotEmpty) 'query': _q.text.trim(),
        if (_loc.text.trim().isNotEmpty) 'location': _loc.text.trim(),
      }));
      thump();
      if (mounted) {
        setState(() {
          _results = asList(r['results']);
          _meta = r;
        });
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<bool> _save(Map<String, dynamic> j) async {
    try {
      await Session.I.api.post('/jobs/discover/save', data: {
        'items': [
          {
            'source': '${j['source'] ?? 'discover'}',
            'source_job_id': j['source_job_id'],
            'title': j['title'],
            'company': '${j['company'] ?? ''}',
            'location': j['location'],
            'remote': j['remote'],
            'url': j['url'],
            'description': '${j['description'] ?? ''}',
            'salary_min': j['salary_min'],
            'salary_max': j['salary_max'],
          }
        ],
        'prepare_applications': false,
      });
      success();
      if (mounted) toast(context, 'Saved to your jobs. Nothing is applied until you approve.');
      return true;
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
      return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final list = [...?_results];
    if (_sort == 'new') list.sort((a, b) => '${b['posted'] ?? ''}'.compareTo('${a['posted'] ?? ''}'));
    return FeatureScaffold(
      title: 'Find jobs',
      subtitle: 'Live from job APIs, scored on your profile',
      child: ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 120),
        children: [
          Stagger(index: 0, child: LabeledField(label: 'Role', controller: _q, hint: 'Blank uses your target role', onSubmitted: (_) => _search())),
          const SizedBox(height: 12),
          Stagger(index: 1, child: LabeledField(label: 'Location', controller: _loc, hint: 'City, country or Remote', onSubmitted: (_) => _search())),
          const SizedBox(height: 16),
          PrimaryButton(label: 'Search', icon: Icons.search_rounded, busy: _busy, onTap: _search),
          if (_busy) const Busy(label: 'Asking every job board'),
          if (_error != null && !_busy) ErrorState(error: _error!, onRetry: _search),
          if (_results != null && !_busy) ...[
            const SizedBox(height: 18),
            Row(children: [
              Expanded(child: Text('${list.length} jobs for "${_meta['query'] ?? ''}"', style: T.h2)),
            ]),
            const SizedBox(height: 10),
            ChipRow(
              padding: 0,
              options: const ['match', 'new'],
              labels: const {'match': 'Best match', 'new': 'Newest'},
              value: _sort,
              onChanged: (v) => setState(() => _sort = v),
            ),
            const SizedBox(height: 14),
            if (list.isEmpty)
              const SizedBox(height: 320, child: EmptyState(icon: Icons.search_off_rounded, title: 'Nothing found', body: 'Try a broader role or another location.'))
            else
              for (final (i, j) in list.take(60).indexed)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Stagger(index: i < 8 ? i : 0, child: OpenJobCard(job: j, saved: j['saved_job_id'] != null, onSave: () => _save(j))),
                ),
          ],
          if (_results == null && !_busy && _error == null)
            const SizedBox(height: 280, child: EmptyState(icon: Icons.travel_explore_rounded, title: 'Search the open web of jobs', body: 'Leave the role blank to use your target role. Results never leave your account.')),
        ],
      ),
    );
  }
}
