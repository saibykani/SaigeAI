import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';

import '../theme.dart';

/// Glowing dotted progress ring. [progress] 0..1 lights dots around the circle;
/// null means indeterminate (a comet of light chasing around the ring).
class DotRing extends StatefulWidget {
  const DotRing({super.key, this.progress, this.size = 56, this.dots = 28, this.color, this.dotRadius, this.child});
  final double? progress;
  final double size;
  final int dots;
  final Color? color;
  final double? dotRadius;
  final Widget? child;

  /// Brightness (0..1) of dot [i] of [n]. Pure function so it can be unit tested.
  static double lit(int i, int n, double? progress, double spin) {
    if (progress == null) {
      final head = spin * n;
      var d = head - i;
      if (d < 0) d += n;
      return d > n * 0.55 ? 0.0 : math.pow(1 - d / (n * 0.55), 1.6).toDouble();
    }
    final edge = progress.clamp(0.0, 1.0) * n;
    if (i + 1 <= edge) return 1.0;
    if (i < edge) return edge - i; // partial dot at the leading edge
    return 0.0;
  }

  @override
  State<DotRing> createState() => _DotRingState();
}

class _DotRingState extends State<DotRing> with TickerProviderStateMixin {
  late final AnimationController _spin = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500));
  late final AnimationController _prog = AnimationController(vsync: this, duration: const Duration(milliseconds: 900));
  double _target = 0;

  @override
  void initState() {
    super.initState();
    _sync(first: true);
  }

  @override
  void didUpdateWidget(DotRing old) {
    super.didUpdateWidget(old);
    _sync();
  }

  void _sync({bool first = false}) {
    final p = widget.progress;
    if (p == null) {
      if (!_spin.isAnimating) _spin.repeat();
    } else {
      _spin.stop();
      if (first || p != _target) {
        _target = p.clamp(0.0, 1.0);
        _prog.animateTo(_target, curve: Curves.easeOutCubic);
      }
    }
  }

  @override
  void dispose() {
    _spin.dispose();
    _prog.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: SizedBox(
        width: widget.size,
        height: widget.size,
        child: Stack(alignment: Alignment.center, children: [
          CustomPaint(
            size: Size.square(widget.size),
            painter: _RingPainter(
              repaint: Listenable.merge([_spin, _prog]),
              spin: _spin,
              prog: _prog,
              indeterminate: widget.progress == null,
              n: widget.dots,
              color: widget.color ?? C.primary,
              dotRadius: widget.dotRadius ?? widget.size / 26 + 0.8,
            ),
          ),
          if (widget.child != null) widget.child!,
        ]),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter(
      {required Listenable repaint,
      required this.spin,
      required this.prog,
      required this.indeterminate,
      required this.n,
      required this.color,
      required this.dotRadius})
      : super(repaint: repaint);
  final Animation<double> spin;
  final Animation<double> prog;
  final bool indeterminate;
  final int n;
  final Color color;
  final double dotRadius;

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = size.width / 2 - dotRadius * 2.2;
    final off = Paint()..color = C.line;
    final on = Paint()..color = color;
    final glow = Paint()..color = color.withValues(alpha: 0.28);
    for (var i = 0; i < n; i++) {
      final a = -math.pi / 2 + i / n * math.pi * 2;
      final p = c + Offset(math.cos(a), math.sin(a)) * r;
      final l = DotRing.lit(i, n, indeterminate ? null : prog.value, spin.value);
      canvas.drawCircle(p, dotRadius, off);
      if (l > 0.02) {
        canvas.drawCircle(p, dotRadius * (1 + 0.9 * l), glow..color = color.withValues(alpha: 0.28 * l));
        canvas.drawCircle(p, dotRadius * (0.8 + 0.35 * l), on..color = color.withValues(alpha: 0.35 + 0.65 * l));
      }
    }
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.color != color || old.n != n || old.indeterminate != indeterminate;
}
