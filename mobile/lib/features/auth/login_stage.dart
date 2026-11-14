import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/scheduler.dart';
import 'package:material_ui/material_ui.dart';
import 'package:sensors_plus/sensors_plus.dart';

import '../../core/motion.dart';

/// Shared animation state for the login stage. One ticker updates it; every painter repaints off it.
class StageSim extends ChangeNotifier {
  double t = 0; // seconds of lively time
  double elapsed = 0; // wall seconds since the stage opened (drives the intro)
  Offset touch = const Offset(0.5, 0.5);
  double press = 0;
  Offset tilt = Offset.zero;
  double calm = 0;

  void tickOnce() => notifyListeners();
}

const _ink = Color(0xFF07080C);
const _blue = Color(0xFF1A73E8);
const _violet = Color(0xFF9334E6);
const _teal = Color(0xFF129EAF);
const _coral = Color(0xFFE8604C);
const _paper = Color(0xFFECEBE7);

const _taglines = ['Find the right jobs', 'Resumes from facts you verified', 'You approve every send'];

/// Living "liquid aurora" login backdrop: a fragment-shader metaball field that follows touch and phone tilt,
/// floating glass shapes from the logo, the logo assembling itself, the wordmark, and a typewriter tagline.
/// [child] (the form) is laid out below the hero. [compact] calms everything while the keyboard is open.
class LoginStage extends StatefulWidget {
  const LoginStage({super.key, required this.child, required this.compact});
  final Widget child;
  final bool compact;
  @override
  State<LoginStage> createState() => _LoginStageState();
}

class _LoginStageState extends State<LoginStage> with SingleTickerProviderStateMixin {
  final _sim = StageSim();
  late final Ticker _ticker;
  ui.FragmentShader? _shader;
  StreamSubscription<AccelerometerEvent>? _sub;
  Duration _last = Duration.zero;
  Offset _sensor = Offset.zero;
  Offset _drag = Offset.zero;
  bool _down = false;
  bool _reduced = false;

  @override
  void initState() {
    super.initState();
    _ticker = createTicker(_frame)..start();
    ui.FragmentProgram.fromAsset('shaders/aurora.frag').then((p) {
      if (mounted) setState(() => _shader = p.fragmentShader());
    }).catchError((_) {});
    try {
      _sub = accelerometerEventStream(samplingPeriod: SensorInterval.uiInterval).listen((e) {
        _sensor = Offset((-e.x / 9.8).clamp(-1.0, 1.0), (e.y / 9.8 - 0.5).clamp(-1.0, 1.0));
      }, onError: (_) {});
    } catch (_) {}
  }

  void _frame(Duration d) {
    final dt = ((d - _last).inMicroseconds / 1e6).clamp(0.0, 0.05);
    _last = d;
    final s = _sim;
    s.elapsed = d.inMicroseconds / 1e6;
    s.t += dt;
    s.press += ((_down ? 1.0 : 0.0) - s.press) * (1 - math.exp(-dt * (_down ? 9 : 3)));
    s.calm += ((widget.compact ? 1.0 : 0.0) - s.calm) * (1 - math.exp(-dt * 4));
    final goal = (_sensor + _drag) * (1 - 0.7 * s.calm);
    s.tilt = Offset.lerp(s.tilt, goal, 1 - math.exp(-dt * 6))!;
    s.tickOnce();
  }

  void _pointer(PointerEvent e, Size size, {bool? down}) {
    if (down != null) _down = down;
    if (size.isEmpty) return;
    _sim.touch = Offset(e.position.dx / size.width, e.position.dy / size.height);
    _drag = down == false ? Offset.zero : Offset((_sim.touch.dx - 0.5) * 1.2, (_sim.touch.dy - 0.5) * 1.2);
  }

  @override
  void dispose() {
    _sub?.cancel();
    _ticker.dispose();
    _sim.dispose();
    _shader?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduced = MediaQuery.disableAnimationsOf(context);
    if (reduced != _reduced) {
      _reduced = reduced;
      if (reduced) {
        _ticker.stop();
        _sim.elapsed = 99;
      } else if (!_ticker.isActive) {
        _ticker.start();
      }
    }
    final size = MediaQuery.sizeOf(context);
    return Listener(
      onPointerDown: (e) => _pointer(e, size, down: true),
      onPointerMove: (e) => _pointer(e, size),
      onPointerUp: (e) => _pointer(e, size, down: false),
      onPointerCancel: (e) => _pointer(e, size, down: false),
      child: Stack(fit: StackFit.expand, children: [
        // Background: shader aurora (or a calm static gradient for reduced motion / no shader support).
        RepaintBoundary(
          child: (_reduced || _shader == null)
              ? const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF0B1B3A), Color(0xFF241046), _ink]),
                  ),
                )
              : CustomPaint(painter: _AuroraPainter(_shader!, _sim)),
        ),
        RepaintBoundary(child: CustomPaint(painter: _OrbsPainter(_sim, _reduced))),
        Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
          child: SafeArea(
          child: LayoutBuilder(
            builder: (context, box) => Column(children: [
              Expanded(child: ClipRect(child: _Hero(sim: _sim, compact: widget.compact, reduced: _reduced))),
              ConstrainedBox(constraints: BoxConstraints(maxHeight: math.max(220, box.maxHeight - (widget.compact ? 76 : 170))), child: widget.child),
            ]),
          ),
        ),
        ),
      ]),
    );
  }
}

class _AuroraPainter extends CustomPainter {
  _AuroraPainter(this.shader, this.sim) : super(repaint: sim);
  final ui.FragmentShader shader;
  final StageSim sim;
  @override
  void paint(Canvas canvas, Size size) {
    shader
      ..setFloat(0, size.width)
      ..setFloat(1, size.height)
      ..setFloat(2, sim.t)
      ..setFloat(3, sim.touch.dx)
      ..setFloat(4, sim.touch.dy)
      ..setFloat(5, sim.press)
      ..setFloat(6, sim.tilt.dx)
      ..setFloat(7, sim.tilt.dy)
      ..setFloat(8, sim.calm);
    canvas.drawRect(Offset.zero & size, Paint()..shader = shader);
  }

  @override
  bool shouldRepaint(_AuroraPainter o) => false;
}

/// The logo's two shapes as paths in 768-unit space.
final _ellipseRect = Rect.fromCenter(center: Offset.zero, width: 245, height: 488);
Path _bowl() => Path()
  ..moveTo(385, 383)
  ..lineTo(627, 383)
  ..arcToPoint(const Offset(385, 383), radius: const Radius.elliptical(121, 245), clockwise: true)
  ..close();

Matrix4 _persp(double cx, double cy, double ry, double rx, {double z = 0}) => Matrix4.identity()
  ..setEntry(3, 2, 0.0011)
  ..translateByDouble(cx, cy, z, 1)
  ..rotateY(ry)
  ..rotateX(rx)
  ..translateByDouble(-cx, -cy, 0, 1);

/// Small glass shapes (spheres, tiny logo ellipses and bowls) drifting at different depths.
class _OrbsPainter extends CustomPainter {
  _OrbsPainter(this.sim, this.reduced) : super(repaint: sim);
  final StageSim sim;
  final bool reduced;

  static const _spec = <(double, double, double, int, Color)>[
    // x, y (0..1), depth 0.4..1.4, kind (0 sphere, 1 ellipse, 2 bowl), colour
    (0.14, 0.14, 1.0, 0, _blue),
    (0.84, 0.10, 0.7, 1, _violet),
    (0.90, 0.40, 1.2, 0, _teal),
    (0.07, 0.46, 0.8, 2, _coral),
    (0.78, 0.66, 0.6, 2, _blue),
    (0.22, 0.72, 1.1, 1, _teal),
    (0.55, 0.06, 0.5, 0, _coral),
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final t = reduced ? 0.0 : sim.t;
    final calm = 1 - 0.55 * sim.calm;
    for (var i = 0; i < _spec.length; i++) {
      final (x, y, z, kind, col) = _spec[i];
      final bob = Offset(math.sin(t * 0.5 + i * 1.7) * 10, math.cos(t * 0.4 + i * 2.3) * 14) * calm;
      var p = Offset(x * size.width, y * size.height) + bob + Offset(sim.tilt.dx * 26 * z, sim.tilt.dy * 26 * z);
      // Shapes shy away from the finger.
      final tp = Offset(sim.touch.dx * size.width, sim.touch.dy * size.height);
      final away = p - tp;
      final dist = away.distance;
      if (sim.press > 0.01 && dist < 160 && dist > 0.1) p += away / dist * (160 - dist) * 0.35 * sim.press;
      final r = 20.0 * z + 10;
      final a = (0.55 + 0.25 * math.sin(t + i)) * calm.clamp(0.4, 1.0);
      switch (kind) {
        case 0:
          _sphere(canvas, p, r, col, a);
        case 1:
          canvas.save();
          canvas.transform(_persp(p.dx, p.dy, t * 0.7 + i + sim.tilt.dx, 0.5 * math.sin(t * 0.5 + i)).storage);
          canvas.translate(p.dx, p.dy);
          canvas.scale(r * 2 / 488);
          _glassPath(canvas, Path()..addOval(_ellipseRect), col, a);
          canvas.restore();
        default:
          canvas.save();
          canvas.transform(_persp(p.dx, p.dy, -t * 0.6 - i + sim.tilt.dx, 0.4 * math.cos(t * 0.45 + i)).storage);
          canvas.translate(p.dx, p.dy);
          canvas.scale(r * 2.2 / 488);
          canvas.translate(-506, -383);
          _glassPath(canvas, _bowl(), col, a);
          canvas.restore();
      }
    }
  }

  void _sphere(Canvas canvas, Offset c, double r, Color col, double a) {
    canvas.drawCircle(c, r * 1.9, Paint()..shader = ui.Gradient.radial(c, r * 1.9, [col.withValues(alpha: 0.22 * a), col.withValues(alpha: 0)]));
    final body = Paint()
      ..shader = ui.Gradient.radial(c + Offset(-r * 0.35, -r * 0.4), r * 1.5, [Colors.white.withValues(alpha: 0.5 * a), col.withValues(alpha: 0.28 * a), col.withValues(alpha: 0.05 * a)], [0, 0.55, 1]);
    canvas.drawCircle(c, r, body);
    canvas.drawCircle(c, r, Paint()..style = PaintingStyle.stroke..strokeWidth = 1..color = Colors.white.withValues(alpha: 0.28 * a));
    canvas.drawCircle(c + Offset(-r * 0.38, -r * 0.42), r * 0.14, Paint()..color = Colors.white.withValues(alpha: 0.8 * a));
  }

  void _glassPath(Canvas canvas, Path path, Color col, double a) {
    final b = path.getBounds();
    canvas.drawPath(path, Paint()..shader = ui.Gradient.linear(b.topLeft, b.bottomRight, [Colors.white.withValues(alpha: 0.42 * a), col.withValues(alpha: 0.2 * a)]));
    canvas.drawPath(path, Paint()..style = PaintingStyle.stroke..strokeWidth = 6..color = Colors.white.withValues(alpha: 0.35 * a));
  }

  @override
  bool shouldRepaint(_OrbsPainter o) => o.reduced != reduced;
}

class _Hero extends StatelessWidget {
  const _Hero({required this.sim, required this.compact, required this.reduced});
  final StageSim sim;
  final bool compact;
  final bool reduced;

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, box) {
        final logo = compact ? 48.0 : (box.maxHeight * 0.42).clamp(72.0, 132.0);
        return Center(
          child: FittedBox(
            fit: BoxFit.scaleDown,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 420),
                curve: Curves.easeOutCubic,
                width: logo,
                height: logo,
                child: RepaintBoundary(child: CustomPaint(painter: _LogoPainter(sim, reduced))),
              ),
              SizedBox(height: compact ? 8 : 18),
              _Wordmark(sim: sim, size: compact ? 26 : 38),
              AnimatedSize(
                duration: const Duration(milliseconds: 360),
                curve: Curves.easeOutCubic,
                child: compact ? const SizedBox(width: 1) : Padding(padding: const EdgeInsets.only(top: 10), child: _Typewriter(sim: sim, reduced: reduced)),
              ),
            ]),
          ),
        );
      });
}

/// The logo assembles from two spinning glass shapes flying in from opposite corners, then idles with 3D tilt.
class _LogoPainter extends CustomPainter {
  _LogoPainter(this.sim, this.reduced) : super(repaint: sim);
  final StageSim sim;
  final bool reduced;

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width / 768;
    final e = reduced ? 1.0 : ((sim.elapsed - 0.15) / 1.9).clamp(0.0, 1.0);
    final spring = e == 1 ? 1.0 : softSpring.transform(e);
    final idle = reduced ? 0.0 : sim.t;
    final tx = sim.tilt.dx * 0.5 + 0.12 * math.sin(idle * 0.8);
    final ty = sim.tilt.dy * 0.4 + 0.08 * math.cos(idle * 0.7);
    final settled = Curves.easeIn.transform(((e - 0.7) / 0.3).clamp(0.0, 1.0));

    canvas.save();
    canvas.scale(s);
    // Paper square fades in once the shapes are close, with a soft shadow under it.
    final sq = RRect.fromRectAndRadius(const Rect.fromLTWH(0, 0, 768, 768), const Radius.circular(170));
    canvas.save();
    canvas.transform(_persp(384, 384, tx * 0.5, ty * 0.5).storage);
    if (settled > 0) {
      canvas.drawRRect(sq.shift(const Offset(0, 36)), Paint()..color = Colors.black.withValues(alpha: 0.35 * settled)..maskFilter = const MaskFilter.blur(BlurStyle.normal, 40));
      canvas.drawRRect(sq, Paint()..color = _paper.withValues(alpha: settled));
    }
    canvas.restore();

    final rimA = 0.9 * (1 - settled) + 0.0;
    void shape(Path path, Offset centre, Offset from, double spin, double axisBias) {
      final pos = Offset.lerp(from, Offset.zero, spring)!;
      final spinA = (1 - e) * spin + (e == 1 ? 0 : 0);
      canvas.save();
      canvas.translate(pos.dx, pos.dy);
      canvas.transform(_persp(centre.dx, centre.dy, spinA + tx * 0.9 + axisBias, (1 - e) * 1.4 + ty * 0.7, z: (1 - e) * 120).storage);
      final b = path.getBounds();
      canvas.drawPath(path, Paint()..color = const Color(0xFF0A0B10));
      if (rimA > 0.01) {
        canvas.drawPath(path, Paint()..shader = ui.Gradient.linear(b.topLeft, b.bottomRight, [_blue, _violet, _coral], [0, 0.5, 1])..style = PaintingStyle.stroke..strokeWidth = 14);
        canvas.drawPath(path, Paint()..shader = ui.Gradient.linear(b.topLeft, b.bottomRight, [Colors.white.withValues(alpha: 0.30 * rimA), Colors.white.withValues(alpha: 0)]));
      }
      // Glass sheen, always visible but subtle once the mark is settled.
      canvas.drawPath(path, Paint()..shader = ui.Gradient.linear(b.topLeft, b.center, [Colors.white.withValues(alpha: 0.20 + 0.0 * settled), Colors.white.withValues(alpha: 0)]));
      canvas.restore();
    }

    final ell = Path()..addOval(_ellipseRect.shift(const Offset(262.5, 384)));
    shape(ell, const Offset(262.5, 384), const Offset(-760, -520), math.pi * 4, 0);
    shape(_bowl(), const Offset(506, 383), const Offset(900, -380), -math.pi * 5, 0);
    canvas.restore();
  }

  @override
  bool shouldRepaint(_LogoPainter o) => o.reduced != reduced;
}

class _Wordmark extends StatelessWidget {
  const _Wordmark({required this.sim, required this.size});
  final StageSim sim;
  final double size;
  static const _word = 'Saige AI';

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: sim,
        builder: (context, _) => Row(mainAxisSize: MainAxisSize.min, children: [
          for (var i = 0; i < _word.length; i++)
            () {
              final p = Curves.easeOutCubic.transform(((sim.elapsed - 1.7 - i * 0.06) / 0.7).clamp(0.0, 1.0));
              return Opacity(
                opacity: p,
                child: Transform.translate(
                  offset: Offset(0, 14 * (1 - p)),
                  child: Text(_word[i], style: TextStyle(fontSize: size, fontWeight: FontWeight.w700, letterSpacing: -0.5, height: 1.1, color: Colors.white)),
                ),
              );
            }(),
        ]),
      );
}

/// Types the three truthful taglines one after another. Time-driven from the stage clock, no timers.
class _Typewriter extends StatelessWidget {
  const _Typewriter({required this.sim, required this.reduced});
  final StageSim sim;
  final bool reduced;

  static String textAt(double secs) {
    const type = 0.045, hold = 1.7, erase = 0.02;
    var t = secs;
    for (final line in _taglines) {
      final cycle = line.length * type + hold + line.length * erase + 0.25;
      if (t < cycle) {
        final typed = line.length * type;
        if (t < typed) return line.substring(0, (t / type).floor().clamp(0, line.length));
        if (t < typed + hold) return line;
        final k = ((t - typed - hold) / erase).floor();
        return line.substring(0, (line.length - k).clamp(0, line.length));
      }
      t -= cycle;
    }
    return '';
  }

  @override
  Widget build(BuildContext context) {
    final style = TextStyle(fontSize: 15.5, color: Colors.white.withValues(alpha: 0.78), letterSpacing: 0.2, fontWeight: FontWeight.w500);
    if (reduced) return Text(_taglines.first, style: style);
    final total = _taglines.fold<double>(0, (a, l) => a + l.length * 0.065 + 1.7 + 0.25);
    return ListenableBuilder(
      listenable: sim,
      builder: (context, _) {
        final secs = math.max(0.0, sim.elapsed - 2.6);
        final text = textAt(secs % total);
        final caret = (sim.elapsed * 2).floor().isEven;
        return SizedBox(
          height: 24,
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text(text, style: style),
            Container(width: 2, height: 18, margin: const EdgeInsets.only(left: 3), color: Colors.white.withValues(alpha: caret ? 0.8 : 0)),
          ]),
        );
      },
    );
  }
}
