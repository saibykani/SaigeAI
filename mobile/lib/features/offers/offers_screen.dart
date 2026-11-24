import 'package:material_ui/material_ui.dart';

import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/forms.dart';
import '../../core/widgets/kit.dart';
import '../../core/widgets/ui.dart';

const _factors = ['money', 'growth', 'work_life', 'commute', 'learning', 'user_set'];
const _factorLabel = {'money': 'Money (4 years)', 'growth': 'Growth', 'work_life': 'Work-life (WFH)', 'commute': 'Commute', 'learning': 'Learning', 'user_set': 'My own rating'};
const _defaults = {'money': 40.0, 'growth': 20.0, 'work_life': 15.0, 'commute': 10.0, 'learning': 10.0, 'user_set': 5.0};

String _inr(dynamic v) {
  final n = (v as num?)?.toDouble();
  if (n == null) return '--';
  if (n >= 10000000) return '₹${(n / 10000000).toStringAsFixed(2)} Cr';
  if (n >= 100000) return '₹${(n / 100000).toStringAsFixed(2)} L';
  return '₹${n.round()}';
}

/// Compare your saved offers: in-hand, year-1 and 4-year totals, commute and a weighted score you control.
class OffersScreen extends StatefulWidget {
  const OffersScreen({super.key});
  @override
  State<OffersScreen> createState() => _OffersScreenState();
}

class _OffersScreenState extends State<OffersScreen> {
  final _saved = Resource<List<Map<String, dynamic>>>(() async => asList(await Session.I.api.get('/offers/saved')));
  final _picked = <String>{};
  final _w = Map<String, double>.from(_defaults);
  Map<String, dynamic>? _res;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _saved.load();
  }

  @override
  void dispose() {
    _saved.dispose();
    super.dispose();
  }

  Future<void> _compare() async {
    if (_picked.isEmpty) return;
    setState(() => _busy = true);
    final weights = _factors.map((f) => '$f:${_w[f]!.round()}').join(',');
    final r = await guarded(context, () async => asMap(await Session.I.api.get('/offers/compare', query: {'ids': _picked.join(','), 'weights': weights})));
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (r != null) _res = r;
    });
  }

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Offer compare',
        subtitle: 'Pick 2 to 6 saved offers',
        child: ResourceView<List<Map<String, dynamic>>>(
          resource: _saved,
          builder: (context, saved) {
            if (saved.isEmpty) {
              return const EmptyState(icon: Icons.balance_rounded, title: 'No saved offers', body: 'Save an offer from the salary calculator on the web app and it shows up here to compare.');
            }
            return RefreshIndicatorList(onRefresh: _saved.load, children: [
              for (final o in saved) _offerTile(o),
              const SectionTitle('What matters to you'),
              GlassCard(
                child: Column(children: [
                  for (final f in _factors)
                    Column(children: [
                      Row(children: [Expanded(child: Text(_factorLabel[f]!, style: T.body)), Text('${_w[f]!.round()}', style: T.body.copyWith(fontWeight: FontWeight.w800, color: C.primary))]),
                      Slider(
                        value: _w[f]!,
                        min: 0,
                        max: 100,
                        divisions: 20,
                        activeColor: C.primary,
                        inactiveColor: C.surface3,
                        onChanged: (v) => setState(() => _w[f] = v),
                        onChangeEnd: (_) => _res == null ? null : _compare(),
                      ),
                    ]),
                ]),
              ),
              const SizedBox(height: 14),
              PrimaryButton(label: 'Compare ${_picked.length} offer${_picked.length == 1 ? '' : 's'}', icon: Icons.balance_rounded, busy: _busy, onTap: _picked.isEmpty ? null : _compare),
              if (_res != null) ...[
                const SectionTitle('Result'),
                ..._results(_res!),
              ],
            ]);
          },
        ),
      );

  Widget _offerTile(Map<String, dynamic> o) {
    final id = '${o['id']}';
    final on = _picked.contains(id);
    final inp = asMap(o['input']);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassCard(
        border: on ? C.primary : null,
        onTap: () {
          tap();
          setState(() => on ? _picked.remove(id) : (_picked.length < 6 ? _picked.add(id) : null));
        },
        child: Row(children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            width: 26,
            height: 26,
            decoration: BoxDecoration(shape: BoxShape.circle, color: on ? C.primary : Colors.transparent, border: Border.all(color: on ? C.primary : C.line, width: 2)),
            child: on ? Icon(Icons.check_rounded, size: 17, color: C.onPrimary) : null,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${inp['company'] ?? ''}'.isEmpty ? '${inp['name'] ?? 'Offer'}' : '${inp['company']}  ·  ${inp['name'] ?? 'Offer'}', style: T.h2.copyWith(fontSize: 16.5), maxLines: 1, overflow: TextOverflow.ellipsis),
              Text('CTC ${_inr(o['ctc'])}  ·  in hand ${_inr(o['monthly_in_hand'])}/mo', style: T.small),
            ]),
          ),
        ]),
      ),
    );
  }

  List<Widget> _results(Map<String, dynamic> r) {
    final offers = asList(r['offers']);
    final winner = (r['winner'] as num?)?.toInt();
    return [
      if (winner != null && winner < offers.length)
        Padding(padding: const EdgeInsets.only(bottom: 10), child: Text('Highest score on your weights: ${offers[winner]['company'] ?? ''} ${offers[winner]['name'] ?? ''}', style: T.small)),
      for (var i = 0; i < offers.length; i++) _result(offers[i], i == winner),
      Text('${r['esop_note'] ?? ''}', style: T.small),
    ];
  }

  Widget _result(Map<String, dynamic> o, bool win) {
    final score = (o['score'] as num?) ?? 0;
    final bd = asMap(o['breakdown']);
    final unrated = (o['unrated'] as List? ?? const []).map((e) => '$e').toSet();
    Widget row(String l, String v) => Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Row(children: [Expanded(child: Text(l, style: T.small)), Text(v, style: T.body.copyWith(fontWeight: FontWeight.w700))]));
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: GlassCard(
        border: win ? C.good : null,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text('${o['company'] ?? ''} ${o['name'] ?? ''}'.trim(), style: T.h2.copyWith(fontSize: 17))),
            if (win) const Pill('Best', color: Colors.green, filled: true),
            const SizedBox(width: 8),
            Text(num0(score), style: T.h1.copyWith(color: scoreColor(score.toDouble()))),
          ]),
          const SizedBox(height: 8),
          row('In hand / month', _inr(o['monthly_in_hand'])),
          row('Year 1 total', _inr(o['year1_total'])),
          row('4-year total', _inr(o['total_4y'])),
          row('Commute', '${num0(o['commute_hours_month'])} h/month'),
          const SizedBox(height: 8),
          for (final f in _factors)
            if (bd[f] != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [Expanded(child: Text('${_factorLabel[f]}${unrated.contains(f) ? ' (not rated, neutral)' : ''}', style: T.small)), Text(num0(asMap(bd[f])['score']), style: T.small)]),
                  const SizedBox(height: 4),
                  BarFill(value: ((asMap(bd[f])['score'] as num?) ?? 0) / 100, color: unrated.contains(f) ? C.muted : C.primary, height: 6),
                ]),
              ),
        ]),
      ),
    );
  }
}
