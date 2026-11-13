import 'package:material_ui/material_ui.dart';

import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/logo.dart';

/// The mark assembles itself: ellipse springs in, the bowl drops and settles, wordmark fades up.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});
  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))..forward();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: C.bg,
        body: Center(
          child: AnimatedBuilder(
            animation: _c,
            builder: (context, _) {
              final t = _c.value;
              final word = Curves.easeOut.transform(((t - 0.55) / 0.45).clamp(0.0, 1.0));
              return Column(mainAxisSize: MainAxisSize.min, children: [
                Transform.scale(scale: 0.85 + 0.15 * Curves.easeOutBack.transform((t * 1.5).clamp(0.0, 1.0)), child: LogoMark(size: 124, t: t, radius: 0.26)),
                const SizedBox(height: 26),
                Opacity(
                  opacity: word,
                  child: Transform.translate(offset: Offset(0, 14 * (1 - word)), child: const Text('Saige AI', style: T.h1)),
                ),
                const SizedBox(height: 34),
                Opacity(opacity: word, child: const DotRing(size: 30, dots: 12)),
              ]);
            },
          ),
        ),
      );
}
