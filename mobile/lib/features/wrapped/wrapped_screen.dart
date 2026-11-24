import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

/// Career Wrapped: swipeable story slides built from counts of your own records.
class WrappedScreen extends StatefulWidget {
  const WrappedScreen({super.key});
  @override
  State<WrappedScreen> createState() => _WrappedScreenState();
}

class _WrappedScreenState extends State<WrappedScreen> {
  String _period = 'all';
  final _page = PageController();
  int _i = 0;
  late final _r = Resource<Map<String, dynamic>>(() async => asMap(await Session.I.api.get('/wrapped', query: {'period': _period})));

  @override
  void initState() {
    super.initState();
    _r.load();
  }

  @override
  void dispose() {
    _page.dispose();
    _r.dispose();
    super.dispose();
  }

  void _set(String p) {
    if (p == _period) return;
    setState(() {
      _period = p;
      _i = 0;
    });
    if (_page.hasClients) _page.jumpToPage(0);
    _r.load();
  }

  List<_Slide> _slides(Map<String, dynamic> d) {
    num n(String k) => (d[k] as num?) ?? 0;
    final top = asList(d['top_skills']);
    final cos = asList(d['top_companies']);
    final busy = asMap(d['busiest_day']);
    final pers = asMap(d['personality']);
    return [
      _Slide(C.primary, 'Applications sent', n('applications'), '', 'over ${n('span_days').toInt()} day${n('span_days') == 1 ? '' : 's'} of searching'),
      _Slide(C.good, 'Replies', n('replies'), '', d['reply_rate'] == null ? 'Reply rate needs more applications' : '${num0(d['reply_rate'])}% reply rate'),
      _Slide(C.warn, 'Interviews', n('interviews'), '', n('offers') > 0 ? '${n('offers').toInt()} offer${n('offers') == 1 ? '' : 's'} so far' : 'Each one is a door opened'),
      _Slide(C.violet, 'Longest streak', n('longest_streak'), ' days', busy.isEmpty ? 'Busiest day: none yet' : 'Busiest day: ${busy['date']} with ${busy['count']} applications'),
      _Slide(C.teal, 'Resumes and outreach', n('resumes_generated') + n('outreach_sent'), '', '${n('resumes_generated').toInt()} resumes tailored, ${n('outreach_sent').toInt()} messages sent'),
      if (top.isNotEmpty) _Slide(C.blue, 'Your top skill', top.first['count'] as num? ?? 0, ' jobs', '${top.first['name']}${top.length > 1 ? '  ·  then ${top.skip(1).take(3).map((e) => e['name']).join(', ')}' : ''}'),
      if (cos.isNotEmpty) _Slide(C.lime, 'Most applied company', cos.first['count'] as num? ?? 0, ' times', '${cos.first['name']}${cos.length > 1 ? '  ·  then ${cos.skip(1).take(3).map((e) => e['name']).join(', ')}' : ''}'),
      _Slide(C.primary, 'You are', null, '', '${pers['rule'] ?? ''}', headline: '${pers['label'] ?? 'The Explorer'}'),
    ];
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Career Wrapped',
        child: Column(children: [
          const SizedBox(height: 4),
          ChipRow(options: const ['all', 'month', 'week'], labels: const {'all': 'All time', 'month': '30 days', 'week': '7 days'}, value: _period, onChanged: _set),
          const SizedBox(height: 12),
          Expanded(
            child: ResourceView<Map<String, dynamic>>(
              resource: _r,
              builder: (context, d) {
                if (d['empty'] == true) {
                  return const EmptyState(icon: Icons.auto_graph_rounded, title: 'Nothing to wrap yet', body: 'Send an application, an outreach message or a tailored resume and your story starts here.');
                }
                final slides = _slides(d);
                return Column(children: [
                  Expanded(
                    child: PageView.builder(
                      controller: _page,
                      physics: const BouncingScrollPhysics(),
                      itemCount: slides.length,
                      onPageChanged: (i) {
                        tick();
                        setState(() => _i = i);
                      },
                      itemBuilder: (context, i) => Padding(padding: const EdgeInsets.fromLTRB(20, 0, 20, 8), child: _SlideCard(key: ValueKey('$_period-$i'), slide: slides[i])),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.only(bottom: 24, top: 8),
                    child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                      for (var i = 0; i < slides.length; i++)
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 250),
                          margin: const EdgeInsets.symmetric(horizontal: 3),
                          width: i == _i ? 22 : 8,
                          height: 8,
                          decoration: BoxDecoration(color: i == _i ? C.primary : C.surface3, borderRadius: BorderRadius.circular(99)),
                        ),
                    ]),
                  ),
                ]);
              },
            ),
          ),
        ]),
      );
}

class _Slide {
  const _Slide(this.color, this.label, this.value, this.suffix, this.note, {this.headline});
  final Color color;
  final String label;
  final num? value;
  final String suffix;
  final String note;
  final String? headline;
}

class _SlideCard extends StatelessWidget {
  const _SlideCard({super.key, required this.slide});
  final _Slide slide;
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(28),
        decoration: BoxDecoration(color: slide.color.withValues(alpha: C.dark ? 0.16 : 0.12), borderRadius: BorderRadius.circular(R.lg), border: Border.all(color: slide.color.withValues(alpha: 0.35))),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          Text(slide.label.toUpperCase(), style: T.label.copyWith(color: slide.color)),
          const SizedBox(height: 18),
          if (slide.headline != null)
            Text(slide.headline!, textAlign: TextAlign.center, style: T.display.copyWith(fontSize: 42, color: slide.color))
          else
            FittedBox(
              fit: BoxFit.scaleDown,
              child: CountUp(value: slide.value ?? 0, suffix: slide.suffix, style: TextStyle(fontSize: 96, fontWeight: FontWeight.w900, letterSpacing: -3, color: slide.color)),
            ),
          const SizedBox(height: 18),
          Text(slide.note, textAlign: TextAlign.center, style: T.body.copyWith(color: C.muted)),
        ]),
      );
}
