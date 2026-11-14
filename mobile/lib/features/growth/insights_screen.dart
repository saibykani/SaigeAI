import 'package:material_ui/material_ui.dart';

import '../../core/widgets/kit.dart';
import 'company_insights_screen.dart';
import 'growth_screen.dart';

/// One place for market and pipeline numbers: how companies and sources treated your applications, and what roles pay.
class InsightsScreen extends StatefulWidget {
  const InsightsScreen({super.key, this.initial = 'company'});
  final String initial;
  @override
  State<InsightsScreen> createState() => _InsightsScreenState();
}

class _InsightsScreenState extends State<InsightsScreen> {
  late String _tab = widget.initial;

  @override
  Widget build(BuildContext context) => FeatureScaffold(
        title: 'Insights',
        subtitle: 'Your results and what roles pay',
        child: Column(children: [
          const SizedBox(height: 6),
          ChipRow(options: const ['company', 'salary'], labels: const {'company': 'Companies', 'salary': 'Salary'}, value: _tab, onChanged: (v) => setState(() => _tab = v)),
          const SizedBox(height: 8),
          Expanded(
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 320),
              switchInCurve: Curves.easeOutCubic,
              transitionBuilder: (c, a) => FadeTransition(opacity: a, child: SlideTransition(position: Tween(begin: const Offset(0.05, 0), end: Offset.zero).animate(a), child: c)),
              child: _tab == 'company' ? const CompanyInsightsBody(key: ValueKey('c')) : const SalaryInsightBody(key: ValueKey('s')),
            ),
          ),
        ]),
      );
}
