import 'package:material_ui/material_ui.dart';

import '../../core/resource.dart';
import '../../core/motion.dart';
import '../../core/theme.dart';
import '../../core/widgets/confetti.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

/// Final report: overall score ring, skill bars, strengths, what to improve, every question with feedback.
class MockReportScreen extends StatefulWidget {
  const MockReportScreen({super.key, required this.report, required this.role});
  final Map<String, dynamic> report;
  final String role;
  @override
  State<MockReportScreen> createState() => _MockReportScreenState();
}

class _MockReportScreenState extends State<MockReportScreen> {
  int? _open;

  @override
  void initState() {
    super.initState();
    if (((widget.report['overall'] as num?) ?? 0) >= 70) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) Confetti.burst(context);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.report;
    final overall = (r['overall'] as num?) ?? 0;
    final skills = asList(r['skills']);
    final strengths = (r['strengths'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    final improve = (r['improvements'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    final qs = asList(r['questions']);
    return FeatureScaffold(
      title: 'Your report',
      subtitle: widget.role,
      child: ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 120),
        children: [
          Stagger(index: 0, child: Center(child: ScoreRing(score: overall, size: 180, label: 'OVERALL'))),
          const SizedBox(height: 8),
          Center(child: Text('${r['answered'] ?? 0} of ${qs.length} answered', style: T.small)),
          if (skills.isNotEmpty) ...[
            const SectionTitle('By skill'),
            GlassCard(
              child: Column(children: [
                for (final (i, s) in skills.indexed)
                  Padding(
                    padding: EdgeInsets.only(bottom: i == skills.length - 1 ? 0 : 12),
                    child: Row(children: [
                      SizedBox(width: 110, child: Text('${s['skill']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5))),
                      Expanded(child: BarFill(value: ((s['score'] as num?) ?? 0) / 100, color: scoreColor(s['score'] as num?))),
                      SizedBox(width: 40, child: Text('${s['score']}', textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.w700, color: scoreColor(s['score'] as num?)))),
                    ]),
                  ),
              ]),
            ),
          ],
          if (strengths.isNotEmpty) ...[
            const SectionTitle('Strengths'),
            for (final (i, t) in strengths.indexed) Stagger(index: i, child: Dot(t, C.good)),
          ],
          if (improve.isNotEmpty) ...[
            const SectionTitle('Work on'),
            for (final (i, t) in improve.indexed) Stagger(index: i, child: Dot(t, C.warn)),
          ],
          const SectionTitle('Question by question'),
          for (final (i, q) in qs.indexed)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Stagger(
                index: i % 8,
                child: GlassCard(
                  radius: R.md,
                  padding: const EdgeInsets.all(14),
                  onTap: () => setState(() => _open = _open == i ? null : i),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Expanded(child: Text('${q['question']}', maxLines: _open == i ? 6 : 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, height: 1.3))),
                      const SizedBox(width: 10),
                      Text(q['answered'] == true ? '${q['score']}' : 'Skipped', style: TextStyle(fontWeight: FontWeight.w700, color: q['answered'] == true ? scoreColor(q['score'] as num?) : C.muted)),
                    ]),
                    AnimatedSize(
                      duration: const Duration(milliseconds: 300),
                      curve: Curves.easeOutCubic,
                      alignment: Alignment.topCenter,
                      child: _open != i
                          ? const SizedBox(width: double.infinity)
                          : Padding(
                              padding: const EdgeInsets.only(top: 12),
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                if ('${q['answer'] ?? ''}'.isNotEmpty) ...[const Text('YOU SAID', style: T.label), const SizedBox(height: 4), Text('${q['answer']}', style: T.small.copyWith(color: C.text)), const SizedBox(height: 12)],
                                for (final t in (q['feedback'] as List? ?? const [])) Dot('$t', C.warn),
                                for (final t in (q['outline'] as List? ?? const [])) Dot('$t', C.good),
                              ]),
                            ),
                    ),
                  ]),
                ),
              ),
            ),
          const SizedBox(height: 10),
          PrimaryButton(label: 'Done', onTap: () => Navigator.of(context).maybePop()),
        ],
      ),
    );
  }
}
