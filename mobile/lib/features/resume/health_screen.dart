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

/// Line-by-line resume health: Saige's wording fixes beside your lines, with inputs for your own real numbers.
class ResumeHealthScreen extends StatefulWidget {
  const ResumeHealthScreen({super.key});
  @override
  State<ResumeHealthScreen> createState() => _ResumeHealthScreenState();
}

class _ResumeHealthScreenState extends State<ResumeHealthScreen> {
  String? _id;
  Map<String, dynamic>? _report;
  ApiException? _error;
  bool _loading = false;
  bool _applying = false;
  final Map<String, TextEditingController> _edits = {};

  @override
  void dispose() {
    for (final c in _edits.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _load(String id) async {
    for (final c in _edits.values) {
      c.dispose();
    }
    _edits.clear();
    setState(() {
      _id = id;
      _loading = true;
      _error = null;
    });
    try {
      final r = asMap(await Session.I.api.get('/resumes/$id/health'));
      if (mounted && _id == id) setState(() => _report = r);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _apply() async {
    final id = _id;
    if (id == null) return;
    final edits = <String, String>{
      for (final e in _edits.entries)
        if (e.value.text.trim().isNotEmpty) e.key: e.value.text.trim(),
    };
    FocusScope.of(context).unfocus();
    setState(() => _applying = true);
    try {
      final r = asMap(await Session.I.api.post('/resumes/$id/health/fix', data: {'edits': edits, 'verbs': true, 'split': true, 'trim_skills': false}));
      success();
      if (!mounted) return;
      final before = r['before'] as num?;
      final now = r['score'] as num?;
      toast(context, 'New version saved. Health ${before ?? '--'} to ${now ?? '--'}. ${(r['changes'] as List?)?.length ?? 0} changes.');
      if ((now ?? 0) >= 80) Confetti.burst(context);
      for (final c in _edits.values) {
        c.dispose();
      }
      _edits.clear();
      setState(() => _report = r);
    } on ApiException catch (e) {
      if (mounted) toast(context, e.status == 409 ? 'Nothing to change yet. Write a rewrite with your real number first.' : friendly(e), error: true);
    }
    if (mounted) setState(() => _applying = false);
  }

  @override
  Widget build(BuildContext context) {
    final r = _report;
    return FeatureScaffold(
      title: 'Resume health',
      subtitle: 'Line by line, your facts only',
      child: ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 120),
        children: [
          ResumePicker(onSelected: (id, _) => _load(id)),
          if (_loading) const Busy(label: 'Checking every line'),
          if (_error != null && !_loading) ErrorState(error: _error!, onRetry: () => _load(_id!)),
          if (r != null && !_loading) ..._body(r),
        ],
      ),
    );
  }

  List<Widget> _body(Map<String, dynamic> r) {
    final score = (r['score'] as num?) ?? 0;
    final plan = asMap(r['plan']);
    final rows = asList(plan['rows']);
    final projected = (plan['projected'] as num?) ?? score;
    final need = (plan['numbers_needed'] as num?)?.toInt() ?? 0;
    final secs = asList(r['sections']);
    return [
      const SizedBox(height: 22),
      Stagger(
        index: 0,
        child: GlassCard(
          child: Row(children: [
            ScoreRing(score: score, size: 112, label: 'HEALTH'),
            const SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${r['label'] ?? ''}', style: T.h2),
                const SizedBox(height: 4),
                Text('${r['quantified'] ?? 0} of ${r['bullets'] ?? 0} bullets have a number.', style: T.small),
                if (rows.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Text('After Saige\'s wording fixes: $projected%${need > 0 ? '. Add $need real number${need > 1 ? 's' : ''} to reach 100.' : '.'}', style: T.small.copyWith(color: C.text)),
                ],
              ]),
            ),
          ]),
        ),
      ),
      const SectionTitle('Checks'),
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
                    Text('${s['area']}', style: const TextStyle(fontWeight: FontWeight.w600)),
                    Text('${s['tip']}', style: T.small),
                  ]),
                ),
              ]),
            ),
          ),
        ),
      if (rows.isNotEmpty) ...[
        const SectionTitle('Your lines, side by side'),
        const Padding(padding: EdgeInsets.only(bottom: 12, left: 4), child: Text('Write only numbers that are true. Saige blocks anything not in your verified profile.', style: T.small)),
        for (final (i, row) in rows.indexed)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Stagger(index: i < 8 ? i : 0, child: _PlanRow(row: row, controller: _controllerFor('${row['before']}', row['needs_number'] == true))),
          ),
        const SizedBox(height: 6),
        PrimaryButton(label: 'Apply all', icon: Icons.done_all_rounded, busy: _applying, onTap: _apply),
        const SizedBox(height: 8),
        const Center(child: Text('Saves a new version. Your original stays.', style: T.small)),
      ],
    ];
  }

  TextEditingController? _controllerFor(String before, bool needs) {
    if (!needs) return null;
    return _edits.putIfAbsent(before, TextEditingController.new);
  }
}

class _PlanRow extends StatelessWidget {
  const _PlanRow({required this.row, required this.controller});
  final Map<String, dynamic> row;
  final TextEditingController? controller;
  @override
  Widget build(BuildContext context) {
    final changed = row['changed'] == true;
    return GlassCard(
      radius: R.md,
      padding: const EdgeInsets.all(14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: _Side(label: 'YOURS', text: '${row['before']}', color: C.muted)),
          const SizedBox(width: 10),
          Expanded(child: _Side(label: changed ? 'SAIGE FIX' : 'KEEPS', text: '${row['after']}', color: changed ? C.good : C.muted)),
        ]),
        if (controller != null) ...[
          const SizedBox(height: 12),
          TextField(
            controller: controller,
            minLines: 1,
            maxLines: 4,
            decoration: InputDecoration(hintText: '${row['ask']}'.isEmpty ? 'Rewrite with your real number' : '${row['ask']}', contentPadding: const EdgeInsets.all(14)),
          ),
        ],
      ]),
    );
  }
}

class _Side extends StatelessWidget {
  const _Side({required this.label, required this.text, required this.color});
  final String label;
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: T.label.copyWith(color: color, fontSize: 10.5)),
        const SizedBox(height: 4),
        Text(text, style: T.body.copyWith(fontSize: 13)),
      ]);
}
