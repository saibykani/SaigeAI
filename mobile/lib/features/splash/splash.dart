import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import '../../core/widgets/logo.dart';

/// Opening sequence (about 2.6 s), plays every time the app opens:
///  1. hyperspace: stars streak out from the centre of a black screen,
///  2. the logo flies in from deep space with a 3D turn and a light sweep across its face,
///  3. "Saige AI" rises letter by letter with the tagline,
///  4. the scene pushes forward into the galaxy sign-in (the root cross-fades to it).
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});
  static const duration = Duration(milliseconds: 2600);
  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: SplashScreen.duration);
  final _stars = List.generate(170, (i) {
    final r = math.Random(i * 7919);
    return (r.nextDouble() * math.pi * 2, r.nextDouble(), 0.4 + r.nextDouble() * 1.4);
  });

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _c.value = 0.8;
    } else if (!_c.isAnimating && _c.value == 0) {
      _c.forward();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  double _seg(double t, double a, double b, [Curve c = Curves.easeOutCubic]) => c.transform(((t - a) / (b - a)).clamp(0.0, 1.0));

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: Colors.black,
        body: AnimatedBuilder(
          animation: _c,
          builder: (context, _) {
            final t = _c.value;
            final fly = _seg(t, 0.18, 0.62, Curves.easeOutQuart);
            final sweep = _seg(t, 0.5, 0.78, Curves.easeInOut);
            final word = _seg(t, 0.55, 0.85);
            final push = _seg(t, 0.86, 1.0, Curves.easeInCubic);
            final m = Matrix4.identity()
              ..setEntry(3, 2, 0.0016)
              ..translateByDouble(0.0, 0.0, -900.0 * (1 - fly), 1.0)
              ..rotateY(-1.25 * (1 - fly))
              ..rotateX(0.35 * (1 - fly));
            return Transform.scale(
              scale: 1 + 0.18 * push,
              child: Opacity(
                opacity: 1 - push * 0.9,
                child: Stack(fit: StackFit.expand, children: [
                  RepaintBoundary(child: CustomPaint(painter: _Warp(_stars, t))),
                  Center(
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Opacity(
                        opacity: fly.clamp(0.0, 1.0),
                        child: Transform(
                          alignment: Alignment.center,
                          transform: m,
                          child: Stack(children: [
                            Container(
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(34),
                                boxShadow: [BoxShadow(color: Colors.white.withValues(alpha: 0.25 * fly), blurRadius: 60, spreadRadius: 4)],
                              ),
                              child: const LogoMark(size: 128, radius: 0.26),
                            ),
                            Positioned.fill(
                              child: ClipRRect(
                                borderRadius: BorderRadius.circular(33),
                                child: CustomPaint(painter: _Sweep(sweep)),
                              ),
                            ),
                          ]),
                        ),
                      ),
                      const SizedBox(height: 30),
                      Row(mainAxisSize: MainAxisSize.min, children: [
                        for (final (i, ch) in 'Saige AI'.split('').indexed)
                          Builder(builder: (_) {
                            final k = ((word * 1.6) - i * 0.08).clamp(0.0, 1.0);
                            return Opacity(
                              opacity: k,
                              child: Transform.translate(
                                offset: Offset(0, 18 * (1 - k)),
                                child: Text(ch, style: const TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.w700, letterSpacing: -0.5)),
                              ),
                            );
                          }),
                      ]),
                      const SizedBox(height: 10),
                      Opacity(
                        opacity: _seg(t, 0.7, 0.92),
                        child: Text('Your truthful AI career agent',
                            style: TextStyle(color: Colors.white.withValues(alpha: 0.65), fontSize: 15, letterSpacing: 0.2)),
                      ),
                    ]),
                  ),
                ]),
              ),
            );
          },
        ),
      );
}

/// Hyperspace streaks: each star travels outward from the centre, its trail lengthening as it speeds up.
class _Warp extends CustomPainter {
  _Warp(this.stars, this.t);
  final List<(double, double, double)> stars;
  final double t;
  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final reach = size.longestSide * 0.75;
    final speed = Curves.easeInCubic.transform((t / 0.55).clamp(0.0, 1.0)) * (1 - ((t - 0.55) / 0.3).clamp(0.0, 1.0)) + 0.06;
    final p = Paint()..strokeCap = StrokeCap.round;
    for (final (ang, start, w) in stars) {
      final d = ((start + t * 1.4) % 1.0);
      final r = d * d * reach;
      final dir = Offset(math.cos(ang), math.sin(ang));
      final head = c + dir * r;
      final tail = c + dir * math.max(0, r - (20 + 260 * speed) * d);
      p
        ..strokeWidth = w * (0.6 + d)
        ..color = Colors.white.withValues(alpha: (0.15 + 0.85 * d) * (0.5 + 0.5 * speed));
      canvas.drawLine(tail, head, p);
    }
  }

  @override
  bool shouldRepaint(_Warp old) => old.t != t;
}

/// A diagonal band of light that passes across the logo once.
class _Sweep extends CustomPainter {
  _Sweep(this.v);
  final double v;
  @override
  void paint(Canvas canvas, Size size) {
    if (v <= 0 || v >= 1) return;
    final x = -size.width + v * size.width * 3;
    final rect = Rect.fromLTWH(x, -size.height, size.width * 0.5, size.height * 3);
    canvas.save();
    canvas.translate(size.width / 2, size.height / 2);
    canvas.rotate(0.45);
    canvas.translate(-size.width / 2, -size.height / 2);
    canvas.drawRect(rect,
        Paint()..shader = LinearGradient(colors: [Colors.white.withValues(alpha: 0), Colors.white.withValues(alpha: 0.55), Colors.white.withValues(alpha: 0)]).createShader(rect));
    canvas.restore();
  }

  @override
  bool shouldRepaint(_Sweep old) => old.v != v;
}
