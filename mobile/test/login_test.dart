import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:saige_mobile/core/theme.dart';
import 'package:saige_mobile/features/auth/auth_screen.dart';

void main() {
  testWidgets('Login renders, toggles to register and shows role cards', (tester) async {
    tester.view.physicalSize = const Size(420, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    // Reduced motion: the card is interactive immediately (no intro choreography to wait for).
    await tester.pumpWidget(MediaQuery(
      data: const MediaQueryData(disableAnimations: true, size: Size(420, 900)),
      child: MaterialApp(theme: buildTheme(), home: const AuthScreen()),
    ));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Continue with Google'), findsOneWidget);
    await tester.tap(find.text('Create account').first, warnIfMissed: false);
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    expect(find.text('Recruiter', skipOffstage: false), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Login honours reduced motion', (tester) async {
    await tester.pumpWidget(MediaQuery(
      data: const MediaQueryData(disableAnimations: true),
      child: MaterialApp(theme: buildTheme(), home: const AuthScreen()),
    ));
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Continue with Google'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
