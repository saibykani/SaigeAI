import 'dart:math' as math;

import 'package:flutter/physics.dart';

import 'package:material_ui/material_ui.dart';

import '../shell/app_drawer.dart';
import '../../core/api.dart';
import '../../core/motion.dart';
import '../../core/pulse.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/confetti.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';
import 'job_detail_screen.dart';

class JobsScreen extends StatefulWidget {
  const JobsScreen({super.key});
  @override
  State<JobsScreen> createState() => _JobsScreenState();
}

class _JobsScreenState extends State<JobsScreen> {
  final _jobs = Resource<List<Map<String, dynamic>>>(() async {
    final r = await Session.I.api.get('/jobs', query: {'limit': 150, 'sort': 'score'});
    return asList(asMap(r)['items']);
  });
  /// The live "Jobs for you" feed (not yet saved): the swipe deck.
  final _feed = Resource<List<Map<String, dynamic>>>(() async {
    final r = asMap(await Session.I.api.get('/jobs/feed'));
    return asList(r['items']).where((i) => i['saved_job_id'] == null).toList();
  });
  final _deck = GlobalKey<_DeckState>();
  String _seg = 'deck'; // deck | all | saved
  bool _finding = false;

  @override
  void initState() {
    super.initState();
    _jobs.load();
    _feed.load();
  }

  @override
  void dispose() {
    _jobs.dispose();
    _feed.dispose();
    super.dispose();
  }

  /// Rebuilds the feed from the job APIs and career pages. Nothing is applied.
  Future<void> _find() async {
    setState(() => _finding = true);
    try {
      final r = asMap(await Session.I.api.get('/jobs/feed', query: {'refresh': true}));
      final fresh = asList(r['items']).where((i) => i['saved_job_id'] == null).toList();
      _feed.set(fresh);
      if (mounted) toast(context, fresh.isEmpty ? 'No new jobs right now. Check back soon.' : '${fresh.length} jobs for your roles');
    } on ApiException catch (e) {
      if (mounted) toast(context, e.message, error: true);
    }
    if (mounted) setState(() => _finding = false);
  }

  /// Swipe on a feed card. Right: save the job and prepare an application (nothing is sent; jobs with an HR email
  /// show up in Approvals). Left: hide it (Undo brings it back).
  Future<void> _decideFeed(Map<String, dynamic> it, String decision) async {
    final id = '${it['id']}';
    try {
      if (decision == 'shortlisted') {
        await Session.I.api.post('/jobs/feed/save', data: {'ids': [id], 'prepare_applications': true});
        _jobs.load();
        if (mounted) Confetti.burst(context);
        final email = (it['hr_emails'] as List?)?.isNotEmpty == true;
        if (email) Pulse.I.check();
        if (mounted) toast(context, email ? 'Saved. Application ready: approve it in Approvals' : 'Saved to your jobs. Application prepared');
      } else {
        await Session.I.api.post('/mobile/feed/hide', data: {'id': id});
        if (!mounted) return;
        ScaffoldMessenger.of(context)
          ..clearSnackBars()
          ..showSnackBar(SnackBar(
            behavior: SnackBarBehavior.floating,
            backgroundColor: C.dark ? C.surface3 : C.surface,
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 96),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(R.sm), side: BorderSide(color: C.line)),
            content: Text('Hidden ${it['company'] ?? ''}', style: TextStyle(color: C.text)),
            action: SnackBarAction(label: 'Undo', textColor: C.primary, onPressed: () async {
              _deck.currentState?.undo();
              try {
                await Session.I.api.post('/mobile/feed/unhide', data: {'id': id});
              } catch (_) {}
            }),
          ));
      }
    } on ApiException catch (e) {
      _deck.currentState?.undo();
      if (mounted) toast(context, e.message, error: true);
    }
  }

  @override
  Widget build(BuildContext context) => SafeArea(
        bottom: false,
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
            child: Row(children: [
              const MenuButton(),
              Expanded(child: Text('Jobs', style: T.display)),
              if (_finding) Padding(padding: EdgeInsets.only(right: 12), child: DotRing(size: 28, dots: 10)) else _IconBtn(icon: Icons.travel_explore_rounded, onTap: _find),
              const SizedBox(width: 8),
            ]),
          ),
          ChipRow(options: const ['deck', 'all', 'saved'], labels: const {'deck': 'For you', 'all': 'All', 'saved': 'Saved'}, value: _seg, onChanged: (v) {
            tick();
            setState(() => _seg = v);
          }),
          const SizedBox(height: 8),
          Expanded(
            child: _seg == 'deck'
                ? ResourceView<List<Map<String, dynamic>>>(
                    resource: _feed,
                    builder: (context, items) => items.isEmpty
                        ? EmptyState(icon: Icons.style_rounded, title: 'Deck cleared', body: 'Fetch fresh jobs for your roles from job boards and company career pages. Nothing is applied without you.', action: 'Find fresh jobs', onAction: _find)
                        : _Deck(key: _deck, jobs: items, onDecision: _decideFeed, onOpen: (j) => j['url'] != null ? openUrl(context, '${j['url']}') : null),
                  )
                : ResourceView<List<Map<String, dynamic>>>(
              resource: _jobs,
              builder: (context, all) {
                final shown = _seg == 'saved' ? all.where((j) => j['status'] == 'saved' || j['status'] == 'shortlisted').toList() : all;
                return LogoRefreshView(onRefresh: _jobs.load, slivers: [
                  if (shown.isEmpty)
                    SliverFillRemaining(hasScrollBody: false, child: _seg == 'saved' ? const EmptyState(icon: Icons.bookmark_border_rounded, title: 'Nothing saved yet', body: 'Swipe right on a job in For you, or save one from Today, and it shows up here.') : const EmptyState(icon: Icons.work_outline_rounded, title: 'No jobs yet', body: 'Tap the globe to fetch matches for your target roles.'))
                  else
                    SliverPadding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      sliver: SliverList.separated(
                        itemCount: shown.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 10),
                        itemBuilder: (context, i) => Stagger(index: i, child: _JobRow(job: shown[i])),
                      ),
                    ),
                ]);
              },
            ),
          ),
        ]),
      );
}

class _IconBtn extends StatelessWidget {
  const _IconBtn({required this.icon, required this.onTap});
  final IconData icon;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => Pressable(
        onTap: onTap,
        child: Container(width: 46, height: 46, decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: C.line)), child: Icon(icon, size: 22)),
      );
}

String salaryText(Map<String, dynamic> j) {
  final a = j['salary_min'] as num?, b = j['salary_max'] as num?;
  if (a == null && b == null) return '';
  String f(num n) => n >= 100000 ? '${(n / 100000).toStringAsFixed(n % 100000 == 0 ? 0 : 1)}L' : n >= 1000 ? '${(n / 1000).round()}k' : '$n';
  return '${j['currency'] ?? ''} ${a != null ? f(a) : ''}${a != null && b != null ? ' - ' : ''}${b != null ? f(b) : ''}'.trim();
}

class _JobRow extends StatelessWidget {
  const _JobRow({required this.job});
  final Map<String, dynamic> job;
  @override
  Widget build(BuildContext context) {
    final s = job['score'] as num?;
    return GlassCard(
      radius: R.md,
      padding: const EdgeInsets.all(16),
      onTap: () => pushDepth(context, (_) => JobDetailScreen(jobId: '${job['id']}', heroTag: 'job-${job['id']}')),
      child: Row(children: [
        _Avatar('${job['company']}'),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${job['title']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15.5)),
            const SizedBox(height: 3),
            Text('${job['company']}${job['location'] != null ? '  ·  ${job['location']}' : ''}', maxLines: 1, overflow: TextOverflow.ellipsis, style: T.small),
          ]),
        ),
        const SizedBox(width: 10),
        Hero(tag: 'job-${job['id']}', child: Material(color: Colors.transparent, child: Text(s == null ? '--' : '$s%', style: T.h2.copyWith(color: scoreColor(s))))),
      ]),
    );
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar(this.name, {this.size = 46});
  final String name;
  final double size;
  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface3, border: Border.all(color: C.line)),
        child: Text(name.isEmpty ? '?' : name[0].toUpperCase(), style: TextStyle(fontSize: size * 0.42, fontWeight: FontWeight.w700, color: C.primary)),
      );
}

/// Tinder-style deck. The top card follows the finger in 3D (tilt + rotation); the cards under it
/// scale up as it leaves. Right = shortlist, left = hide, tap = detail.
class _Deck extends StatefulWidget {
  const _Deck({super.key, required this.jobs, required this.onDecision, required this.onOpen});
  final List<Map<String, dynamic>> jobs;
  final Future<void> Function(Map<String, dynamic>, String) onDecision;
  final void Function(Map<String, dynamic>) onOpen;
  @override
  State<_Deck> createState() => _DeckState();
}

class _DeckState extends State<_Deck> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController.unbounded(vsync: this);
  final _off = ValueNotifier<Offset>(Offset.zero);
  Offset _from = Offset.zero;
  Offset _to = Offset.zero;
  int _top = 0;
  bool _flying = false;
  bool _crossed = false;

  @override
  void initState() {
    super.initState();
    _c.addListener(() {
      if (_flying || _c.isAnimating) {
        final t = _c.value;
        _off.value = Offset.lerp(_from, _to, t)!;
      }
    });
  }

  @override
  void dispose() {
    _c.dispose();
    _off.dispose();
    super.dispose();
  }

  void _release(double vx, double width) {
    final dx = _off.value.dx;
    final go = dx.abs() > 110 || vx.abs() > 1000;
    _from = _off.value;
    if (go) {
      final dir = (dx.abs() > 40 ? dx : vx).sign == 0 ? 1.0 : (dx.abs() > 40 ? dx : vx).sign;
      _to = Offset(dir * width * 1.5, _off.value.dy + 60);
      _flying = true;
      thump();
      _c.value = 0;
      _c.animateTo(1, duration: const Duration(milliseconds: 320), curve: Curves.easeIn).whenComplete(() {
        _flying = false;
        final job = widget.jobs[_top];
        _off.value = Offset.zero;
        setState(() => _top++);
        widget.onDecision(job, dir > 0 ? 'shortlisted' : 'archived');
      });
    } else {
      _to = Offset.zero;
      _c.value = 0;
      _c.animateWith(SpringSimulation(const SpringDescription(mass: 1, stiffness: 220, damping: 14), 0, 1, 0));
    }
    _crossed = false;
  }

  @override
  void didUpdateWidget(_Deck old) {
    super.didUpdateWidget(old);
    if (!identical(old.jobs, widget.jobs)) _top = 0; // a fresh feed starts from the first card
  }

  /// Brings the last swiped card back (Undo, or the server refused the action).
  void undo() {
    if (_top > 0 && mounted) setState(() => _top--);
  }

  void _swipe(bool right) {
    if (_top >= widget.jobs.length || _flying) return;
    _off.value = Offset(right ? 30 : -30, 0);
    _release(right ? 1500 : -1500, MediaQuery.sizeOf(context).width);
  }

  @override
  Widget build(BuildContext context) {
    final w = MediaQuery.sizeOf(context).width;
    final remaining = widget.jobs.length - _top;
    if (remaining <= 0) return const EmptyState(icon: Icons.done_all_rounded, title: 'All caught up', body: 'Open the list to see what you shortlisted, or find fresh jobs.');
    final visible = [for (var i = math.min(2, remaining - 1); i >= 0; i--) i];
    return Column(children: [
      Expanded(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
          child: Stack(children: [
            for (final i in visible)
              i == 0
                  ? _topCard(w)
                  : Positioned.fill(
                      child: ValueListenableBuilder<Offset>(
                        valueListenable: _off,
                        builder: (context, o, child) {
                          final p = (o.dx.abs() / 160).clamp(0.0, 1.0);
                          final depth = i - p;
                          return Transform.translate(offset: Offset(0, 16.0 * depth), child: Transform.scale(scale: 1 - 0.05 * depth, child: child));
                        },
                        child: _JobCard(job: widget.jobs[_top + i], live: false),
                      ),
                    ),
          ]),
        ),
      ),
      Padding(
        padding: const EdgeInsets.only(bottom: 110, top: 4),
        child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          _RoundAction(icon: Icons.close_rounded, color: C.bad, onTap: () => _swipe(false)),
          const SizedBox(width: 28),
          _RoundAction(icon: Icons.bookmark_added_rounded, color: C.good, big: true, onTap: () => _swipe(true)),
        ]),
      ),
    ]);
  }

  Widget _topCard(double w) {
    final job = widget.jobs[_top];
    return Positioned.fill(
      child: GestureDetector(
        onTap: () => widget.onOpen(job),
        onPanStart: (_) {
          _c.stop();
          _flying = false;
        },
        onPanUpdate: (d) {
          _off.value += d.delta;
          if (!_crossed && _off.value.dx.abs() > 110) {
            _crossed = true;
            tick();
          } else if (_crossed && _off.value.dx.abs() < 100) {
            _crossed = false;
          }
        },
        onPanEnd: (d) => _release(d.velocity.pixelsPerSecond.dx, w),
        child: ValueListenableBuilder<Offset>(
          valueListenable: _off,
          builder: (context, o, child) {
            final p = (o.dx / 160).clamp(-1.0, 1.0);
            final m = Matrix4.identity()
              ..setEntry(3, 2, 0.0012)
              ..translateByDouble(o.dx, o.dy * 0.6, 0, 1)
              ..rotateZ(o.dx / w * 0.38)
              ..rotateY(-p * 0.28);
            return Transform(
              alignment: Alignment.bottomCenter,
              transform: m,
              child: Stack(fit: StackFit.expand, children: [
                child!,
                Positioned(top: 26, left: 26, child: Opacity(opacity: p.clamp(0.0, 1.0), child: _Stamp('SAVE', C.good, -0.2))),
                Positioned(top: 26, right: 26, child: Opacity(opacity: (-p).clamp(0.0, 1.0), child: _Stamp('HIDE', C.bad, 0.2))),
              ]),
            );
          },
          child: _JobCard(job: job, live: true),
        ),
      ),
    );
  }
}

class _Stamp extends StatelessWidget {
  const _Stamp(this.t, this.c, this.angle);
  final String t;
  final Color c;
  final double angle;
  @override
  Widget build(BuildContext context) => Transform.rotate(
        angle: angle,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          decoration: BoxDecoration(border: Border.all(color: c, width: 3), borderRadius: BorderRadius.circular(22)),
          child: Text(t, style: TextStyle(color: c, fontSize: 24, fontWeight: FontWeight.w800, letterSpacing: 2)),
        ),
      );
}

class _RoundAction extends StatelessWidget {
  const _RoundAction({required this.icon, required this.color, required this.onTap, this.big = false});
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  final bool big;
  @override
  Widget build(BuildContext context) => Pressable(
        scale: 0.86,
        onTap: onTap,
        child: Container(
          width: big ? 76 : 62,
          height: big ? 76 : 62,
          decoration: BoxDecoration(shape: BoxShape.circle, color: C.surface2, border: Border.all(color: color.withValues(alpha: 0.6), width: 1.5), boxShadow: [BoxShadow(color: color.withValues(alpha: 0.2), blurRadius: 18)]),
          child: Icon(icon, color: color, size: big ? 34 : 28),
        ),
      );
}

class _JobCard extends StatelessWidget {
  const _JobCard({required this.job, required this.live});
  final Map<String, dynamic> job;
  final bool live;
  @override
  Widget build(BuildContext context) {
    final s = (job['score'] as num?)?.toDouble();
    final sal = salaryText(job);
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(40),
        border: Border.all(color: C.line),
        color: C.surface,
        boxShadow: C.dark ? const [BoxShadow(color: Color(0x99000000), blurRadius: 24, offset: Offset(0, 12))] : C.shadow,
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [_Avatar('${job['company']}', size: 54), const Spacer(), if (job['classification'] != null) Pill('${job['classification']}', color: scoreColor(s), filled: true)]),
        const Spacer(),
        Center(
          child: live
              ? Hero(
                  tag: 'job-${job['id']}',
                  child: Material(
                    color: Colors.transparent,
                    child: DotRing(size: 150, dots: 40, progress: s == null ? 0 : s / 100, color: scoreColor(s), child: Column(mainAxisSize: MainAxisSize.min, children: [Text(s == null ? '--' : '${s.round()}%', style: T.display.copyWith(color: scoreColor(s))), Text('MATCH', style: T.label)])),
                  ),
                )
              : DotRing(size: 150, dots: 40, progress: s == null ? 0 : s / 100, color: scoreColor(s)),
        ),
        const Spacer(),
        Text('${job['title']}', maxLines: 3, overflow: TextOverflow.ellipsis, style: T.h1),
        const SizedBox(height: 6),
        Text('${job['company']}', style: TextStyle(fontSize: 16, color: C.muted)),
        const SizedBox(height: 14),
        Wrap(spacing: 8, runSpacing: 8, children: [
          if (job['location'] != null) Pill('${job['location']}'),
          if (job['remote'] == true) Pill('Remote', color: C.good),
          if (sal.isNotEmpty) Pill(sal, color: C.text),
          if (job['experience_required'] != null) Pill('${job['experience_required']} yrs'),
          if ((job['hr_emails'] as List?)?.isNotEmpty == true) Pill('HR email', color: C.good),
          if (job['walk_in'] != null) Pill('Walk-in', color: C.warn),
          if (job['source_label'] != null) Pill('${job['source_label']}'),
        ]),
        const SizedBox(height: 8),
        Center(child: Text(job['url'] != null && job['status'] == null ? 'Tap to open the posting' : 'Tap for details', style: T.small)),
      ]),
    );
  }
}
