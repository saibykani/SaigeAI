import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import 'core/config.dart';
import 'core/session.dart';
import 'core/theme.dart';
import 'features/auth/auth_screen.dart';
import 'features/shell/shell.dart';
import 'features/splash/splash.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    systemNavigationBarColor: Colors.black,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarIconBrightness: Brightness.light,
  ));
  await AppConfig.load();
  await Session.I.init();
  runApp(const SaigeApp());
}

class SaigeApp extends StatelessWidget {
  const SaigeApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Saige AI',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        home: const _Root(),
      );
}

class _Root extends StatefulWidget {
  const _Root();
  @override
  State<_Root> createState() => _RootState();
}

class _RootState extends State<_Root> {
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    Future.wait([Session.I.bootstrap(), Future<void>.delayed(const Duration(milliseconds: 1900))]).then((_) {
      if (mounted) setState(() => _ready = true);
    });
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: Session.I,
        builder: (context, _) {
          final Widget page;
          if (!_ready) {
            page = const SplashScreen(key: ValueKey('splash'));
          } else if (Session.I.state == AuthState.signedIn) {
            page = const Shell(key: ValueKey('shell'));
          } else {
            page = const AuthScreen(key: ValueKey('auth'));
          }
          return AnimatedSwitcher(
            duration: const Duration(milliseconds: 650),
            switchInCurve: Curves.easeOutCubic,
            transitionBuilder: (child, a) => FadeTransition(opacity: a, child: ScaleTransition(scale: Tween(begin: 1.06, end: 1.0).animate(a), child: child)),
            child: page,
          );
        },
      );
}
