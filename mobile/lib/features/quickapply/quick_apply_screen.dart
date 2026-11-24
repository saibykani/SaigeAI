import 'dart:async';
import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import 'quick_apply_logic.dart';
import 'quick_apply_store.dart';
import 'ready_tray_screen.dart';

/// Builds the tailored resume and application email for one radar job (ATS Studio). Nothing is sent here: the result goes to
/// the "Ready to send" tray, where the user reviews it and sends on purpose.
Future<ReadyItem> prepareApplication(Map<String, dynamic> j) async {
  final api = Session.I.api;
  final careers = j['origin'] == 'careers';
  final url = '${j['url'] ?? ''}';
  var jd = '';
  if (!careers) {
    // Greenhouse / Lever / Ashby links give the real description through their public APIs; otherwise use what the radar knows.
    if (url.isNotEmpty) {
      try {
        jd = '${asMap(await api.post('/studio/fetch-jd', data: {'url': url}))['jd_text'] ?? ''}';
      } catch (_) {}
    }
    if (jd.trim().length < 30) jd = thinJdText(j);
  }
  final r = asMap(await api.post('/studio/apply/draft', data: {
    if (careers) 'career_job_id': '${j['id']}' else 'jd_text': jd,
    'title': '${j['title']}',
    'company': '${j['company']}',
    'template': 'modern',
  }));
  final base = (
    jobId: '${j['id']}',
    title: '${j['title']}',
    company: '${j['company']}',
    url: url,
    score: j['score'] as num?,
    careerJobId: careers ? '${j['id']}' : null,
    jd: careers ? '' : jd,
    loc: j['location'] as String?,
  );
  if (r['status'] == 'needs_details') {
    return ReadyItem(
      jobId: base.jobId, title: base.title, company: base.company, url: base.url, score: base.score, needsDetails: true,
      careerJobId: base.careerJobId, jdText: base.jd, location: base.loc, suggestions: [for (final e in (r['emails_found'] as List? ?? const [])) '$e'], from: r['gmail'] as String?,
    );
  }
  return ReadyItem(
    jobId: base.jobId, title: base.title, company: base.company, url: base.url, score: base.score, careerJobId: base.careerJobId, jdText: base.jd, location: base.loc,
    resumeId: '${r['id']}', to: '${r['to'] ?? ''}', subject: '${r['subject'] ?? ''}', body: '${r['body'] ?? ''}', from: r['gmail'] as String?,
    suggestions: [for (final e in (r['emails_found'] as List? ?? const [])) '$e'],
  );
}

/// Full-screen card stack of your top matches. Swipe right to prepare a resume and email (goes to Ready to send), left to skip.
/// Swiping never sends anything.
class QuickApplyScreen extends StatefulWidget {
  const QuickApplyScreen({super.key});
  @override
  State<QuickApplyScreen> createState() => _QuickApplyScreenState();
}

class _QuickApplyScreenState extends State<QuickApplyScreen> {
  final _store = QuickApplyStore.I;
  final _r = Resource<List<Map<String, dynamic>>>(() async => asList(asMap(await Session.I.api.get('/radar', query: {'top': 30}))['items']));
  List<Map<String, dynamic>> _deck = [];
  int _working = 0;
  Future<void> _chain = Future.value();

  @override
  void initState() {
    super.initState();
    _r.addListener(_rebuildDeck);
    _store.ensure().then((_) => _r.load());
  }

  @override
  void dispose() {
    _r.removeListener(_rebuildDeck);
    _r.dispose();
    super.dispose();
  }

  void _rebuildDeck() {
    final d = _r.data;
    if (d != null && mounted) setState(() => _deck = buildDeck(d, skipped: _store.skipped, handled: _store.handled));
  }

  void _swiped(bool right) {
    if (_deck.isEmpty) return;
    final j = _deck.first;
    setState(() => _deck = _deck.sublist(1));
    if (right) {
      thump();
      setState(() => _working++);
      _chain = _chain.then((_) => _prepare(j));
    } else {
      tick();
      _store.skip('${j['id']}');
    }
  }

  Future<void> _prepare(Map<String, dynamic> j) async {
    try {
      final item = await prepareApplication(j);
      await _store.add(item);
      if (!mounted) return;
      success();
      toast(
        context,
        item.needsDetails
            ? '${j['company']}: Saige needs a few details. Finish it in Ready to send.'
            : item.hasEmail
                ? 'Ready to send: ${j['title']} at ${j['company']}'
                : 'Resume ready for ${j['company']}. No email found, so open the job or download it.',
      );
    } catch (e) {
      if (mounted) toast(context, 'Could not prepare ${j['company']}: ${friendly(e)}', error: true);
    }
    if (mounted) setState(() => _working--);
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Quick apply',
        subtitle: 'Right to prepare, left to skip',
        trailing: ValueListenableBuilder<List<ReadyItem>>(
          valueListenable: _store.tray,
          builder: (context, tray, _) => Pressable(
            onTap: () => pushDepth(context, (_) => const ReadyTrayScreen()),
            child: Container(
              height: 40,
              padding: const EdgeInsets.symmetric(horizontal: 14),
              decoration: BoxDecoration(color: tray.isEmpty ? C.surface2 : C.primary, borderRadius: BorderRadius.circular(99)),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.outbox_rounded, size: 18, color: tray.isEmpty ? C.muted : C.onPrimary),
                const SizedBox(width: 6),
                Text('${tray.length}', style: TextStyle(fontWeight: FontWeight.w800, color: tray.isEmpty ? C.muted : C.onPrimary)),
              ]),
            ),
          ),
        ),
        child: ResourceView<List<Map<String, dynamic>>>(
          resource: _r,
          builder: (context, _) {
            if (_deck.isEmpty) return _done();
            return Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
              child: Column(children: [
                if (_working > 0)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Pill('Preparing $_working…', color: C.primary, filled: true),
                  ),
                Expanded(
                  child: SwipeDeck(
                    // The key makes a fresh state per top card so drag offsets never carry over.
                    key: ValueKey('${_deck.first['id']}'),
                    top: _JobCard(job: _deck.first),
                    next: _deck.length > 1 ? _JobCard(job: _deck[1]) : null,
                    onSwipe: _swiped,
                  ),
                ),
                const SizedBox(height: 16),
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  _roundBtn(Icons.close_rounded, C.bad, () => _swiped(false), 'Skip'),
                  const SizedBox(width: 28),
                  _roundBtn(Icons.check_rounded, C.good, () => _swiped(true), 'Prepare'),
                ]),
                const SizedBox(height: 10),
                Text('${_deck.length} left. Preparing never sends: you review and send from Ready to send.', style: T.small, textAlign: TextAlign.center),
              ]),
            );
          },
        ),
      );

  Widget _roundBtn(IconData icon, Color color, VoidCallback onTap, String label) => Column(mainAxisSize: MainAxisSize.min, children: [
        Pressable(
          onTap: onTap,
          child: Container(width: 68, height: 68, decoration: BoxDecoration(shape: BoxShape.circle, color: color.withValues(alpha: 0.16), border: Border.all(color: color.withValues(alpha: 0.5), width: 2)), child: Icon(icon, color: color, size: 32)),
        ),
        const SizedBox(height: 6),
        Text(label, style: T.small),
      ]);

  Widget _done() => ListView(physics: const AlwaysScrollableScrollPhysics(), children: [
        SizedBox(
          height: 380,
          child: EmptyState(
            icon: Icons.style_rounded,
            title: _working > 0 ? 'Preparing your applications' : 'You are all caught up',
            body: _store.tray.value.isEmpty
                ? 'No more matches to swipe right now. New ones show up as the radar finds them.'
                : '${_store.tray.value.length} ready to review. Open the tray to send or discard.',
            action: _store.tray.value.isEmpty ? (_store.skipped.isEmpty ? null : 'Show skipped jobs again') : 'Open Ready to send',
            onAction: _store.tray.value.isEmpty
                ? () async {
                    await _store.clearSkipped();
                    _rebuildDeck();
                  }
                : () => pushDepth(context, (_) => const ReadyTrayScreen()),
          ),
        ),
      ]);
}

/// Two stacked cards: the top one follows the finger and flies off past a threshold; the next one waits underneath.
class SwipeDeck extends StatefulWidget {
  const SwipeDeck({super.key, required this.top, this.next, required this.onSwipe});
  final Widget top;
  final Widget? next;
  final ValueChanged<bool> onSwipe; // true = right
  @override
  State<SwipeDeck> createState() => _SwipeDeckState();
}

class _SwipeDeckState extends State<SwipeDeck> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 260));
  Offset _drag = Offset.zero;
  Offset _from = Offset.zero;
  Offset _to = Offset.zero;
  bool _leaving = false;
  bool? _dir;

  @override
  void initState() {
    super.initState();
    _c.addListener(() => setState(() => _drag = Offset.lerp(_from, _to, Curves.easeOut.transform(_c.value))!));
    _c.addStatusListener((s) {
      if (s == AnimationStatus.completed && _leaving && _dir != null) widget.onSwipe(_dir!);
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  void _fly(bool right, double width) {
    if (_leaving) return;
    _leaving = true;
    _dir = right;
    _from = _drag;
    _to = Offset((right ? 1 : -1) * width * 1.4, _drag.dy);
    _c.forward(from: 0);
  }

  void _back() {
    _from = _drag;
    _to = Offset.zero;
    _c.forward(from: 0);
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, box) {
        final w = box.maxWidth;
        final p = (_drag.dx / (w * 0.4)).clamp(-1.0, 1.0);
        return Stack(children: [
          if (widget.next != null)
            Positioned.fill(child: Transform.scale(scale: 0.94 + 0.06 * p.abs(), child: Opacity(opacity: 0.75 + 0.25 * p.abs(), child: widget.next!))),
          Positioned.fill(
            child: GestureDetector(
              onPanUpdate: _leaving ? null : (d) => setState(() => _drag += d.delta),
              onPanEnd: _leaving
                  ? null
                  : (d) {
                      final v = d.velocity.pixelsPerSecond.dx;
                      if (_drag.dx > w * 0.28 || v > 900) {
                        _fly(true, w);
                      } else if (_drag.dx < -w * 0.28 || v < -900) {
                        _fly(false, w);
                      } else {
                        _back();
                      }
                    },
              child: Transform.translate(
                offset: _drag,
                child: Transform.rotate(
                  angle: math.min(0.35, math.max(-0.35, _drag.dx / w * 0.5)),
                  child: Stack(children: [
                    Positioned.fill(child: widget.top),
                    Positioned(top: 22, left: 22, child: _stamp('PREPARE', C.good, p > 0 ? p : 0)),
                    Positioned(top: 22, right: 22, child: _stamp('SKIP', C.bad, p < 0 ? -p : 0)),
                  ]),
                ),
              ),
            ),
          ),
        ]);
      });

  Widget _stamp(String text, Color color, double o) => Opacity(
        opacity: o.clamp(0.0, 1.0),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(color: color.withValues(alpha: 0.16), borderRadius: BorderRadius.circular(99), border: Border.all(color: color, width: 2)),
          child: Text(text, style: TextStyle(color: color, fontWeight: FontWeight.w900, letterSpacing: 1.2, fontSize: 15)),
        ),
      );
}

class _JobCard extends StatelessWidget {
  const _JobCard({required this.job});
  final Map<String, dynamic> job;

  Color _fit(num s) => s >= 75 ? C.good : s >= 55 ? C.warn : C.muted;

  @override
  Widget build(BuildContext context) {
    final j = job;
    final score = (j['score'] as num?) ?? 0;
    final color = _fit(score);
    final matched = (j['matched_skills'] as List? ?? const []).map((e) => '$e').toList();
    final missing = (j['missing_skills'] as List? ?? const []).map((e) => '$e').toList();
    final reasons = (j['reasons'] as List? ?? const []).map((e) => '$e').toList();
    final url = '${j['url'] ?? ''}';
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(color: C.surface, borderRadius: BorderRadius.circular(R.lg), border: Border.all(color: C.line), boxShadow: C.shadow),
      child: ClipRect(
        child: SingleChildScrollView(
          physics: const NeverScrollableScrollPhysics(),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Container(
                width: 72,
                height: 72,
                alignment: Alignment.center,
                decoration: BoxDecoration(shape: BoxShape.circle, color: color.withValues(alpha: 0.15)),
                child: Text('${score.round()}', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: color)),
              ),
              const SizedBox(width: 14),
              Expanded(child: Text('match with your verified profile', style: T.small)),
            ]),
            const SizedBox(height: 18),
            Text('${j['title']}', maxLines: 3, overflow: TextOverflow.ellipsis, style: T.h1.copyWith(fontSize: 24)),
            const SizedBox(height: 6),
            Text('${j['company']}', style: T.h2.copyWith(color: C.muted)),
            const SizedBox(height: 10),
            Wrap(spacing: 6, runSpacing: 6, children: [
              if ('${j['location'] ?? ''}'.isNotEmpty) Pill('${j['location']}', color: C.text),
              if ('${j['source'] ?? ''}'.isNotEmpty) Pill('${j['source']}', color: C.muted),
              if (url.isEmpty) Pill('No link', color: C.warn),
            ]),
            if (reasons.isNotEmpty) ...[
              const SizedBox(height: 18),
              Text('WHY YOU FIT', style: T.label),
              const SizedBox(height: 8),
              for (final r in reasons.take(3)) Dot(r, C.good),
            ],
            if (matched.isNotEmpty) ...[
              const SizedBox(height: 4),
              Wrap(spacing: 6, runSpacing: 6, children: [for (final s in matched.take(6)) Pill(s, color: C.good, filled: true)]),
            ],
            if (missing.isNotEmpty) ...[
              const SizedBox(height: 14),
              Text('NOT ON YOUR PROFILE', style: T.label),
              const SizedBox(height: 8),
              Wrap(spacing: 6, runSpacing: 6, children: [for (final s in missing.take(4)) Pill(s, color: C.warn)]),
            ],
          ]),
        ),
      ),
    );
  }
}
