import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:saige_mobile/core/widgets/dot_ring.dart';

void main() {
  test('determinate: dots before the edge are lit, after are dark, edge is partial', () {
    expect(DotRing.lit(0, 10, 0.5, 0), 1.0);
    expect(DotRing.lit(4, 10, 0.5, 0), 1.0);
    expect(DotRing.lit(5, 10, 0.5, 0), 0.0);
    expect(DotRing.lit(2, 10, 0.25, 0), closeTo(0.5, 1e-9));
    expect(DotRing.lit(9, 10, 1.0, 0), 1.0);
    expect(DotRing.lit(0, 10, 0.0, 0), 0.0);
  });

  test('indeterminate: head is brightest and a tail fades behind it', () {
    final head = DotRing.lit(5, 20, null, 0.25);
    final behind = DotRing.lit(3, 20, null, 0.25);
    final ahead = DotRing.lit(8, 20, null, 0.25);
    expect(head, closeTo(1.0, 1e-9));
    expect(behind, lessThan(head));
    expect(behind, greaterThan(0));
    expect(ahead, 0.0);
  });

  testWidgets('renders determinate and indeterminate rings without throwing', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: Column(children: [DotRing(progress: 0.6, child: Text('60')), DotRing()]))));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('60'), findsOneWidget);
    expect(find.byType(DotRing), findsNWidgets(2));
    await tester.pumpWidget(const SizedBox());
  });
}
