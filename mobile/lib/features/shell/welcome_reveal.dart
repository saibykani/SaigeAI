import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/logo.dart';

/// Plays once right after sign-in: the logo lifts on the brand colour with "Welcome" with the first name, then the app
/// opens through an expanding circle (like a premium Apple/Google onboarding hand-off). Skipped for reduced motion.
class WelcomeReveal extends StatefulWidget {
  const WelcomeReveal({super.key, required this.child});
  final Widget child;
  @override
  State<WelcomeReveal> createState() => _WelcomeRevealState();
}

class _WelcomeRevealState extends State<WelcomeReveal> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1900));

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _c.value = 1;
    } else if (!_c.isAnimating && _c.value == 0) {
      _c.forward();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final first = (Session.I.user['name'] as String? ?? '').trim().split(' ').first;
    return AnimatedBuilder(
      animation: _c,
      child: widget.child,
      builder: (context, child) {
        final t = _c.value;
        if (t >= 1) return child!;
        final intro = Curves.easeOutCubic.transform((t / 0.45).clamp(0.0, 1.0));
        final reveal = Curves.easeInOutCubic.transform(((t - 0.5) / 0.5).clamp(0.0, 1.0));
        final size = MediaQuery.sizeOf(context);
        final maxR = math.sqrt(size.width * size.width + size.height * size.height);
        return Stack(fit: StackFit.expand, children: [
          ColoredBox(color: C.primary),
          Opacity(
            opacity: (1 - reveal * 1.6).clamp(0.0, 1.0),
            child: Center(
              child: Transform.translate(
                offset: Offset(0, 24 * (1 - intro)),
                child: Opacity(
                  opacity: intro,
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Transform.scale(scale: 0.8 + 0.2 * intro, child: const LogoMark(size: 76, radius: 0.26)),
                    const SizedBox(height: 22),
                    Text(first.isEmpty ? 'Welcome' : 'Welcome, $first',
                        style: TextStyle(color: C.onPrimary, fontSize: 28, fontWeight: FontWeight.w600, letterSpacing: -0.6)),
                    const SizedBox(height: 6),
                    Text("Let's find your next role", style: TextStyle(color: C.onPrimary.withValues(alpha: 0.8), fontSize: 15)),
                  ]),
                ),
              ),
            ),
          ),
          if (reveal > 0)
            ClipPath(
              clipper: _Circle(reveal * maxR, Offset(size.width / 2, size.height / 2)),
              child: Transform.scale(scale: 1.04 - 0.04 * reveal, child: child),
            ),
        ]);
      },
    );
  }
}

class _Circle extends CustomClipper<Path> {
  _Circle(this.r, this.c);
  final double r;
  final Offset c;
  @override
  Path getClip(Size size) => Path()..addOval(Rect.fromCircle(center: c, radius: r));
  @override
  bool shouldReclip(_Circle old) => old.r != r;
}
