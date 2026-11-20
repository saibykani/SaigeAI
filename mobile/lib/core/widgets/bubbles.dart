import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import '../theme.dart';

/// Soft translucent circles drifting and bobbing behind the content. One controller, one painter, no blur.
class FloatingBubbles extends StatefulWidget {
  const FloatingBubbles({super.key, this.count = 10});
  final int count;
  @override
  State<FloatingBubbles> createState() => _FloatingBubblesState();
}

class _Bubble {
  _Bubble(this.x, this.y, this.r, this.speed, this.phase, this.ampX, this.ampY, this.alpha, this.tint);
  final double x, y, r, speed, phase, ampX, ampY, alpha;
  final int tint;
}

class _FloatingBubblesState extends State<FloatingBubbles> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(seconds: 40));
  late final List<_Bubble> _bs;
  bool _started = false;

  @override
  void initState() {
    super.initState();
    final r = math.Random(7);
    _bs = List.generate(widget.count.clamp(8, 12), (i) {
      return _Bubble(r.nextDouble(), r.nextDouble(), 22 + r.nextDouble() * 58, (1 + r.nextInt(3)).toDouble(), r.nextDouble() * math.pi * 2,
          0.02 + r.nextDouble() * 0.05, 0.015 + r.nextDouble() * 0.04, 0.10 + r.nextDouble() * 0.08, i % 5);
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final still = MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    if (still) {
      _c.stop();
      _started = false;
    } else if (!_started) {
      _c.repeat();
      _started = true;
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cols = [C.primary, C.good, C.warn, C.violet, C.teal];
    return IgnorePointer(
      child: RepaintBoundary(child: CustomPaint(size: Size.infinite, painter: _BubblePainter(_c, _bs, cols))),
    );
  }
}

class _BubblePainter extends CustomPainter {
  _BubblePainter(this.a, this.bs, this.cols) : super(repaint: a);
  final Animation<double> a;
  final List<_Bubble> bs;
  final List<Color> cols;

  @override
  void paint(Canvas canvas, Size s) {
    final t = a.value * math.pi * 2;
    final paint = Paint();
    for (final b in bs) {
      final x = (b.x + math.sin(t * b.speed + b.phase) * b.ampX) * s.width;
      final y = (b.y + math.cos(t * b.speed + b.phase * 1.3) * b.ampY) * s.height;
      final breathe = 1 + 0.06 * math.sin(t * (b.speed + 1) + b.phase);
      paint.color = cols[b.tint].withValues(alpha: b.alpha);
      canvas.drawCircle(Offset(x, y), b.r * breathe, paint);
    }
  }

  @override
  bool shouldRepaint(_BubblePainter old) => old.cols[0] != cols[0] || old.cols[1] != cols[1];
}
