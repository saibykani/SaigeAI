import 'dart:async';

import 'package:material_ui/material_ui.dart';

import '../../core/api.dart';
import '../../core/config.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import '../mock/interview_room.dart';

String _countdown(DateTime at) {
  final d = at.difference(DateTime.now());
  if (d.isNegative) return 'Started ${d.abs().inMinutes} min ago';
  if (d.inDays >= 1) return 'In ${d.inDays}d ${d.inHours % 24}h';
  if (d.inHours >= 1) return 'In ${d.inHours}h ${d.inMinutes % 60}m';
  return 'In ${d.inMinutes}m ${d.inSeconds % 60}s';
}

String _clock(DateTime t) {
  const wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  return '${wd[t.weekday - 1]} ${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
}

/// Upcoming interviews with checklist progress; tap one to open its war room.
class WarRoomListScreen extends StatefulWidget {
  const WarRoomListScreen({super.key});
  @override
  State<WarRoomListScreen> createState() => _WarRoomListScreenState();
}

class _WarRoomListScreenState extends State<WarRoomListScreen> {
  final _r = Resource<List<Map<String, dynamic>>>(() async => asList(asMap(await Session.I.api.get('/war-room'))['interviews']));

  @override
  void initState() {
    super.initState();
    _r.load();
  }

  @override
  void dispose() {
    _r.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'War room',
        subtitle: 'Prep right before an interview',
        child: ResourceView<List<Map<String, dynamic>>>(
          resource: _r,
          builder: (context, items) => RefreshIndicatorList(onRefresh: _r.load, children: [
            if (items.isEmpty)
              const SizedBox(height: 360, child: EmptyState(icon: Icons.shield_moon_rounded, title: 'No interviews in the next 14 days', body: 'When one is scheduled it appears here with a prep brief.'))
            else
              for (var i = 0; i < items.length; i++)
                Stagger(
                  index: i,
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: GlassCard(
                      onTap: () async {
                        await pushDepth(context, (_) => WarRoomScreen(interviewId: '${items[i]['interview_id']}'));
                        _r.load();
                      },
                      child: Row(children: [
                        Container(width: 48, height: 48, decoration: BoxDecoration(shape: BoxShape.circle, color: C.good.withValues(alpha: 0.15)), child: Icon(Icons.event_available_rounded, color: C.good)),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text('${items[i]['company'] ?? 'Interview'}', style: T.h2.copyWith(fontSize: 17)),
                            Text('${items[i]['round'] ?? items[i]['role'] ?? ''}  ·  ${_clock(DateTime.parse('${items[i]['scheduled_at']}').toLocal())}', style: T.small, maxLines: 1, overflow: TextOverflow.ellipsis),
                          ]),
                        ),
                        Pill('${items[i]['checklist_done']}/${items[i]['checklist_total']}', color: C.good, filled: true),
                      ]),
                    ),
                  ),
                ),
          ]),
        ),
      );
}

/// One interview's war room: countdown, join, requirements, questions with your own stories, checklist.
class WarRoomScreen extends StatefulWidget {
  const WarRoomScreen({super.key, required this.interviewId});
  final String interviewId;
  @override
  State<WarRoomScreen> createState() => _WarRoomScreenState();
}

class _WarRoomScreenState extends State<WarRoomScreen> {
  late final _r = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/war-room/${widget.interviewId}')));
  final _add = TextEditingController();
  Timer? _t;
  List<Map<String, dynamic>> _items = const [];
  String? _openQ;
  bool _practising = false;

  @override
  void initState() {
    super.initState();
    _r.addListener(() {
      final c = asMap(_r.data?['checklist']);
      if (mounted) setState(() => _items = asList(c['items']));
    });
    _r.load();
    _t = Timer.periodic(const Duration(seconds: 1), (_) => mounted ? setState(() {}) : null);
  }

  @override
  void dispose() {
    _t?.cancel();
    _add.dispose();
    _r.dispose();
    super.dispose();
  }

  Future<void> _patch(Map<String, dynamic> body) async {
    final res = await guarded(context, () async => asMap(await Session.I.api.request('PATCH', '/war-room/${widget.interviewId}/checklist', data: body)));
    if (res != null && mounted) setState(() => _items = asList(res['items']));
  }

  void _toggle(Map<String, dynamic> it) {
    tap();
    final done = it['done'] != true;
    setState(() => it['done'] = done); // optimistic
    _patch({'item_id': it['id'], 'done': done});
  }

  /// 5-minute voice practice: starts the mock interview room for this interview's job (5 questions, spoken by the interviewer,
  /// answered by voice or text, scored, then the short report). The backend writes the questions from the job; the mock API
  /// cannot take a ready-made question list, so the job is passed by application id, or by the war room's own requirements.
  Future<void> _practice(Map<String, dynamic> d) async {
    if (_practising) return;
    setState(() => _practising = true);
    try {
      String? appId;
      try {
        final g = asMap(await Session.I.api.get('/interviews'));
        for (final k in ['upcoming', 'rescheduled']) {
          for (final i in asList(g[k])) {
            if ('${i['id']}' == widget.interviewId && i['application_id'] != null) appId = '${i['application_id']}';
          }
        }
      } catch (_) {}
      final reqs = [for (final q in asList(d['requirements']).take(10)) '${q['text']}'];
      final skills = (d['skills'] as List? ?? const []).map((e) => '$e').toList();
      final jd = [...reqs, if (skills.isNotEmpty) 'Skills: ${skills.join(', ')}'].join(' ');
      final role = '${d['role'] ?? ''}'.trim().isNotEmpty ? '${d['role']}' : 'Interview at ${d['company'] ?? 'the company'}';
      final lang = mockLocales.containsKey(AppConfig.lang) ? AppConfig.lang : 'en';
      final s = asMap(await Session.I.api.post('/mock-interview/sessions', data: {
        'role': role,
        if (appId != null) 'application_id': appId else if (jd.length >= 20) 'jd_text': jd,
        'interview_type': 'mixed',
        'difficulty': 'medium',
        'num_questions': 5,
        'language': lang,
        'persona': 'priya',
      }));
      thump();
      if (!mounted) return;
      await pushDepth(context, (_) => InterviewRoom(session: s));
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _practising = false);
  }

  void _addItem() {
    final t = _add.text.trim();
    if (t.isEmpty) return;
    _add.clear();
    _patch({'add': t});
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'War room',
        child: ResourceView<Map<String, dynamic>>(
          resource: _r,
          builder: (context, d) {
            final at = DateTime.tryParse('${d['scheduled_at']}')?.toLocal();
            final join = '${asMap(d['links'])['join'] ?? ''}';
            final qs = asList(d['questions']);
            final reqs = asList(d['requirements']);
            final brush = (d['brush_up'] as List? ?? const []).map((e) => '$e').toList();
            final done = _items.where((e) => e['done'] == true).length;
            return RefreshIndicatorList(onRefresh: _r.load, children: [
              GlassCard(
                color: C.primarySoft,
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${d['company'] ?? 'Interview'}${d['round'] == null ? '' : '  ·  ${d['round']}'}', style: T.h2),
                  if ('${d['role'] ?? ''}'.isNotEmpty && d['role'] != null) Text('${d['role']}', style: T.small),
                  const SizedBox(height: 14),
                  if (at != null) Text(_countdown(at), style: T.display.copyWith(color: C.primary)),
                  if (at != null) Text('${_clock(at)}  ·  ${d['duration_minutes'] ?? 60} min${d['interviewer'] == null ? '' : '  ·  ${d['interviewer']}'}', style: T.small),
                  if (join.isNotEmpty) ...[const SizedBox(height: 16), PrimaryButton(label: 'Join interview', icon: Icons.videocam_rounded, onTap: () => openUrl(context, join))],
                ]),
              ),
              const SizedBox(height: 14),
              GlassCard(
                onTap: _practising ? null : () => _practice(d),
                child: Row(children: [
                  IconBadge(Icons.record_voice_over_rounded, C.violet, size: 48),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('5-minute voice practice', style: T.h2.copyWith(fontSize: 17)),
                      Text('Five questions for this role, spoken aloud. Short scored report at the end.', style: T.small),
                    ]),
                  ),
                  if (_practising) const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2.5)) else Icon(Icons.play_circle_fill_rounded, color: C.violet, size: 34),
                ]),
              ),
              if (brush.isNotEmpty) ...[
                const SectionTitle('Brush up on'),
                Wrap(spacing: 6, runSpacing: 6, children: [for (final s in brush) Pill(s, color: C.warn, filled: true)]),
              ],
              if (reqs.isNotEmpty) ...[
                const SectionTitle('What they want'),
                GlassCard(child: Column(children: [for (final q in reqs.take(8)) Dot('${q['text']}${q['evidence'] == null ? '' : '   (your story: ${q['evidence']})'}', q['evidence'] == null ? C.muted : C.good)])),
              ],
              const SectionTitle('Questions to expect'),
              if (qs.isEmpty) Text('No questions yet.', style: T.small),
              for (final q in qs) _question(q),
              SectionTitle('Checklist', trailing: Pill('$done/${_items.length}', color: C.good, filled: true)),
              GlassCard(
                child: Column(children: [
                  for (final it in _items)
                    Pressable(
                      scale: 0.98,
                      onTap: () => _toggle(it),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Row(children: [
                          AnimatedContainer(
                            duration: const Duration(milliseconds: 200),
                            width: 26,
                            height: 26,
                            decoration: BoxDecoration(shape: BoxShape.circle, color: it['done'] == true ? C.good : Colors.transparent, border: Border.all(color: it['done'] == true ? C.good : C.line, width: 2)),
                            child: it['done'] == true ? Icon(Icons.check_rounded, size: 17, color: C.onPrimary) : null,
                          ),
                          const SizedBox(width: 12),
                          Expanded(child: Text('${it['text']}', style: T.body.copyWith(decoration: it['done'] == true ? TextDecoration.lineThrough : null, color: it['done'] == true ? C.muted : C.text))),
                          if (it['custom'] == true)
                            Pressable(onTap: () => _patch({'remove': it['id']}), child: Padding(padding: const EdgeInsets.all(6), child: Icon(Icons.close_rounded, size: 18, color: C.muted))),
                        ]),
                      ),
                    ),
                  const SizedBox(height: 6),
                  Row(children: [
                    Expanded(child: TextField(controller: _add, decoration: const InputDecoration(hintText: 'Add your own item'), onSubmitted: (_) => _addItem())),
                    const SizedBox(width: 8),
                    Pressable(onTap: _addItem, child: Container(width: 48, height: 48, decoration: BoxDecoration(shape: BoxShape.circle, color: C.primary), child: Icon(Icons.add_rounded, color: C.onPrimary))),
                  ]),
                ]),
              ),
            ]);
          },
        ),
      );

  Widget _question(Map<String, dynamic> q) {
    final key = '${q['text']}';
    final open = _openQ == key;
    final story = asMap(q['story']);
    final line = '${story['line'] ?? 'UNKNOWN'}';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassCard(
        onTap: () {
          tick();
          setState(() => _openQ = open ? null : key);
        },
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(key, style: T.body.copyWith(fontWeight: FontWeight.w600))),
            Icon(open ? Icons.expand_less_rounded : Icons.expand_more_rounded, color: C.muted),
          ]),
          if (open) ...[
            const SizedBox(height: 10),
            Text('YOUR STORY${story['name'] == null ? '' : ': ${'${story['name']}'.toUpperCase()}'}', style: T.label),
            const SizedBox(height: 6),
            Text(line == 'UNKNOWN' ? 'No verified story matches this yet. Answer from your own experience.' : line, style: T.small.copyWith(color: C.text)),
          ],
        ]),
      ),
    );
  }
}
