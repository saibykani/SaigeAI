import 'dart:async';
import 'dart:ui' show PointMode;
import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';
import 'package:sensors_plus/sensors_plus.dart';

import '../theme.dart';

/// 3D-parallax star field. Three depth layers shift in opposite directions as the phone tilts
/// (accelerometer) or the finger drags; drawn with three batched drawPoints calls, so it is cheap.
class ParallaxField extends StatefulWidget {
  const ParallaxField({super.key, this.child, this.count = 90});
  final Widget? child;
  final int count;
  @override
  State<ParallaxField> createState() => _ParallaxFieldState();
}

class _ParallaxFieldState extends State<ParallaxField> with SingleTickerProviderStateMixin {
  late final AnimationController _t = AnimationController(vsync: this, duration: const Duration(seconds: 40))..repeat();
  final ValueNotifier<Offset> _tilt = ValueNotifier(Offset.zero);
  Offset _target = Offset.zero;
  Offset _touch = Offset.zero;
  StreamSubscription<AccelerometerEvent>? _sub;
  late final List<Offset> _pts;
  late final List<int> _layer;

  @override
  void initState() {
    super.initState();
    final r = math.Random(7);
    _pts = List.generate(widget.count, (_) => Offset(r.nextDouble(), r.nextDouble()));
    _layer = List.generate(widget.count, (i) => i % 3);
    try {
      _sub = accelerometerEventStream(samplingPeriod: SensorInterval.uiInterval).listen((e) {
        _target = Offset((-e.x / 9.8).clamp(-1.0, 1.0), (e.y / 9.8).clamp(-1.0, 1.0) - 0.5);
      }, onError: (_) {});
    } catch (_) {}
    _t.addListener(() {
      final goal = _target + _touch;
      _tilt.value = Offset.lerp(_tilt.value, goal, 0.08)!;
    });
  }

  @override
  void dispose() {
    _sub?.cancel();
    _t.dispose();
    _tilt.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Listener(
        behavior: HitTestBehavior.translucent,
        onPointerMove: (e) {
          final s = MediaQuery.sizeOf(context);
          _touch = Offset((e.position.dx / s.width - 0.5) * 1.4, (e.position.dy / s.height - 0.5) * 1.4);
        },
        onPointerUp: (_) => _touch = Offset.zero,
        child: Stack(fit: StackFit.expand, children: [
          RepaintBoundary(
            child: CustomPaint(painter: _FieldPainter(_t, _tilt, _pts, _layer)),
          ),
          if (widget.child != null) widget.child!,
        ]),
      );
}

class _FieldPainter extends CustomPainter {
  _FieldPainter(this.t, this.tilt, this.pts, this.layer) : super(repaint: Listenable.merge([t, tilt]));
  final Animation<double> t;
  final ValueNotifier<Offset> tilt;
  final List<Offset> pts;
  final List<int> layer;

  @override
  void paint(Canvas canvas, Size s) {
    // Soft crimson horizon glow.
    final r = Rect.fromCircle(center: Offset(s.width / 2 + tilt.value.dx * 40, s.height * 1.02), radius: s.width * 0.95);
    canvas.drawRect(Offset.zero & s, Paint()..shader = const RadialGradient(colors: [Color(0x55E5304A), Color(0x00000000)]).createShader(r));
    final buckets = [<Offset>[], <Offset>[], <Offset>[]];
    final drift = t.value * s.height;
    for (var i = 0; i < pts.length; i++) {
      final l = layer[i];
      final depth = 12.0 + l * 22; // px shift per tilt unit
      final x = (pts[i].dx * s.width + tilt.value.dx * depth * (l + 1)) % s.width;
      final y = (pts[i].dy * s.height + drift * (0.15 + l * 0.2) + tilt.value.dy * depth * (l + 1)) % s.height;
      buckets[l].add(Offset(x < 0 ? x + s.width : x, y < 0 ? y + s.height : y));
    }
    const sizes = [1.6, 2.6, 4.0];
    const alphas = [0.35, 0.6, 0.95];
    for (var l = 0; l < 3; l++) {
      canvas.drawPoints(
        PointMode.points,
        buckets[l],
        Paint()
          ..strokeWidth = sizes[l]
          ..strokeCap = StrokeCap.round
          ..color = (l == 2 ? C.primary : C.text).withValues(alpha: alphas[l]),
      );
    }
  }

  @override
  bool shouldRepaint(_FieldPainter o) => false;
}
