import 'features/shell/welcome_reveal.dart';
import 'package:material_ui/material_ui.dart';

import 'core/config.dart';
import 'core/native_bridge.dart';
import 'core/session.dart';
import 'core/theme.dart';
import 'core/theme_controller.dart';
import 'features/auth/auth_screen.dart';
import 'features/shell/shell.dart';
import 'features/splash/splash.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ThemeController.I.load();
  await AppConfig.load();
  await Session.I.init();
  await NativeBridge.I.init();
  runApp(const SaigeApp());
}

class SaigeApp extends StatelessWidget {
  const SaigeApp({super.key});
  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: ThemeController.I,
        builder: (context, _) => MaterialApp(
          title: 'Saige AI',
          debugShowCheckedModeBanner: false,
          navigatorKey: ThemeController.I.navigatorKey,
          theme: buildTheme(),
          builder: (context, child) => RepaintBoundary(key: ThemeController.I.boundaryKey, child: child),
          home: const _Root(),
        ),
      );
}

class _Root extends StatefulWidget {
  const _Root();
  @override
  State<_Root> createState() => _RootState();
}

class _RootState extends State<_Root> {
  bool _ready = false;
  bool _sawAuth = false; // the welcome hand-off plays only after an actual sign-in, not on app start

  @override
  void initState() {
    super.initState();
    Future.wait([Session.I.bootstrap(), Future<void>.delayed(SplashScreen.duration)]).then((_) {
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
            page = _sawAuth ? const WelcomeReveal(key: ValueKey('shell'), child: Shell()) : const Shell(key: ValueKey('shell'));
          } else {
            _sawAuth = true;
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
