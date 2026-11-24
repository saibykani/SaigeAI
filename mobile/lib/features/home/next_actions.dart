import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/ui.dart';
import '../growth/growth_screen.dart';
import '../notifications/approvals_screen.dart';
import '../radar/radar_screen.dart';
import '../resume/health_screen.dart';
import '../warroom/war_room_screen.dart';

class _Next {
  const _Next(this.icon, this.color, this.title, this.detail, this.go);
  final IconData icon;
  final Color color;
  final String title, detail;
  final Widget Function() go;
}

/// "Do this next": a short, ranked list built from real data. Each row is one tap to the screen that finishes the job.
class NextActions extends StatefulWidget {
  const NextActions({super.key, required this.dash, required this.tips});
  final Map<String, dynamic> dash;
  final List<Map<String, dynamic>> tips;
  @override
  State<NextActions> createState() => _NextActionsState();
}

class _NextActionsState extends State<NextActions> {
  late final _extra = Resource<Map<String, dynamic>>(() async {
    Future<dynamic> safe(Future<dynamic> f) async {
      try {
        return await f;
      } catch (_) {
        return null;
      }
    }

    final r = await Future.wait([safe(Session.I.api.get('/war-room')), safe(Session.I.api.get('/radar', query: {'top': 10}))]);
    return {'rooms': asMap(r[0])['interviews'], 'radar': asMap(r[1])['items']};
  });

  @override
  void initState() {
    super.initState();
    _extra.load();
  }

  @override
  void dispose() {
    _extra.dispose();
    super.dispose();
  }

  List<_Next> _items() {
    final act = asMap(widget.dash['action_required']);
    int n(String k) => (act[k] as num?)?.toInt() ?? 0;
    final out = <_Next>[];
    final now = DateTime.now();

    final rooms = asList(_extra.data?['rooms']).where((i) {
      final at = DateTime.tryParse('${i['scheduled_at']}')?.toLocal();
      return at != null && at.difference(now).inHours < 36;
    }).toList();
    for (final i in rooms.take(1)) {
      final at = DateTime.parse('${i['scheduled_at']}').toLocal();
      final same = at.day == now.day && at.month == now.month;
      final hm = '${at.hour.toString().padLeft(2, '0')}:${at.minute.toString().padLeft(2, '0')}';
      out.add(_Next(Icons.shield_moon_rounded, C.good, 'Prep for ${i['company'] ?? 'your interview'}', '${same ? 'Today' : 'Tomorrow'} $hm  ·  checklist ${i['checklist_done']}/${i['checklist_total']}', () => WarRoomScreen(interviewId: '${i['interview_id']}')));
    }
    if (n('applications_need_approval') > 0) {
      final c = n('applications_need_approval');
      out.add(_Next(Icons.task_alt_rounded, C.primary, '$c application${c == 1 ? '' : 's'} waiting for your approval', 'Nothing is sent until you approve', () => const ApprovalsScreen()));
    }
    final top = asList(_extra.data?['radar']).where((j) => ((j['score'] as num?) ?? 0) >= 70).toList();
    if (top.isNotEmpty) {
      out.add(_Next(Icons.radar_rounded, C.violet, '${top.length} strong match${top.length == 1 ? '' : 'es'} on your radar', 'Best: ${top.first['title']} at ${top.first['company']} (${top.first['score']}%)', () => const RadarScreen()));
    }
    if (n('followups_due') > 0) {
      final c = n('followups_due');
      out.add(_Next(Icons.mark_chat_unread_rounded, C.warn, '$c follow-up${c == 1 ? '' : 's'} due', 'Silent for 10+ days. Draft a polite nudge', () => const GrowthScreen(initial: 'followups')));
    }
    final fix = widget.tips.where((t) => t['area'] == 'resume').toList();
    if (fix.isNotEmpty) {
      out.add(_Next(Icons.monitor_heart_rounded, C.teal, '${fix.first['title']}', 'Resume health: ${fix.first['why'] ?? 'tighten your wording'}', () => const ResumeHealthScreen()));
    }
    return out;
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: _extra,
        builder: (context, _) {
          final items = _items().take(5).toList();
          if (items.isEmpty) return const SizedBox.shrink();
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const SectionTitle('Do this next'),
            for (var i = 0; i < items.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Pressable(
                  scale: 0.97,
                  onTap: () => pushDepth(context, (_) => items[i].go()),
                  child: Container(
                    padding: const EdgeInsets.fromLTRB(12, 12, 16, 12),
                    decoration: BoxDecoration(color: C.surface, borderRadius: BorderRadius.circular(99), border: Border.all(color: C.dark ? C.line : Colors.transparent), boxShadow: C.shadow),
                    child: Row(children: [
                      Container(width: 46, height: 46, decoration: BoxDecoration(shape: BoxShape.circle, color: items[i].color.withValues(alpha: 0.16)), child: Icon(items[i].icon, color: items[i].color, size: 22)),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(items[i].title, maxLines: 1, overflow: TextOverflow.ellipsis, style: T.body.copyWith(fontWeight: FontWeight.w700)),
                          Text(items[i].detail, maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
                        ]),
                      ),
                      Icon(Icons.chevron_right_rounded, color: C.muted),
                    ]),
                  ),
                ),
              ),
          ]);
        },
      );
}
