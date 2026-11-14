import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:saige_mobile/features/mock/interviewer_face.dart';

void main() {
  testWidgets('Interviewer face animates in every mood without errors', (tester) async {
    for (final m in FaceMood.values) {
      await tester.pumpWidget(MaterialApp(home: Scaffold(body: Center(child: InterviewerFace(mood: m)))));
      await tester.pump(const Duration(milliseconds: 700));
      await tester.pump(const Duration(milliseconds: 700));
    }
    expect(tester.takeException(), isNull);
  });
}
