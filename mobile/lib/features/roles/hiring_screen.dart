import 'package:material_ui/material_ui.dart';

import '../shell/app_drawer.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../search/saved_jobs_screen.dart' show RefreshIndicatorList;

/// Recruiter experience: post jobs, find opted-in candidates ranked by skill match, send interest,
/// and see answers. Candidates only share contact details after they accept.
class HiringScreen extends StatefulWidget {
  const HiringScreen({super.key, this.embedded = false});
  final bool embedded;
  @override
  State<HiringScreen> createState() => _HiringScreenState();
}

class _HiringScreenState extends State<HiringScreen> {
  String _tab = 'jobs';
  final _jobs = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/hiring/jobs')));
  final _reqs = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/hiring/requests')));
  String? _jobId;
  final _q = TextEditingController();
  late final Resource<List<Map<String, dynamic>>> _cands = Resource(() async => asList(await Session.I.api.get('/hiring/candidates', query: {if (_jobId != null) 'job_id': _jobId, if (_q.text.trim().isNotEmpty) 'q': _q.text.trim()})));

  @override
  void initState() {
    super.initState();
    _jobs.load();
    _reqs.load();
    _cands.load();
  }

  @override
  void dispose() {
    _jobs.dispose();
    _reqs.dispose();
    _cands.dispose();
    _q.dispose();
    super.dispose();
  }

  Future<void> _postJob() async {
    final ok = await showSheet<bool>(context, (c) => const _JobForm());
    if (ok == true) _jobs.load();
  }

  Future<void> _interest(Map<String, dynamic> cand) async {
    final msg = TextEditingController();
    final go = await showSheet<bool>(
      context,
      (c) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('Send interest to ${cand['name']}', style: T.h2),
        const SizedBox(height: 6),
        Text('They see your name and message. Their contact details stay private until they accept.', style: T.small),
        const SizedBox(height: 14),
        LabeledField(label: 'Message (optional)', controller: msg, lines: 4),
        const SizedBox(height: 16),
        PrimaryButton(label: 'Send interest', icon: Icons.send_rounded, onTap: () => Navigator.pop(c, true)),
      ]),
    );
    final text = msg.text.trim();
    msg.dispose();
    if (go != true || !mounted) return;
    final r = await guarded(context, () => Session.I.api.post('/hiring/requests', data: {'candidate_id': cand['id'], if (_jobId != null) 'job_id': _jobId, 'message': text}), ok: 'Interest sent');
    if (r != null) {
      success();
      _reqs.load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final body = Column(children: [
      ChipRow(options: const ['jobs', 'candidates', 'requests'], labels: const {'jobs': 'My jobs', 'candidates': 'Candidates', 'requests': 'Sent'}, value: _tab, onChanged: (v) => setState(() => _tab = v)),
      const SizedBox(height: 8),
      Expanded(child: switch (_tab) { 'jobs' => _jobsTab(), 'candidates' => _candTab(), _ => _reqTab() }),
    ]);
    if (widget.embedded) {
      return SafeArea(
        bottom: false,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(padding: const EdgeInsets.fromLTRB(20, 12, 20, 12), child: Row(children: [const MenuButton(), Text('Hiring', style: T.display)])),
          Expanded(child: body),
        ]),
      );
    }
    return FeatureScaffold(title: 'Hiring', subtitle: 'Post jobs and find candidates', child: body);
  }

  Widget _jobsTab() => Stack(children: [
        ResourceView<List<Map<String, dynamic>>>(
          resource: _jobs,
          builder: (context, l) {
            if (l.isEmpty) return EmptyState(icon: Icons.work_outline_rounded, title: 'No jobs posted', body: 'Post a role. Saige ranks opted-in candidates by how many required skills they verifiably have.', action: 'Post a job', onAction: _postJob);
            return RefreshIndicatorList(onRefresh: _jobs.load, children: [
              for (final (i, j) in l.indexed)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Stagger(
                    index: i % 8,
                    child: GlassCard(
                      radius: R.md,
                      padding: const EdgeInsets.all(14),
                      onTap: () {
                        setState(() {
                          _jobId = '${j['id']}';
                          _tab = 'candidates';
                        });
                        _cands.load();
                      },
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Row(children: [
                          Expanded(child: Text('${j['title']}', style: const TextStyle(fontWeight: FontWeight.w700))),
                          Pressable(
                            onTap: () async {
                              if (!await confirmSheet(this.context, title: 'Delete this job?', body: 'Candidate requests already sent stay.', action: 'Delete', danger: true)) return;
                              if (!mounted) return;
                              await guarded(this.context, () => Session.I.api.request('DELETE', '/hiring/jobs/${j['id']}'));
                              _jobs.load();
                            },
                            child: Icon(Icons.delete_outline_rounded, color: C.muted),
                          ),
                        ]),
                        Text('${j['company']}${(j['location'] as String?)?.isNotEmpty == true ? '  ·  ${j['location']}' : ''}', style: T.small),
                        const SizedBox(height: 8),
                        Wrap(spacing: 6, runSpacing: 6, children: [for (final s in (j['skills'] as List? ?? []).take(8)) Pill('$s', color: C.blue)]),
                        const SizedBox(height: 8),
                        Text('Tap to see ranked candidates', style: T.small.copyWith(color: C.primary)),
                      ]),
                    ),
                  ),
                ),
              const SizedBox(height: 70),
            ]);
          },
        ),
        Positioned(right: 20, bottom: 24, child: PillFab(label: 'Post job', icon: Icons.add_rounded, onTap: _postJob)),
      ]);

  Widget _candTab() => Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
          child: TextField(
            controller: _q,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _cands.load(),
            decoration: InputDecoration(hintText: 'Skills or role, comma separated', prefixIcon: Icon(Icons.search_rounded, color: C.muted), contentPadding: const EdgeInsets.symmetric(vertical: 14)),
          ),
        ),
        ListenableBuilder(
          listenable: _jobs,
          builder: (context, _) {
            final l = _jobs.data ?? [];
            if (l.isEmpty) return const SizedBox.shrink();
            return ChipRow(
              options: ['all', ...l.map((j) => '${j['id']}')],
              labels: {'all': 'Any job', for (final j in l) '${j['id']}': '${j['title']}'},
              value: _jobId ?? 'all',
              onChanged: (v) {
                setState(() => _jobId = v == 'all' ? null : v);
                _cands.load();
              },
            );
          },
        ),
        const SizedBox(height: 6),
        Expanded(
          child: ResourceView<List<Map<String, dynamic>>>(
            resource: _cands,
            builder: (context, l) {
              if (l.isEmpty) return const EmptyState(icon: Icons.person_search_rounded, title: 'No candidates yet', body: 'Only job seekers who turned on "Let recruiters find me" appear here, ranked by skill match.');
              return RefreshIndicatorList(onRefresh: _cands.load, children: [
                for (final (i, c) in l.indexed)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Stagger(
                      index: i % 8,
                      child: GlassCard(
                        radius: R.md,
                        padding: const EdgeInsets.all(14),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Row(children: [
                            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${c['name']}', style: const TextStyle(fontWeight: FontWeight.w700)), Text('${c['role'] ?? ''}${c['years'] != null ? '  ·  ${num0(c['years'])} yrs' : ''}${c['location'] != null ? '  ·  ${c['location']}' : ''}', style: T.small)])),
                            if (c['match'] != null) Pill('${c['match']}% match', color: scoreColor(c['match'] as num), filled: true),
                          ]),
                          const SizedBox(height: 8),
                          Wrap(spacing: 6, runSpacing: 6, children: [
                            for (final s in (c['matched_skills'] as List? ?? [])) Pill('$s', color: C.good, filled: true),
                            for (final s in (c['skills'] as List? ?? []).where((s) => !((c['matched_skills'] as List?) ?? []).contains(s)).take(5)) Pill('$s'),
                          ]),
                          const SizedBox(height: 12),
                          Row(children: [
                            Expanded(child: PrimaryButton(label: 'Send interest', onTap: () => _interest(c))),
                            if (c['portfolio_url'] != null) ...[const SizedBox(width: 8), PrimaryButton(label: 'Portfolio', ghost: true, expand: false, onTap: () => openUrl(context, webUrl('${c['portfolio_url']}')))],
                          ]),
                        ]),
                      ),
                    ),
                  ),
              ]);
            },
          ),
        ),
      ]);

  Widget _reqTab() => ResourceView<List<Map<String, dynamic>>>(
        resource: _reqs,
        builder: (context, l) {
          if (l.isEmpty) return const EmptyState(icon: Icons.outbox_rounded, title: 'No requests sent', body: 'Send interest to a candidate. Their answer shows up here, with contact details only if they accept.');
          return RefreshIndicatorList(onRefresh: _reqs.load, children: [
            for (final (i, r) in l.indexed)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Stagger(
                  index: i % 8,
                  child: GlassCard(
                    radius: R.md,
                    padding: const EdgeInsets.all(14),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [Expanded(child: Text('${r['candidate_name']}', style: const TextStyle(fontWeight: FontWeight.w700))), Pill(prettyStatus('${r['status']}'), color: r['status'] == 'accepted' ? C.good : (r['status'] == 'declined' ? C.bad : C.warn), filled: true)]),
                      if (r['job_title'] != null) Text('${r['job_title']}', style: T.small),
                      if (r['contact'] != null) ...[
                        const SizedBox(height: 10),
                        if (asMap(r['contact'])['email'] != null) Row(children: [Icon(Icons.mail_outline_rounded, size: 18, color: C.muted), const SizedBox(width: 8), Expanded(child: SelectableText('${asMap(r['contact'])['email']}'))]),
                        if (asMap(r['contact'])['phone'] != null) Padding(padding: const EdgeInsets.only(top: 4), child: Row(children: [Icon(Icons.phone_outlined, size: 18, color: C.muted), const SizedBox(width: 8), Expanded(child: SelectableText('${asMap(r['contact'])['phone']}'))])),
                      ],
                    ]),
                  ),
                ),
              ),
          ]);
        },
      );
}

class _JobForm extends StatefulWidget {
  const _JobForm();
  @override
  State<_JobForm> createState() => _JobFormState();
}

class _JobFormState extends State<_JobForm> {
  final _title = TextEditingController();
  final _company = TextEditingController();
  final _loc = TextEditingController();
  final _desc = TextEditingController();
  final _skills = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    for (final c in [_title, _company, _loc, _desc, _skills]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    if (_title.text.trim().length < 2 || _company.text.trim().isEmpty) {
      toast(context, 'Add a title and a company.', error: true);
      return;
    }
    setState(() => _busy = true);
    final r = await guarded(
      context,
      () => Session.I.api.post('/hiring/jobs', data: {'title': _title.text.trim(), 'company': _company.text.trim(), 'location': _loc.text.trim(), 'description': _desc.text.trim(), 'skills': _skills.text.split(RegExp(r'[,;]')).map((s) => s.trim()).where((s) => s.isNotEmpty).toList()}),
      ok: 'Job posted',
    );
    if (!mounted) return;
    if (r != null) {
      success();
      Navigator.pop(context, true);
    } else {
      setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('Post a job', style: T.h2),
        const SizedBox(height: 14),
        LabeledField(label: 'Title', controller: _title),
        const SizedBox(height: 12),
        LabeledField(label: 'Company', controller: _company),
        const SizedBox(height: 12),
        LabeledField(label: 'Location', controller: _loc),
        const SizedBox(height: 12),
        LabeledField(label: 'Required skills (comma separated)', controller: _skills, hint: 'Python, SQL, AWS'),
        const SizedBox(height: 12),
        LabeledField(label: 'Description', controller: _desc, lines: 5),
        const SizedBox(height: 18),
        PrimaryButton(label: 'Post job', busy: _busy, onTap: _save),
      ]);
}
