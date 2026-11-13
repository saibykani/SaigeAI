import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:saige_mobile/core/theme.dart';
import 'package:saige_mobile/features/mock/interviewer_face.dart';
import 'package:saige_mobile/features/more/more_hub.dart';

void main() {
  testWidgets('More hub lists the feature groups', (tester) async {
    await tester.pumpWidget(MaterialApp(theme: buildTheme(), home: const MoreHub()));
    await tester.pump(const Duration(seconds: 2));
    expect(find.text('RESUME & ATS'), findsOneWidget);
    expect(find.text('ATS coach'), findsOneWidget);
    expect(find.text('Resume health'), findsOneWidget);
  });

  testWidgets('Interviewer face animates in every mood without errors', (tester) async {
    for (final m in FaceMood.values) {
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: Center(child: InterviewerFace(mood: m)))));
      await tester.pump(const Duration(milliseconds: 700));
      await tester.pump(const Duration(milliseconds: 700));
    }
    expect(tester.takeException(), isNull);
  });
}
