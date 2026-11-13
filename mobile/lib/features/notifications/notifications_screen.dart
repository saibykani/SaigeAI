import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/ui.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});
  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final _n = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/notifications')));

  @override
  void initState() {
    super.initState();
    _n.load();
  }

  @override
  void dispose() {
    _n.dispose();
    super.dispose();
  }

  Future<void> _readAll() async {
    try {
      await Session.I.api.post('/notifications/read-all');
      Session.I.unread.value = 0;
      await _n.load();
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
  }

  Future<void> _read(Map<String, dynamic> n) async {
    if (n['read'] == true) return;
    try {
      await Session.I.api.post('/notifications/${n['id']}/read');
      n['read'] = true;
      _n.set([...?_n.data]);
      Session.I.refreshUnread();
    } catch (_) {}
  }

  IconData _icon(String k) => switch (k) {
        'offer' => Icons.emoji_events_rounded,
        'rejected' || 'rejection' => Icons.heart_broken_outlined,
        final s when s.contains('interview') => Icons.event_available_rounded,
        final s when s.contains('gmail') || s.contains('email') => Icons.mail_outline_rounded,
        _ => Icons.notifications_none_rounded,
      };

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        body: SafeArea(
          child: Stack(children: [
            ResourceView<List<Map<String, dynamic>>>(
              resource: _n,
              builder: (context, list) => LogoRefreshView(onRefresh: _n.load, slivers: [
                if (list.isEmpty)
                  const SliverFillRemaining(hasScrollBody: false, child: EmptyState(icon: Icons.notifications_off_outlined, title: 'All quiet', body: 'Replies, interview invites and offers will appear here.'))
                else
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(20, 64, 20, 0),
                    sliver: SliverList.list(children: [
                      Row(children: [const Expanded(child: Text('Notifications', style: T.display)), TextButton(onPressed: _readAll, child: const Text('Read all'))]),
                      const SizedBox(height: 14),
                      for (final (i, n) in list.indexed)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: Stagger(
                            index: i,
                            child: GlassCard(
                              radius: R.md,
                              padding: const EdgeInsets.all(16),
                              onTap: () => _read(n),
                              border: n['read'] == true ? null : C.primary.withValues(alpha: 0.5),
                              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Icon(_icon('${n['kind']}'), color: n['read'] == true ? C.muted : C.primary),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                    Text('${n['title']}', style: const TextStyle(fontWeight: FontWeight.w600)),
                                    if ('${n['body'] ?? ''}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 3), child: Text('${n['body']}', style: T.small, maxLines: 3, overflow: TextOverflow.ellipsis)),
                                    const SizedBox(height: 6),
                                    Text(timeAgo('${n['created_at']}'), style: T.label),
                                  ]),
                                ),
                              ]),
                            ),
                          ),
                        ),
                    ]),
                  ),
              ]),
            ),
            Positioned(left: 12, top: 8, child: Pressable(onTap: () => Navigator.of(context).maybePop(), child: Container(width: 46, height: 46, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: const Icon(Icons.arrow_back_rounded)))),
          ]),
        ),
      );
}
