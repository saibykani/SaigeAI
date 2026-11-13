import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/ui.dart';

/// A job from discover / career portals: score ring, tags, matched skills, Save + Open.
class OpenJobCard extends StatefulWidget {
  const OpenJobCard({super.key, required this.job, required this.onSave, this.saved = false});
  final Map<String, dynamic> job;
  final Future<bool> Function() onSave;
  final bool saved;
  @override
  State<OpenJobCard> createState() => _OpenJobCardState();
}

class _OpenJobCardState extends State<OpenJobCard> {
  bool _saving = false;
  late bool _saved = widget.saved;
  bool _open = false;

  Future<void> _save() async {
    if (_saved || _saving) return;
    setState(() => _saving = true);
    final ok = await widget.onSave();
    if (mounted) {
      setState(() {
        _saving = false;
        _saved = ok;
      });
    }
  }

  Future<void> _link() async {
    final u = Uri.tryParse('${widget.job['url'] ?? ''}');
    if (u == null || !u.hasScheme) return;
    await launchUrl(u, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final j = widget.job;
    final s = j['score'] as num?;
    final matched = (j['matched_skills'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    final missing = (j['missing_skills'] as List?)?.map((e) => '$e').toList() ?? const <String>[];
    final salary = '${j['salary_text'] ?? ''}'.trim();
    return GlassCard(
      onTap: () => setState(() => _open = !_open),
      radius: R.md,
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${j['title']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15.5)),
              const SizedBox(height: 2),
              Text('${j['company'] ?? ''}${j['location'] != null ? '  ·  ${j['location']}' : ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
            ]),
          ),
          const SizedBox(width: 12),
          if (s != null)
            DotRing(size: 52, dots: 18, progress: s / 100, color: scoreColor(s), child: Text('${s.round()}', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14, color: scoreColor(s)))),
        ]),
        const SizedBox(height: 10),
        Wrap(spacing: 6, runSpacing: 6, children: [
          if (j['fresh'] == true) Pill('New', color: C.good, filled: true),
          if (j['remote'] == true || j['scope'] == 'remote') Pill('Remote', color: C.good),
          if (j['walk_in'] == true) Pill('Walk-in', color: C.warn),
          if ('${j['fit_label'] ?? ''}'.isNotEmpty) Pill('${j['fit_label']}'.split(':').first, color: scoreColor(s)),
          if (salary.isNotEmpty) Pill(salary),
          if ('${j['source'] ?? ''}'.isNotEmpty) Pill('${j['source']}'),
        ]),
        AnimatedSize(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOutCubic,
          alignment: Alignment.topCenter,
          child: !_open
              ? const SizedBox(width: double.infinity)
              : Padding(
                  padding: const EdgeInsets.only(top: 14),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    if (matched.isNotEmpty) ...[Text('YOU HAVE', style: T.label), const SizedBox(height: 6), Wrap(spacing: 6, runSpacing: 6, children: [for (final m in matched) Pill(m, color: C.good, filled: true)])],
                    if (missing.isNotEmpty) ...[const SizedBox(height: 12), Text('GAPS (not on your profile)', style: T.label), const SizedBox(height: 6), Wrap(spacing: 6, runSpacing: 6, children: [for (final m in missing) Pill(m, color: C.warn)])],
                    if (matched.isEmpty && missing.isEmpty) Text('Open the posting for the full description.', style: T.small),
                  ]),
                ),
        ),
        const SizedBox(height: 14),
        Row(children: [
          Expanded(child: PrimaryButton(label: _saved ? 'Saved' : 'Save', icon: _saved ? Icons.check_rounded : Icons.bookmark_add_outlined, busy: _saving, ghost: _saved, onTap: _saved ? null : _save)),
          const SizedBox(width: 10),
          SizedBox(width: 130, child: PrimaryButton(label: 'Open', icon: Icons.open_in_new_rounded, ghost: true, onTap: _link)),
        ]),
      ]),
    );
  }
}
