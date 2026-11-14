import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:saige_mobile/core/session.dart';
import 'package:saige_mobile/core/theme.dart';
import 'package:saige_mobile/features/shell/app_drawer.dart';

void main() {
  testWidgets('Drawer groups modules and highlights the active tab', (tester) async {
    Session.I.user = {'name': 'Asha Rao', 'role': 'jobseeker'};
    final tab = ValueNotifier(1);
    await tester.pumpWidget(MaterialApp(
      theme: buildTheme(),
      home: Scaffold(
        key: DrawerNav.key,
        onDrawerChanged: (o) => DrawerNav.open.value = o,
        drawer: AppDrawer(tabIndex: tab, onTab: (i) => tab.value = i),
        body: const Center(child: MenuButton()),
      ),
    ));
    await tester.tap(find.byType(MenuButton));
    await tester.pump(const Duration(seconds: 2));
    expect(find.text('Asha Rao'), findsOneWidget);
    expect(find.text('JOB SEARCH'), findsOneWidget);
    expect(find.text('Jobs for you'), findsOneWidget);
    expect(find.text('Sign out'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
