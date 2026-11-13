import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import '../motion.dart';
import '../theme.dart';

/// Particle burst rendered in the root overlay (one CustomPainter, ~70 particles).
class Confetti {
  static void burst(BuildContext context, {Offset? origin, int count = 70}) {
    final overlay = Overlay.maybeOf(context, rootOverlay: true);
    if (overlay == null) return;
    final size = MediaQuery.sizeOf(context);
    final o = origin ?? Offset(size.width / 2, size.height * 0.45);
    late OverlayEntry entry;
    entry = OverlayEntry(builder: (_) => IgnorePointer(child: _Burst(origin: o, count: count, onDone: () => entry.remove())));
    overlay.insert(entry);
    success();
  }
}

class _Burst extends StatefulWidget {
  const _Burst({required this.origin, required this.count, required this.onDone});
  final Offset origin;
  final int count;
  final VoidCallback onDone;
  @override
  State<_Burst> createState() => _BurstState();
}

class _BurstState extends State<_Burst> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1700))
    ..forward().whenComplete(widget.onDone);
  late final List<_P> _ps;

  @override
  void initState() {
    super.initState();
    final r = math.Random();
    final cols = [C.primary, C.text, C.violet, C.warn, C.good];
    _ps = List.generate(widget.count, (_) {
      final a = r.nextDouble() * math.pi * 2;
      final v = 260 + r.nextDouble() * 520;
      return _P(math.cos(a) * v, math.sin(a) * v - 260, r.nextDouble() * 6.28, (r.nextDouble() - 0.5) * 14, 3 + r.nextDouble() * 4, cols[r.nextInt(cols.length)], r.nextBool());
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => RepaintBoundary(child: CustomPaint(size: Size.infinite, painter: _BurstPainter(_c, widget.origin, _ps)));
}

class _P {
  _P(this.vx, this.vy, this.rot, this.spin, this.size, this.color, this.round);
  final double vx, vy, rot, spin, size;
  final Color color;
  final bool round;
}

class _BurstPainter extends CustomPainter {
  _BurstPainter(this.a, this.o, this.ps) : super(repaint: a);
  final Animation<double> a;
  final Offset o;
  final List<_P> ps;
  @override
  void paint(Canvas canvas, Size s) {
    final t = a.value * 1.7; // seconds
    final fade = (1 - ((a.value - 0.6) / 0.4)).clamp(0.0, 1.0);
    final paint = Paint();
    for (final p in ps) {
      final drag = math.exp(-1.6 * t);
      final x = o.dx + p.vx * (1 - drag) / 1.6;
      final y = o.dy + p.vy * (1 - drag) / 1.6 + 520 * t * t;
      paint.color = p.color.withValues(alpha: fade);
      if (p.round) {
        canvas.drawCircle(Offset(x, y), p.size * 0.6, paint);
      } else {
        canvas.save();
        canvas.translate(x, y);
        canvas.rotate(p.rot + p.spin * t);
        canvas.scale(1, math.cos(t * 9 + p.rot).abs() * 0.8 + 0.2); // fake 3D flip
        canvas.drawRect(Rect.fromCenter(center: Offset.zero, width: p.size * 2, height: p.size), paint);
        canvas.restore();
      }
    }
  }

  @override
  bool shouldRepaint(_BurstPainter o) => false;
}
