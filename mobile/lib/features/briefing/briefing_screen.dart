import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/briefing.dart';
import '../../core/briefing_logic.dart';
import '../../core/motion.dart';
import '../../core/pulse.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/ui.dart';
import '../notifications/approvals_screen.dart';
import '../quickapply/quick_apply_screen.dart';
import '../radar/radar_screen.dart';
import '../reply/reply_screen.dart';
import '../shell/shell.dart';
import '../warroom/war_room_screen.dart';

/// Opens the screen a briefing row points to (also used by notification taps).
void openBriefingRoute(BuildContext context, String route) {
  final i = route.indexOf(':');
  final kind = i < 0 ? route : route.substring(0, i);
  final id = i < 0 ? '' : route.substring(i + 1);
  switch (kind) {
    case 'radar':
      pushDepth(context, (_) => const RadarScreen());
    case 'quickapply':
      pushDepth(context, (_) => const QuickApplyScreen());
    case 'warroom':
      pushDepth(context, (_) => id.isEmpty ? const WarRoomListScreen() : WarRoomScreen(interviewId: id));
    case 'reply':
      pushDepth(context, (_) => ReplyScreen(replyId: id));
    case 'streak':
      Navigator.of(context).popUntil((r) => r.isFirst);
      ShellNav.go(0);
    default:
      pushDepth(context, (_) => const ApprovalsScreen());
  }
}

/// Your morning in one place: matches, interviews, replies, approvals, streak and one suggested next step.
/// Built from real records only; a section with nothing real in it is left out.
class BriefingScreen extends StatefulWidget {
  const BriefingScreen({super.key});
  @override
  State<BriefingScreen> createState() => _BriefingScreenState();
}

class _BriefingScreenState extends State<BriefingScreen> {
  Briefing? _b;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _failed = false);
    try {
      final b = await BriefingService.I.loadLive();
      Pulse.I.check();
      if (mounted) setState(() => _b = b);
    } catch (_) {
      if (mounted) setState(() => _failed = true);
    }
  }

  static const _icons = {
    'matches': (Icons.radar_rounded, 0),
    'interview': (Icons.event_available_rounded, 1),
    'reply': (Icons.mark_email_unread_rounded, 2),
    'approvals': (Icons.task_alt_rounded, 3),
    'streak': (Icons.local_fire_department_rounded, 4),
    'suggest': (Icons.auto_awesome_rounded, 5),
  };

  Color _tone(int n) => [C.violet, C.good, C.bad, C.warn, C.warn, C.primary][n];

  @override
  Widget build(BuildContext context) {
    final b = _b;
    final hour = DateTime.now().hour;
    final greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
    return FeatureScaffold(
      title: 'Briefing',
      subtitle: '$greet, ${Session.I.firstName}',
      child: b == null
          ? (_failed ? ErrorState(error: ApiException("You're offline or the server can't be reached.", offline: true), onRetry: _load) : const Busy(label: 'Gathering your day'))
          : RefreshIndicatorList(onRefresh: _load, children: [
              if (b.isEmpty)
                const SizedBox(height: 360, child: EmptyState(icon: Icons.wb_sunny_rounded, title: 'Nothing urgent', body: 'No interviews, replies or approvals right now. Check Jobs for you or Match Radar for new roles.'))
              else ...[
                if (b.suggestion != null) Stagger(index: 0, child: _suggest(b.suggestion!)),
                if (b.items.isNotEmpty) const SectionTitle('Your day'),
                for (final (i, it) in b.items.indexed) Stagger(index: i + 1, child: _row(it)),
              ],
            ]),
    );
  }

  Widget _suggest(BriefingItem s) => GlassCard(
        color: C.primarySoft,
        onTap: () => openBriefingRoute(context, s.route),
        child: Row(children: [
          IconBadge(Icons.auto_awesome_rounded, C.primary, size: 46),
          const SizedBox(width: 14),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('SUGGESTED NEXT STEP', style: T.label),
              const SizedBox(height: 4),
              Text(s.title, style: T.h2.copyWith(fontSize: 17)),
              Text(s.sub, style: T.small),
            ]),
          ),
          Icon(Icons.chevron_right_rounded, color: C.muted),
        ]),
      );

  Widget _row(BriefingItem it) {
    final (icon, tone) = _icons[it.kind] ?? (Icons.circle, 5);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassCard(
        radius: R.md,
        padding: const EdgeInsets.all(14),
        onTap: () => openBriefingRoute(context, it.route),
        child: Row(children: [
          IconBadge(icon, _tone(tone)),
          const SizedBox(width: 14),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(it.title, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15.5)),
              const SizedBox(height: 2),
              Text(it.sub, maxLines: 2, overflow: TextOverflow.ellipsis, style: T.small),
            ]),
          ),
          Icon(Icons.chevron_right_rounded, color: C.muted),
        ]),
      ),
    );
  }
}
