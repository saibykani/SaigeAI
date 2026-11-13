import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/ui.dart';
import '../shell/shell.dart';
import 'jobs_screen.dart' show salaryText;

class JobDetailScreen extends StatefulWidget {
  const JobDetailScreen({super.key, required this.jobId, this.heroTag});
  final String jobId;
  final String? heroTag;
  @override
  State<JobDetailScreen> createState() => _JobDetailScreenState();
}

class _JobDetailScreenState extends State<JobDetailScreen> {
  late final Resource<Map<String, dynamic>> _job = Resource(() async => asMap(await Session.I.api.get('/jobs/${widget.jobId}')));
  bool _tailoring = false;
  bool _applying = false;
  bool _expand = false;

  @override
  void initState() {
    super.initState();
    _job.load();
  }

  @override
  void dispose() {
    _job.dispose();
    super.dispose();
  }

  Future<void> _tailor() async {
    setState(() => _tailoring = true);
    try {
      final r = asMap(await Session.I.api.post('/jobs/${widget.jobId}/tailor-resume', data: <String, dynamic>{}));
      final changes = r['changes'] is List ? (r['changes'] as List).length : null;
      if (mounted) toast(context, changes == null ? 'Tailored resume saved. Review it in Profile.' : 'Tailored resume saved with $changes truthful changes.');
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _tailoring = false);
  }

  /// Creates the application in the approval queue. Nothing is sent until the user approves it.
  Future<void> _apply() async {
    setState(() => _applying = true);
    try {
      await Session.I.api.post('/applications', data: {'job_id': widget.jobId});
      success();
      if (mounted) {
        toast(context, 'Added to your queue. Nothing is sent until you approve.');
        Navigator.of(context).popUntil((r) => r.isFirst);
        ShellNav.go(2);
      }
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _applying = false);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        body: SafeArea(
          child: Stack(children: [
            ResourceView<Map<String, dynamic>>(
              resource: _job,
              builder: (context, j) {
                final m = asMap(j['match']);
                final bd = asMap(m['breakdown']);
                final score = (j['score'] as num?)?.toDouble();
                final have = (m['matched_skills'] as List?)?.cast<dynamic>() ?? const [];
                final miss = [...(m['missing_required_skills'] as List? ?? const []), ...(m['missing_preferred_skills'] as List? ?? const [])];
                final reqs = (j['requirements'] as List?) ?? const [];
                final sal = salaryText(j);
                return ListView(
                  physics: const BouncingScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(20, 64, 20, 130),
                  children: [
                    Stagger(
                      index: 0,
                      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text('${j['title']}', style: T.h1),
                            const SizedBox(height: 6),
                            Text('${j['company']}', style: const TextStyle(fontSize: 16, color: C.muted)),
                          ]),
                        ),
                        const SizedBox(width: 14),
                        DotRing(
                          size: 84,
                          dots: 26,
                          progress: score == null ? 0 : score / 100,
                          color: scoreColor(score),
                          child: Hero(tag: widget.heroTag ?? 'x', child: Material(color: Colors.transparent, child: Text(score == null ? '--' : '${score.round()}%', style: T.h2.copyWith(color: scoreColor(score))))),
                        ),
                      ]),
                    ),
                    const SizedBox(height: 16),
                    Stagger(index: 1, child: Wrap(spacing: 8, runSpacing: 8, children: [
                      if (j['location'] != null) Pill('${j['location']}'),
                      if (j['remote'] == true) const Pill('Remote', color: C.good),
                      if (sal.isNotEmpty) Pill(sal, color: C.text),
                      if (j['employment_type'] != null) Pill('${j['employment_type']}'),
                      if (j['classification'] != null) Pill('${j['classification']}', color: scoreColor(score), filled: true),
                    ])),
                    if (bd.isNotEmpty) ...[
                      const SectionTitle('Why this score'),
                      Stagger(index: 2, child: GlassCard(child: Column(children: [for (final e in bd.entries.where((e) => e.value is num)) _Bar(label: e.key, value: (e.value as num).toDouble())]))),
                    ],
                    if (have.isNotEmpty || miss.isNotEmpty) ...[
                      const SectionTitle('Your skills vs this role'),
                      Stagger(
                        index: 3,
                        child: GlassCard(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            if (have.isNotEmpty) ...[
                              const Text('YOU HAVE', style: T.label),
                              const SizedBox(height: 8),
                              Wrap(spacing: 8, runSpacing: 8, children: [for (final s in have) Pill('$s', color: C.good, filled: true)]),
                            ],
                            if (miss.isNotEmpty) ...[
                              const SizedBox(height: 16),
                              const Text('MISSING', style: T.label),
                              const SizedBox(height: 8),
                              Wrap(spacing: 8, runSpacing: 8, children: [for (final s in miss) Pill('$s', color: C.warn, filled: true)]),
                              const SizedBox(height: 10),
                              const Text('Saige only adds skills you can back up. Add missing ones in Profile if you truly have them.', style: T.small),
                            ],
                          ]),
                        ),
                      ),
                    ],
                    if (reqs.isNotEmpty) ...[
                      const SectionTitle('Requirements'),
                      GlassCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [for (final r in reqs.take(8)) Padding(padding: const EdgeInsets.only(bottom: 8), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Padding(padding: EdgeInsets.only(top: 7, right: 10), child: Icon(Icons.circle, size: 6, color: C.primary)), Expanded(child: Text('$r', style: T.body))]))])),
                    ],
                    const SectionTitle('Description'),
                    GlassCard(
                      onTap: () => setState(() => _expand = !_expand),
                      child: AnimatedSize(
                        duration: const Duration(milliseconds: 350),
                        curve: Curves.easeOutCubic,
                        alignment: Alignment.topCenter,
                        child: Text('${j['description'] ?? ''}', maxLines: _expand ? null : 8, overflow: _expand ? TextOverflow.visible : TextOverflow.fade, style: T.body),
                      ),
                    ),
                    if ((j['application_url'] as String?)?.isNotEmpty ?? false) ...[
                      const SizedBox(height: 12),
                      Center(child: TextButton.icon(onPressed: () => launchUrl(Uri.parse(j['application_url'] as String), mode: LaunchMode.externalApplication), icon: const Icon(Icons.open_in_new_rounded, size: 18), label: const Text('Open original posting'))),
                    ],
                  ],
                );
              },
            ),
            Positioned(left: 12, top: 8, child: Pressable(onTap: () => Navigator.of(context).maybePop(), child: Container(width: 46, height: 46, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: const Icon(Icons.arrow_back_rounded)))),
            Positioned(
              left: 16,
              right: 16,
              bottom: 16,
              child: Row(children: [
                Expanded(child: PrimaryButton(label: 'Tailor resume', icon: Icons.auto_fix_high_rounded, ghost: true, busy: _tailoring, onTap: _tailor)),
                const SizedBox(width: 12),
                Expanded(child: PrimaryButton(label: 'Apply', icon: Icons.send_rounded, busy: _applying, onTap: _apply)),
              ]),
            ),
          ]),
        ),
      );
}

class _Bar extends StatelessWidget {
  const _Bar({required this.label, required this.value});
  final String label;
  final double value;
  @override
  Widget build(BuildContext context) {
    final v = (value <= 1 ? value * 100 : value).clamp(0.0, 100.0);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        SizedBox(width: 110, child: Text(label.replaceAll('_', ' '), style: T.small)),
        Expanded(
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: v / 100),
            duration: const Duration(milliseconds: 900),
            curve: Curves.easeOutCubic,
            builder: (_, p, _) => ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(value: p, minHeight: 8, backgroundColor: C.surface3, valueColor: AlwaysStoppedAnimation(scoreColor(v))),
            ),
          ),
        ),
        SizedBox(width: 40, child: Text('${v.round()}', textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w600))),
      ]),
    );
  }
}
