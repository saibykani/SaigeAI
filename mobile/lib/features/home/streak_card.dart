import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/ui.dart';

/// Daily goal + streak from real activity (applications, outreach, interviews, mock interviews). Hides itself if the
/// numbers can't be loaded, so it never blocks the home screen.
class StreakCard extends StatefulWidget {
  const StreakCard({super.key});
  @override
  State<StreakCard> createState() => _StreakCardState();
}

class _StreakCardState extends State<StreakCard> {
  Map<String, dynamic>? _d;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final r = asMap(await Session.I.api.get('/mobile/streak'));
      if (mounted) setState(() => _d = r);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    if (d == null) return const SizedBox.shrink();
    final streak = (d['current'] as num?)?.toInt() ?? 0;
    final best = (d['best'] as num?)?.toInt() ?? 0;
    final today = (d['today'] as num?)?.toInt() ?? 0;
    final goal = ((d['goal'] as num?)?.toInt() ?? 1).clamp(1, 1000);
    final days = asList(d['last7']);
    final met = today >= goal;
    final flame = streak > 0 ? C.warn : C.muted;
    return GlassCard(
      radius: R.lg,
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.local_fire_department_rounded, color: flame, size: 40),
          const SizedBox(width: 8),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(crossAxisAlignment: CrossAxisAlignment.baseline, textBaseline: TextBaseline.alphabetic, children: [
                CountUp(value: streak, style: T.display.copyWith(color: flame)),
                const SizedBox(width: 6),
                Text('day streak', style: T.small),
              ]),
              Text(
                streak == 0 ? 'Do one thing today to start a streak' : 'Best: $best ${best == 1 ? 'day' : 'days'}',
                style: T.small,
              ),
            ]),
          ),
          DotRing(
            size: 64,
            dots: 24,
            progress: (today / goal).clamp(0, 1).toDouble(),
            color: met ? C.good : C.primary,
            child: Text('$today/$goal', style: T.small.copyWith(fontWeight: FontWeight.w800, color: C.text)),
          ),
        ]),
        const SizedBox(height: 14),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          for (final x in days) _Dot(active: asMap(x)['active'] == true, label: _wd('${asMap(x)['date']}')),
        ]),
      ]),
    );
  }

  static String _wd(String iso) {
    final t = DateTime.tryParse(iso);
    return t == null ? '' : 'MTWTFSS'[t.weekday - 1];
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.active, required this.label});
  final bool active;
  final String label;
  @override
  Widget build(BuildContext context) => Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(shape: BoxShape.circle, color: active ? C.good : C.surface2),
          child: active ? Icon(Icons.check_rounded, size: 18, color: C.onPrimary) : null,
        ),
        const SizedBox(height: 4),
        Text(label, style: T.small.copyWith(fontSize: 11)),
      ]);
}
