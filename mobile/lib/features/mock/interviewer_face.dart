import 'dart:math' as math;

import 'package:flutter/scheduler.dart';
import 'package:material_ui/material_ui.dart';

import '../../core/theme.dart';

enum FaceMood { idle, speaking, listening, thinking }

/// Animated interviewer: blinks at random, drifts its gaze, mouth moves while [mood] is speaking,
/// glows green while listening. Pure CustomPainter driven by one ticker (no per-frame allocations beyond paths).
class InterviewerFace extends StatefulWidget {
  const InterviewerFace({super.key, required this.mood, this.size = 220, this.level = 0});
  final FaceMood mood;
  final double size;

  /// Microphone level 0..1 (makes the glow breathe with your voice while listening).
  final double level;
  @override
  State<InterviewerFace> createState() => _InterviewerFaceState();
}

class _InterviewerFaceState extends State<InterviewerFace> with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  final _clock = ValueNotifier<double>(0);
  final _rnd = math.Random();
  double _nextBlink = 1.5;
  double _blinkStart = -10;
  double _blink = 0;
  double _mouth = 0;
  Offset _gaze = Offset.zero;
  Offset _gazeTarget = Offset.zero;
  double _nextGaze = 2;
  double _last = 0;
  double _glow = 0;

  @override
  void initState() {
    super.initState();
    _ticker = createTicker(_tick)..start();
  }

  void _tick(Duration d) {
    final t = d.inMicroseconds / 1e6;
    final dt = (t - _last).clamp(0.0, 0.05);
    _last = t;
    // blink: 0.16s lid cycle, occasionally a double blink
    if (t >= _nextBlink) {
      _blinkStart = t;
      _nextBlink = t + 2.2 + _rnd.nextDouble() * 3.2;
      if (_rnd.nextDouble() < 0.2) _nextBlink = t + 0.28;
    }
    final p = (t - _blinkStart) / 0.16;
    _blink = p >= 0 && p <= 1 ? math.sin(p * math.pi) : 0;
    // mouth: syllable-ish motion while speaking, eased closed otherwise
    final target = widget.mood == FaceMood.speaking ? (0.22 + 0.78 * (math.sin(t * 13.0).abs() * (0.55 + 0.45 * math.sin(t * 4.1 + 1.0).abs()))) : 0.0;
    _mouth += (target - _mouth) * (1 - math.pow(0.0004, dt)).toDouble();
    // gaze: look around lazily; look at the user when listening
    if (t >= _nextGaze) {
      _nextGaze = t + 1.2 + _rnd.nextDouble() * 2.4;
      _gazeTarget = widget.mood == FaceMood.listening ? Offset.zero : Offset((_rnd.nextDouble() - 0.5) * 1.2, (_rnd.nextDouble() - 0.5) * 0.7);
      if (widget.mood == FaceMood.thinking) _gazeTarget = const Offset(0.7, -0.6);
    }
    _gaze = Offset.lerp(_gaze, _gazeTarget, 1 - math.pow(0.002, dt).toDouble())!;
    final g = switch (widget.mood) { FaceMood.speaking => 0.55 + 0.45 * _mouth, FaceMood.listening => 0.5 + widget.level * 0.5, FaceMood.thinking => 0.3, FaceMood.idle => 0.12 };
    _glow += (g - _glow) * (1 - math.pow(0.01, dt)).toDouble();
    _clock.value = t;
  }

  @override
  void dispose() {
    _ticker.dispose();
    _clock.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => RepaintBoundary(
        child: CustomPaint(
          size: Size.square(widget.size),
          painter: _FacePainter(
            clock: _clock,
            read: () => (_blink, _mouth, _gaze, _glow, widget.mood),
          ),
        ),
      );
}

class _FacePainter extends CustomPainter {
  _FacePainter({required this.clock, required this.read}) : super(repaint: clock);
  final ValueNotifier<double> clock;
  final (double, double, Offset, double, FaceMood) Function() read;

  @override
  void paint(Canvas canvas, Size size) {
    final (blink, mouth, gaze, glow, mood) = read();
    final s = size.width;
    final t = clock.value;
    final accent = mood == FaceMood.listening ? C.good : C.primary;
    final c = Offset(s / 2, s / 2 + math.sin(t * 1.3) * s * 0.006);

    canvas.save();
    canvas.translate(c.dx, c.dy);
    canvas.rotate(mood == FaceMood.listening ? 0.035 : math.sin(t * 0.7) * 0.012 + (mood == FaceMood.thinking ? -0.04 : 0));

    // aura
    final aura = Paint()
      ..shader = RadialGradient(colors: [accent.withValues(alpha: 0.30 * glow), accent.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: Offset.zero, radius: s * 0.62));
    canvas.drawCircle(Offset.zero, s * 0.62, aura);
    final ringP = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..color = accent.withValues(alpha: 0.25 + 0.5 * glow);
    canvas.drawCircle(Offset.zero, s * (0.475 + 0.012 * glow * math.sin(t * 6)), ringP);

    // head
    final head = Rect.fromCircle(center: Offset.zero, radius: s * 0.43);
    canvas.drawCircle(
        Offset.zero,
        s * 0.43,
        Paint()
          ..shader = const RadialGradient(center: Alignment(-0.3, -0.4), colors: [Color(0xFF34343C), Color(0xFF141418)]).createShader(head));
    canvas.drawCircle(Offset.zero, s * 0.43, Paint()..style = PaintingStyle.stroke..strokeWidth = 1.2..color = C.line);

    // hair
    final hair = Path()
      ..moveTo(-s * 0.43, -s * 0.02)
      ..cubicTo(-s * 0.47, -s * 0.36, -s * 0.2, -s * 0.52, s * 0.04, -s * 0.46)
      ..cubicTo(s * 0.3, -s * 0.5, s * 0.5, -s * 0.28, s * 0.43, -s * 0.02)
      ..cubicTo(s * 0.36, -s * 0.2, s * 0.14, -s * 0.3, -s * 0.12, -s * 0.28)
      ..cubicTo(-s * 0.28, -s * 0.26, -s * 0.38, -s * 0.16, -s * 0.43, -s * 0.02)
      ..close();
    canvas.drawPath(hair, Paint()..color = const Color(0xFF0A0A0C));
    canvas.drawPath(hair, Paint()..style = PaintingStyle.stroke..strokeWidth = 1..color = accent.withValues(alpha: 0.35));

    // cheeks
    final cheek = Paint()..color = C.primary.withValues(alpha: 0.10 + 0.08 * mouth);
    canvas.drawCircle(Offset(-s * 0.27, s * 0.12), s * 0.06, cheek);
    canvas.drawCircle(Offset(s * 0.27, s * 0.12), s * 0.06, cheek);

    // eyes + brows
    final raise = mood == FaceMood.speaking ? mouth * s * 0.012 : (mood == FaceMood.thinking ? s * 0.02 : 0.0);
    for (final side in [-1.0, 1.0]) {
      final ec = Offset(side * s * 0.165, -s * 0.045);
      final ew = s * 0.075;
      final eh = math.max(s * 0.012, s * 0.09 * (1 - blink));
      final eye = Rect.fromCenter(center: ec, width: ew * 2, height: eh * 2);
      canvas.save();
      canvas.clipPath(Path()..addOval(eye));
      canvas.drawOval(eye, Paint()..color = const Color(0xFFECEBE7));
      final pc = ec + Offset(gaze.dx * s * 0.022, gaze.dy * s * 0.018);
      canvas.drawCircle(pc, s * 0.045, Paint()..color = const Color(0xFF1B1210));
      canvas.drawCircle(pc, s * 0.022, Paint()..color = Colors.black);
      canvas.drawCircle(pc + Offset(-s * 0.014, -s * 0.014), s * 0.01, Paint()..color = Colors.white);
      canvas.restore();
      // lid line
      canvas.drawArc(Rect.fromCenter(center: ec, width: ew * 2.1, height: eh * 2.1), math.pi, math.pi, false, Paint()..style = PaintingStyle.stroke..strokeWidth = s * 0.008..color = const Color(0xFF050506));
      // brow
      final bp = Path()
        ..moveTo(ec.dx - ew * 1.1, ec.dy - s * 0.085 - raise + side * s * 0.004)
        ..quadraticBezierTo(ec.dx, ec.dy - s * 0.125 - raise, ec.dx + ew * 1.1, ec.dy - s * 0.085 - raise - side * s * 0.004);
      canvas.drawPath(bp, Paint()..style = PaintingStyle.stroke..strokeCap = StrokeCap.round..strokeWidth = s * 0.014..color = const Color(0xFF0A0A0C));
    }

    // nose
    canvas.drawPath(
        Path()
          ..moveTo(0, s * 0.01)
          ..quadraticBezierTo(s * 0.022, s * 0.085, -s * 0.004, s * 0.095),
        Paint()..style = PaintingStyle.stroke..strokeCap = StrokeCap.round..strokeWidth = s * 0.007..color = const Color(0xFF55555E));

    // mouth
    final my = s * 0.2;
    final w = s * 0.115 * (1 - 0.22 * mouth);
    final smile = s * 0.028 * (1 - mouth * 0.6);
    final open = mouth * s * 0.105;
    final m = Path()
      ..moveTo(-w, my)
      ..quadraticBezierTo(0, my - s * 0.018 + smile * 0.2, w, my)
      ..quadraticBezierTo(0, my + smile + open + s * 0.012, -w, my)
      ..close();
    canvas.drawPath(m, Paint()..color = Color.lerp(const Color(0xFF3A1018), const Color(0xFF14070A), mouth)!);
    if (mouth > 0.25) {
      // teeth hint
      canvas.save();
      canvas.clipPath(m);
      canvas.drawRect(Rect.fromLTWH(-w, my - s * 0.004, w * 2, s * 0.022 * mouth), Paint()..color = const Color(0xFFECEBE7).withValues(alpha: 0.9));
      canvas.restore();
    }
    canvas.drawPath(m, Paint()..style = PaintingStyle.stroke..strokeJoin = StrokeJoin.round..strokeWidth = s * 0.009..color = C.primary.withValues(alpha: 0.9));

    // neck / shoulders hint
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _FacePainter old) => false; // repaints via [clock]
}
