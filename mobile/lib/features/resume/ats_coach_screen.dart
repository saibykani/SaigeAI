import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/confetti.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import 'resume_picker.dart';

/// ATS coach for any role: where the resume is weak, what Saige can add truthfully, then "Build my resume".
class AtsCoachScreen extends StatefulWidget {
  const AtsCoachScreen({super.key});
  @override
  State<AtsCoachScreen> createState() => _AtsCoachScreenState();
}

class _AtsCoachScreenState extends State<AtsCoachScreen> {
  final _role = TextEditingController();
  final _jd = TextEditingController();
  final _built = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/studio/resumes')));
  String? _resumeId;
  Map<String, dynamic>? _out;
  bool _busy = false;
  bool _building = false;
  bool _showJd = false;

  @override
  void initState() {
    super.initState();
    _built.load();
  }

  @override
  void dispose() {
    _role.dispose();
    _jd.dispose();
    _built.dispose();
    super.dispose();
  }

  Future<void> _analyze() async {
    if (_resumeId == null) return toast(context, 'Pick a resume first.', error: true);
    if (_role.text.trim().length < 2) return toast(context, 'Type the role you are targeting.', error: true);
    FocusScope.of(context).unfocus();
    setState(() => _busy = true);
    try {
      final r = asMap(await Session.I.api.post('/resumes/ats-coach', data: {
        'resume_id': _resumeId,
        'role': _role.text.trim(),
        if (_jd.text.trim().isNotEmpty) 'jd_text': _jd.text.trim(),
      }));
      thump();
      if (mounted) setState(() => _out = r);
    } on ApiException catch (e) {
      if (mounted) toast(context, friendly(e), error: true);
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _build() async {
    final o = _out;
    if (o == null) return;
    setState(() => _building = true);
    try {
      final r = asMap(await Session.I.api.post('/studio/resume', data: {
        'title': '${o['role']}',
        'jd_text': '${o['jd_text'] ?? ''}',
        'template': 'modern',
        'base_resume_id': _resumeId,
      }));
      success();
      if (!mounted) return;
      Confetti.burst(context);
      await pushDepth(context, (_) => StudioResultScreen(result: r));
      _built.load();
    } on ApiException catch (e) {
      if (mounted) toast(context, friendly(e), error: true);
    }
    if (mounted) setState(() => _building = false);
  }

  @override
  Widget build(BuildContext context) {
    final o = _out;
    return FeatureScaffold(
      title: 'ATS coach',
      subtitle: 'Any role, truthful fixes only',
      child: ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 120),
        children: [
          Stagger(index: 0, child: Text('YOUR RESUME', style: T.label)),
          const SizedBox(height: 10),
          ResumePicker(onSelected: (id, _) => _resumeId = id),
          const SizedBox(height: 22),
          Stagger(index: 1, child: LabeledField(label: 'Target role', controller: _role, hint: 'e.g. SDET, Data Analyst, Product Manager')),
          const SizedBox(height: 10),
          Pressable(
            onTap: () => setState(() => _showJd = !_showJd),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Row(children: [
                Icon(_showJd ? Icons.remove_rounded : Icons.add_rounded, size: 18, color: C.primary),
                const SizedBox(width: 6),
                Text(_showJd ? 'Hide job description' : 'Paste a job description (optional)', style: TextStyle(color: C.primary, fontWeight: FontWeight.w600)),
              ]),
            ),
          ),
          AnimatedSize(
            duration: const Duration(milliseconds: 320),
            curve: Curves.easeOutCubic,
            alignment: Alignment.topCenter,
            child: _showJd
                ? Padding(padding: const EdgeInsets.only(bottom: 10), child: LabeledField(label: 'Job description', controller: _jd, lines: 6, hint: 'Paste the JD to score against it'))
                : const SizedBox(width: double.infinity),
          ),
          const SizedBox(height: 6),
          PrimaryButton(label: 'Analyze my resume', icon: Icons.bolt_rounded, busy: _busy, onTap: _analyze),
          if (_busy) const Busy(label: 'Reading your resume against the role'),
          if (o != null && !_busy) ..._results(o),
          const SectionTitle('Resumes you built'),
          ListenableBuilder(
            listenable: _built,
            builder: (context, _) {
              final l = _built.data;
              if (l == null) return _built.error != null ? ErrorState(error: _built.error!, onRetry: _built.load) : const Busy();
              if (l.isEmpty) return GlassCard(child: Text('Resumes you build here show up with PDF and Word downloads.', style: T.small));
              return Column(children: [for (final (i, r) in l.indexed) Padding(padding: const EdgeInsets.only(bottom: 10), child: Stagger(index: i, child: _BuiltRow(r)))]);
            },
          ),
        ],
      ),
    );
  }

  List<Widget> _results(Map<String, dynamic> o) {
    final score = (o['score'] as num?) ?? 0;
    final projected = (o['projected'] as num?) ?? score;
    final secs = asList(o['sections']);
    final canAdd = (o['can_add'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    final confirm = (o['confirm'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    return [
      const SizedBox(height: 26),
      Stagger(
        index: 0,
        child: GlassCard(
          child: Row(children: [
            ScoreRing(score: score, size: 112, label: 'NOW'),
            const SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('For ${o['role']}', style: T.h2),
                const SizedBox(height: 6),
                Text('Could reach about $projected% with the keywords you can already prove.', style: T.small),
                const SizedBox(height: 10),
                BarFill(value: projected / 100, color: scoreColor(projected)),
              ]),
            ),
          ]),
        ),
      ),
      if (canAdd.isNotEmpty) ...[
        const SectionTitle('Add these now (already in your profile)'),
        Wrap(spacing: 8, runSpacing: 8, children: [for (final s in canAdd) Pill(s, color: C.good, filled: true)]),
      ],
      if (confirm.isNotEmpty) ...[
        const SectionTitle('Only if you have really used them'),
        Wrap(spacing: 8, runSpacing: 8, children: [for (final s in confirm) Pill(s, color: C.warn)]),
        const SizedBox(height: 6),
        Text('Saige will not put these on your resume until you confirm them in Profile. Unknown stays unknown.', style: T.small),
      ],
      const SectionTitle('Weak spots'),
      for (final (i, s) in secs.indexed)
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Stagger(
            index: i,
            child: GlassCard(
              radius: R.md,
              padding: const EdgeInsets.all(14),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(s['ok'] == true ? Icons.check_circle_rounded : Icons.error_outline_rounded, color: s['ok'] == true ? C.good : C.warn, size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${s['section']}', style: const TextStyle(fontWeight: FontWeight.w600)),
                    Text('${s['issue']}', style: T.small),
                    if ('${s['fix'] ?? ''}'.isNotEmpty && s['ok'] != true)
                      Padding(padding: const EdgeInsets.only(top: 6), child: Text('${s['fix']}', style: TextStyle(fontSize: 13, color: C.text, height: 1.35))),
                  ]),
                ),
              ]),
            ),
          ),
        ),
      const SizedBox(height: 10),
      PrimaryButton(label: 'Build my resume', icon: Icons.auto_awesome_rounded, busy: _building, onTap: _build),
      const SizedBox(height: 6),
      Center(child: Text('Built only from your verified profile.', style: T.small)),
    ];
  }
}

class _BuiltRow extends StatelessWidget {
  const _BuiltRow(this.r);
  final Map<String, dynamic> r;
  @override
  Widget build(BuildContext context) {
    final s = r['ats_score'] as num?;
    final p = '/studio/resumes/${r['id']}/download';
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
        Pressable(onTap: () => downloadAndShare(context, p, query: {'format': 'pdf'}, fallbackName: 'resume.pdf'), child: Pill('PDF', color: C.primary, filled: true)),
        const SizedBox(width: 8),
        Pressable(onTap: () => downloadAndShare(context, p, query: {'format': 'docx'}, fallbackName: 'resume.docx'), child: Pill('DOCX', color: C.muted)),
      ]),
    );
  }
}

/// The freshly built resume: ATS score, what changed, what is still missing, downloads.
class StudioResultScreen extends StatelessWidget {
  const StudioResultScreen({super.key, required this.result});
  final Map<String, dynamic> result;

  @override
  Widget build(BuildContext context) {
    final ats = asMap(result['ats']);
    final score = (ats['score'] as num?) ?? 0;
    final changes = (result['changes'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    final improve = (result['improve'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    final p = '/studio/resumes/${result['id']}/download';
    return FeatureScaffold(
      title: 'Your resume',
      subtitle: '${result['name'] ?? ''}',
      child: ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 14, 20, 120),
        children: [
          Stagger(index: 0, child: Center(child: ScoreRing(score: score, size: 170, label: 'ATS SCORE'))),
          const SizedBox(height: 22),
          Stagger(
            index: 1,
            child: Row(children: [
              Expanded(child: PrimaryButton(label: 'PDF', icon: Icons.picture_as_pdf_rounded, onTap: () => downloadAndShare(context, p, query: {'format': 'pdf'}, fallbackName: 'resume.pdf'))),
              const SizedBox(width: 12),
              Expanded(child: PrimaryButton(label: 'Word', icon: Icons.description_rounded, ghost: true, onTap: () => downloadAndShare(context, p, query: {'format': 'docx'}, fallbackName: 'resume.docx'))),
            ]),
          ),
          if (changes.isNotEmpty) ...[
            const SectionTitle('What changed (all truthful)'),
            for (final (i, c) in changes.take(12).indexed) Stagger(index: i, child: Dot(c, C.good)),
          ],
          if (improve.isNotEmpty) ...[
            const SectionTitle('To score higher'),
            for (final (i, c) in improve.indexed) Stagger(index: i, child: Dot(c, C.warn)),
          ],
        ],
      ),
    );
  }
}
