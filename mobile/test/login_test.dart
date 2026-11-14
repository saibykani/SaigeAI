import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:saige_mobile/core/theme.dart';
import 'package:saige_mobile/features/auth/auth_screen.dart';

void main() {
  testWidgets('Sign in is ready instantly and switches to create account with roles', (tester) async {
    tester.view.physicalSize = const Size(420, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(theme: buildTheme(), home: const AuthScreen()));
    await tester.pump();
    expect(find.text('Continue with Google'), findsOneWidget);
    expect(find.text('Sign in'), findsWidgets);
    await tester.tap(find.text('New to Saige? Create account'));
    await tester.pump();
    expect(find.text('Create your account'), findsOneWidget);
    expect(find.text('Recruiter'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
