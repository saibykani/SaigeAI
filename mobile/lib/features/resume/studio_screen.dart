import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

/// ATS Studio on the phone: paste a JD (or open from a saved job), see how you fit, generate an ATS resume
/// from the verified profile only, then download or share it as PDF or DOCX.
class StudioScreen extends StatefulWidget {
  const StudioScreen({super.key, this.initialJd, this.jobId, this.initialTitle, this.initialCompany});
  final String? initialJd;
  final String? jobId;
  final String? initialTitle;
  final String? initialCompany;
  @override
  State<StudioScreen> createState() => _StudioScreenState();
}

class _StudioScreenState extends State<StudioScreen> {
  late final _jd = TextEditingController(text: widget.initialJd ?? '');
  late final _title = TextEditingController(text: widget.initialTitle ?? '');
  late final _company = TextEditingController(text: widget.initialCompany ?? '');
  final _built = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/studio/resumes')));
  Map<String, dynamic>? _out;
  String _template = 'modern';
  List<Map<String, dynamic>> _templates = const [];
  bool _analyzing = false;
  bool _generating = false;

  bool get _fromJob => widget.jobId != null;

  @override
  void initState() {
    super.initState();
    _built.load();
    _loadTemplates();
    if (_fromJob || (widget.initialJd ?? '').trim().length >= 30) WidgetsBinding.instance.addPostFrameCallback((_) => _analyze());
  }

  @override
  void dispose() {
    _jd.dispose();
    _title.dispose();
    _company.dispose();
    _built.dispose();
    super.dispose();
  }

  Future<void> _loadTemplates() async {
    try {
      final r = asMap(await Session.I.api.get('/studio/templates'));
      final l = asList(r['templates']);
      if (mounted && l.isNotEmpty) setState(() => _templates = l);
    } on ApiException {
      // chips fall back to the default template
    }
  }

  Map<String, dynamic> _body() => {
        if (_fromJob) 'job_id': widget.jobId,
        if (_jd.text.trim().isNotEmpty) 'jd_text': _jd.text.trim(),
        if (_title.text.trim().isNotEmpty) 'title': _title.text.trim(),
        if (_company.text.trim().isNotEmpty) 'company': _company.text.trim(),
      };

  bool _ready() {
    if (_fromJob || _jd.text.trim().length >= 30) return true;
    toast(context, 'Paste the job description (at least a few lines).', error: true);
    return false;
  }

  Future<void> _analyze() async {
    if (!_ready()) return;
    FocusScope.of(context).unfocus();
    setState(() => _analyzing = true);
    try {
      final r = asMap(await Session.I.api.post('/studio/analyze', data: _body()));
      thump();
      if (!mounted) return;
      setState(() => _out = r);
      if (_company.text.trim().isEmpty && '${r['company'] ?? ''}'.isNotEmpty) _company.text = '${r['company']}';
      if (_title.text.trim().isEmpty && '${r['title'] ?? ''}'.isNotEmpty) _title.text = '${r['title']}';
    } on ApiException catch (e) {
      if (mounted) toast(context, friendly(e), error: true);
    }
    if (mounted) setState(() => _analyzing = false);
  }

  Future<void> _generate() async {
    if (!_ready()) return;
    FocusScope.of(context).unfocus();
    setState(() => _generating = true);
    try {
      final r = asMap(await Session.I.api.post('/studio/resume', data: {..._body(), 'template': _template}));
      success();
      if (!mounted) return;
      toast(context, 'Resume ready: ATS score ${num0(asMap(r['ats'])['score'])}');
      await _built.load();
    } on ApiException catch (e) {
      if (mounted) toast(context, friendly(e), error: true);
    }
    if (mounted) setState(() => _generating = false);
  }

  Color _status(String s) => switch (s) {
        'met' => C.good,
        'partial' => C.warn,
        'not_met' => C.bad,
        _ => C.muted,
      };

  IconData _statusIcon(String s) => switch (s) {
        'met' => Icons.check_circle_rounded,
        'partial' => Icons.adjust_rounded,
        'not_met' => Icons.cancel_rounded,
        _ => Icons.help_outline_rounded,
      };

  @override
  Widget build(BuildContext context) {
    final o = _out;
    final ids = _templates.isEmpty ? const ['modern'] : [for (final t in _templates) '${t['id']}'];
    final labels = {for (final t in _templates) '${t['id']}': '${t['name']}'};
    return FeatureScaffold(
      title: 'ATS resume',
      subtitle: 'Built only from your verified profile',
      child: ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 120),
        children: [
          if (_fromJob) ...[
            Stagger(index: 0, child: GlassCard(radius: R.md, padding: const EdgeInsets.all(14), child: Text('Using the description of your saved job. Paste a longer JD below only if you want to override it.', style: T.small))),
            const SizedBox(height: 12),
          ],
          Stagger(index: 1, child: LabeledField(label: 'Job description', controller: _jd, lines: 7, hint: 'Paste the full JD here')),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: LabeledField(label: 'Role (optional)', controller: _title, hint: 'e.g. SDET')),
            const SizedBox(width: 10),
            Expanded(child: LabeledField(label: 'Company (optional)', controller: _company, hint: 'Auto-detected')),
          ]),
          const SizedBox(height: 16),
          PrimaryButton(label: 'Analyze fit', icon: Icons.bolt_rounded, busy: _analyzing, onTap: _analyze),
          if (_analyzing) const Busy(label: 'Reading the JD against your profile'),
          if (o != null && !_analyzing) ..._analysis(o),
          const SectionTitle('Template'),
          ChipRow(options: ids, value: ids.contains(_template) ? _template : ids.first, labels: labels, padding: 0, onChanged: (v) => setState(() => _template = v)),
          const SizedBox(height: 16),
          PrimaryButton(label: 'Generate ATS resume', icon: Icons.auto_awesome_rounded, busy: _generating, onTap: _generate),
          if (_generating) const Busy(label: 'Building your resume'),
          const SizedBox(height: 6),
          Center(child: Text('Only facts from your profile. Missing skills are never added.', style: T.small)),
          const SectionTitle('Your ATS resumes'),
          ListenableBuilder(
            listenable: _built,
            builder: (context, _) {
              final l = _built.data;
              if (l == null) return _built.error != null ? ErrorState(error: _built.error!, onRetry: _built.load) : const Busy();
              if (l.isEmpty) return GlassCard(child: Text('Generated resumes show up here with PDF and Word downloads.', style: T.small));
              return Column(children: [for (final (i, r) in l.indexed) Padding(padding: const EdgeInsets.only(bottom: 10), child: Stagger(index: i, child: _ResumeRow(r, ids.contains(_template) ? _template : ids.first)))]);
            },
          ),
        ],
      ),
    );
  }

  List<Widget> _analysis(Map<String, dynamic> o) {
    final score = (o['score'] as num?) ?? 0;
    final verdict = asMap(o['verdict']);
    final checks = asList(o['eligibility']);
    final skills = asMap(o['skills']);
    final all = [...asList(skills['required']), ...asList(skills['preferred'])];
    final have = [for (final s in all) if (s['have'] == true) '${s['name']}'];
    final miss = [for (final s in all) if (s['have'] != true) '${s['name']}'];
    final strengths = (o['strengths'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    return [
      const SizedBox(height: 22),
      Stagger(
        index: 0,
        child: GlassCard(
          child: Row(children: [
            ScoreRing(score: score, size: 104, label: 'MATCH'),
            const SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${o['title'] ?? 'This role'}', style: T.h2, maxLines: 2, overflow: TextOverflow.ellipsis),
                if ('${o['company'] ?? ''}'.isNotEmpty && o['company'] != null) Text('${o['company']}', style: T.small),
                const SizedBox(height: 8),
                if ('${verdict['label'] ?? ''}'.isNotEmpty) Pill('${verdict['label']}', color: scoreColor(score), filled: true),
              ]),
            ),
          ]),
        ),
      ),
      if ('${o['summary'] ?? ''}'.isNotEmpty) ...[const SizedBox(height: 10), Text('${o['summary']}', style: T.small)],
      if (checks.isNotEmpty) ...[
        const SectionTitle('Eligibility'),
        for (final c in checks)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: GlassCard(
              radius: R.md,
              padding: const EdgeInsets.all(14),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(_statusIcon('${c['status']}'), color: _status('${c['status']}'), size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${c['label']}', style: const TextStyle(fontWeight: FontWeight.w600)),
                    Text('${c['text'] ?? c['why'] ?? ''}', style: T.small),
                  ]),
                ),
              ]),
            ),
          ),
      ],
      if (have.isNotEmpty) ...[
        const SectionTitle('You have'),
        Wrap(spacing: 8, runSpacing: 8, children: [for (final s in have) Pill(s, color: C.good, filled: true)]),
      ],
      if (miss.isNotEmpty) ...[
        const SectionTitle('Not in your profile'),
        Wrap(spacing: 8, runSpacing: 8, children: [for (final s in miss) Pill(s, color: C.warn)]),
        const SizedBox(height: 6),
        Text('These stay off the resume. If you really have them, add them in Profile first.', style: T.small),
      ],
      if (strengths.isNotEmpty) ...[
        const SectionTitle('Your strengths here'),
        for (final s in strengths.take(8)) Dot(s, C.good),
      ],
    ];
  }
}

class _ResumeRow extends StatelessWidget {
  const _ResumeRow(this.r, this.template);
  final Map<String, dynamic> r;
  final String template;
  @override
  Widget build(BuildContext context) {
    final s = r['ats_score'] as num?;
    final p = '/studio/resumes/${r['id']}/download';
    Map<String, dynamic> q(String f) => {'format': f, 'template': template};
    return GlassCard(
      radius: R.md,
      padding: const EdgeInsets.all(14),
      child: Row(children: [
        Text(s == null ? '--' : '${s.round()}', style: T.h2.copyWith(color: scoreColor(s))),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${r['name']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
            Text(timeAgo('${r['created_at']}'), style: T.small),
          ]),
        ),
        Pressable(onTap: () => downloadAndShare(context, p, query: q('pdf'), fallbackName: 'resume.pdf'), child: Pill('PDF', color: C.primary, filled: true)),
        const SizedBox(width: 8),
        Pressable(onTap: () => downloadAndShare(context, p, query: q('docx'), fallbackName: 'resume.docx'), child: Pill('DOCX', color: C.muted)),
      ]),
    );
  }
}
