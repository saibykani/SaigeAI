import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/scheduler.dart';
import 'package:material_ui/material_ui.dart';

/// The Saige Milky Way, ported from the web login (frontend/components/galaxy.tsx):
/// a slowly rotating 3D spiral galaxy with four arms, warm core bulge, nebula clouds,
/// dark dust lanes, a distant Milky Way band, twinkling field stars, our solar system
/// travelling on an arm, shooting stars and comets.
/// Touch: drag to orbit the camera (with inertia), tap to gently spread nearby stars.
/// Stars are drawn per colour bucket with drawRawPoints, so a frame is a handful of draw calls.
class GalaxyBackground extends StatefulWidget {
  const GalaxyBackground({super.key, required this.child});
  final Widget child;

  @override
  State<GalaxyBackground> createState() => _GalaxyBackgroundState();
}

class _Star {
  _Star(this.r, this.a, this.y, this.speed, this.size, this.bucket);
  final double r, a, y, speed, size;
  final int bucket;
}

class _Blob {
  _Blob(this.r, this.a, this.y, this.size, this.alpha, this.warm);
  final double r, a, y, size, alpha;
  final bool warm;
}

class _Streak {
  _Streak(this.x, this.y, this.vx, this.vy, this.size);
  double x, y, life = 1;
  final double vx, vy, size;
}

const _buckets = <List<double>>[
  [255, 224, 180, 0.95],
  [255, 236, 208, 0.85],
  [250, 244, 232, 0.75],
  [238, 240, 246, 0.7],
  [228, 232, 242, 0.55],
  [214, 220, 236, 0.4],
];

class _GalaxyBackgroundState extends State<GalaxyBackground> with SingleTickerProviderStateMixin {
  final _rnd = math.Random();
  late final Ticker _ticker;
  final _repaint = ValueNotifier<int>(0);
  late final _GalaxyModel model;
  Duration _last = Duration.zero;

  @override
  void initState() {
    super.initState();
    model = _GalaxyModel(_rnd);
    _ticker = createTicker((elapsed) {
      final dt = math.min(0.05, (elapsed - _last).inMicroseconds / 1e6);
      _last = elapsed;
      model.step(dt);
      _repaint.value++;
    })
      ..start();
  }

  @override
  void dispose() {
    _ticker.dispose();
    _repaint.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final reduce = MediaQuery.of(context).disableAnimations;
    if (reduce && _ticker.isActive) _ticker.stop();
    return Stack(fit: StackFit.expand, children: [
      Positioned.fill(
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onPanStart: (_) => model.dragging = true,
          onPanUpdate: (d) {
            model.vYaw = d.delta.dx * 0.0035;
            model.vTilt = d.delta.dy * 0.0025;
          },
          onPanEnd: (_) => model.dragging = false,
          onTapUp: (d) => model.tap(d.localPosition),
          child: RepaintBoundary(child: CustomPaint(painter: _GalaxyPainter(model, _repaint), isComplex: true, willChange: true)),
        ),
      ),
      widget.child,
    ]);
  }
}

class _GalaxyModel {
  _GalaxyModel(this.rnd) {
    const count = 4200;
    for (var i = 0; i < count; i++) {
      final bulge = i % 7 == 0;
      final t = bulge ? math.pow(rnd.nextDouble(), 1.8) * 0.28 : math.pow(rnd.nextDouble(), 0.65).toDouble();
      final arm = i % 4;
      final spread = (1 - t) * 0.45 + 0.06;
      final a = bulge ? rnd.nextDouble() * math.pi * 2 : arm / 4 * math.pi * 2 + t * 5.2 + (rnd.nextDouble() - 0.5) * spread * 1.6;
      final thick = bulge ? (0.28 - t) * 0.55 : (1 - t) * 0.06 + 0.008;
      final b = bulge || t < 0.12 ? (rnd.nextBool() ? 0 : 1) : t < 0.3 ? 2 : t < 0.65 ? 3 : (rnd.nextBool() ? 4 : 5);
      stars.add(_Star(t + (rnd.nextDouble() - 0.5) * 0.03, a, (rnd.nextDouble() - 0.5) * thick, 0.11 / (0.24 + t),
          rnd.nextDouble() < 0.02 ? 1.8 + rnd.nextDouble() * 1.2 : 0.35 + rnd.nextDouble() * 1.05, b));
    }
    stars.sort((p, q) => p.bucket - q.bucket);
    off = Float32List(stars.length * 2);
    vel = Float32List(stars.length * 2);
    for (var i = 0; i < 110; i++) {
      final t = math.pow(rnd.nextDouble(), 0.8) * 0.9 + 0.08;
      clouds.add(_Blob(t, (i % 4) / 4 * math.pi * 2 + t * 5.2 + (rnd.nextDouble() - 0.5) * 0.45, (rnd.nextDouble() - 0.5) * 0.04,
          0.07 + rnd.nextDouble() * 0.13, 0.05 + rnd.nextDouble() * 0.08, t < 0.45 && rnd.nextDouble() < 0.6));
    }
    for (var i = 0; i < 70; i++) {
      final t = rnd.nextDouble() * 0.7 + 0.14;
      lanes.add(_Blob(t, (i % 4) / 4 * math.pi * 2 + t * 5.2 - 0.22, 0, 0.05 + rnd.nextDouble() * 0.07, 0.35 + rnd.nextDouble() * 0.3, false));
    }
    for (var i = 0; i < 180; i++) {
      field.add([rnd.nextDouble(), rnd.nextDouble(), rnd.nextDouble() * 1.2 + 0.2, rnd.nextDouble() * math.pi * 2, rnd.nextDouble() * 0.6 + 0.2]);
    }
    for (var i = 0; i < 250; i++) {
      band.add([rnd.nextDouble(), (rnd.nextDouble() + rnd.nextDouble() + rnd.nextDouble() - 1.5) * 0.08, rnd.nextDouble() * 0.35 + 0.05]);
    }
    for (final p in planets) {
      p.add(rnd.nextDouble() * math.pi * 2);
    }
  }

  final math.Random rnd;
  final stars = <_Star>[];
  final clouds = <_Blob>[];
  final lanes = <_Blob>[];
  final field = <List<double>>[];
  final band = <List<double>>[];
  final meteors = <_Streak>[];
  final comets = <_Streak>[];
  final ripples = <List<double>>[]; // x, y, t
  final pendingTaps = <Offset>[];
  // radius, size, speed, r, g, b, (angle appended)
  final planets = <List<double>>[
    [9, 0.9, 4.1, 190, 180, 170], [14, 1.4, 1.6, 236, 204, 150], [20, 1.6, 1.0, 86, 156, 214],
    [27, 1.2, 0.53, 214, 110, 70], [40, 3.2, 0.084, 222, 186, 140], [52, 2.7, 0.034, 230, 210, 160],
  ];
  late Float32List off, vel;
  double time = 0, yaw = 0.6, tilt = 0.38, vYaw = 0, vTilt = 0, nextMeteor = 0.8;
  bool dragging = false;

  void tap(Offset p) {
    pendingTaps.add(p);
    ripples.add([p.dx, p.dy, 0]);
  }

  void step(double dt) {
    time += dt;
    if (!dragging) {
      vYaw *= 0.94;
      vTilt *= 0.9;
    }
    yaw += vYaw;
    tilt = (tilt + vTilt).clamp(0.04, 1.42);
    if (dragging) {
      vYaw *= 0.6;
      vTilt *= 0.6;
    }
    if (time >= nextMeteor) {
      nextMeteor = time + 2 + rnd.nextDouble();
      meteors.add(_Streak(rnd.nextDouble(), rnd.nextDouble() * 0.45, -(260 + rnd.nextDouble() * 240), 120 + rnd.nextDouble() * 100, 1.2));
    }
    for (final m in meteors) {
      m.life -= dt * 0.9;
    }
    meteors.removeWhere((m) => m.life <= 0);
    if (rnd.nextDouble() < dt * 0.09) {
      final left = rnd.nextBool();
      comets.add(_Streak(left ? rnd.nextDouble() * 0.5 : 0.5 + rnd.nextDouble() * 0.5, -0.02, (left ? 1 : -1) * (40 + rnd.nextDouble() * 50),
          70 + rnd.nextDouble() * 60, 1.4 + rnd.nextDouble() * 1.2));
    }
    for (final c in comets) {
      c.life -= dt * 0.12;
    }
    comets.removeWhere((c) => c.life <= 0);
    for (final r in ripples) {
      r[2] += dt;
    }
    ripples.removeWhere((r) => r[2] > 0.8);
    _dt = dt;
  }

  double _dt = 0;
}

class _GalaxyPainter extends CustomPainter {
  _GalaxyPainter(this.m, Listenable repaint) : super(repaint: repaint);
  final _GalaxyModel m;
  final _pts = List.generate(6, (_) => Float32List(0));

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width, h = size.height;
    final dt = m._dt;
    canvas.drawRect(Offset.zero & size, Paint()..color = Colors.black);

    // Far Milky Way band and twinkling field stars.
    final p = Paint()..color = const Color(0xFFE1E4F0);
    for (final b in m.band) {
      p.color = Color.fromRGBO(225, 228, 240, b[2] * 0.6);
      canvas.drawRect(Rect.fromLTWH(b[0] * w * 1.3 - w * 0.15, h * 0.62 - b[0] * h * 0.25 + b[1] * h, 1, 1), p);
    }
    for (final s in m.field) {
      p.color = Color.fromRGBO(225, 228, 240, ((0.2 + (0.4 + 0.6 * math.sin(m.time * 1.1 + s[3])) * 0.5) * s[4]).clamp(0, 1));
      canvas.drawRect(Rect.fromLTWH(s[0] * w, s[1] * h, s[2], s[2]), p);
    }

    final cx = w / 2, cy = h / 2;
    final scale = math.max(w, h) * 0.66;
    final tilt = m.tilt + math.sin(m.time * 0.05) * 0.04;
    final yaw = m.yaw + m.time * 0.02;
    final cosT = math.cos(tilt), sinT = math.sin(tilt);
    const focal = 2.0, rot = 0.4, roll = -0.14;
    final cr = math.cos(roll), sr = math.sin(roll);
    Offset toLocal(Offset o) => Offset((o.dx - cx) * cr + (o.dy - cy) * sr, -(o.dx - cx) * sr + (o.dy - cy) * cr);

    canvas.save();
    canvas.translate(cx, cy);
    canvas.rotate(roll);

    void glow(double radius, double squash, List<Color> colors, List<double> stops) {
      canvas.save();
      canvas.scale(1, squash);
      final g = Paint()..shader = ui.Gradient.radial(Offset.zero, radius, colors, stops);
      canvas.drawRect(Rect.fromCircle(center: Offset.zero, radius: radius), g);
      canvas.restore();
    }

    glow(scale * 0.95, math.max(0.2, sinT.abs() * 1.4), const [Color(0x38FFECD2), Color(0x0FD2D4E4), Color(0x00000000)], const [0, 0.45, 1]);
    glow(scale * 0.26, 0.42 + 0.5 * cosT.abs(), const [Color(0xF2FFF8E8), Color(0x8CFFE4B8), Color(0x21FFC48C), Color(0x00000000)], const [0, 0.1, 0.4, 1]);

    (double, double, double) project(double r, double a, double y0) {
      final ang = a + yaw;
      final x = math.cos(ang) * r, z0 = math.sin(ang) * r;
      final y = y0 * cosT - z0 * sinT, z = y0 * sinT + z0 * cosT;
      final persp = focal / (focal + z);
      return (x * scale * persp, y * scale * persp, persp);
    }

    // Nebula clouds (additive) then dust lanes.
    final blob = Paint()..blendMode = BlendMode.plus;
    for (final d in m.clouds) {
      final (x, y, ps) = project(d.r, d.a + m.time * (0.11 / (0.24 + d.r)) * rot, d.y);
      final r = d.size * scale * ps / 2;
      final c = d.warm ? const Color(0xFFFFC88C) : Colors.white;
      blob.shader = ui.Gradient.radial(Offset(x, y), r, [c.withValues(alpha: (0.9 * d.alpha * math.min(1, ps) * 2).clamp(0, 1)), c.withValues(alpha: 0)]);
      canvas.drawCircle(Offset(x, y), r, blob);
    }
    final dust = Paint();
    for (final d in m.lanes) {
      final (x, y, ps) = project(d.r, d.a + m.time * (0.11 / (0.24 + d.r)) * rot, 0);
      final r = d.size * scale * ps / 2;
      dust.shader = ui.Gradient.radial(Offset(x, y), r, [Color.fromRGBO(0, 0, 0, 0.55 * d.alpha * 0.8), const Color(0x00000000)]);
      canvas.drawOval(Rect.fromCenter(center: Offset(x, y), width: r * 2, height: r * 1.2), dust);
    }

    // Stars, bucketed, with tap spreads and spring-back.
    final taps = m.pendingTaps.map(toLocal).toList();
    m.pendingTaps.clear();
    const s2 = 240.0;
    final counts = List.filled(6, 0);
    for (final s in m.stars) {
      counts[s.bucket]++;
    }
    for (var b = 0; b < 6; b++) {
      if (_pts[b].length != counts[b] * 2) _pts[b] = Float32List(counts[b] * 2);
    }
    final fill = List.filled(6, 0);
    final halos = <Offset>[];
    final reach = math.sqrt(w * w + h * h) / 2 + 8;
    for (var i = 0; i < m.stars.length; i++) {
      final s = m.stars[i];
      final ang = s.a + yaw + m.time * s.speed * rot;
      final x = math.cos(ang) * s.r, z0 = math.sin(ang) * s.r;
      final y = s.y * cosT - z0 * sinT, z = s.y * sinT + z0 * cosT;
      final ps = focal / (focal + z);
      final bx = x * scale * ps, by = y * scale * ps;
      for (final t in taps) {
        final dx = bx - t.dx, dy = by - t.dy, d2 = dx * dx + dy * dy;
        if (d2 < s2 * s2 && d2 > 0.01) {
          final d = math.sqrt(d2), f = math.pow(1 - d / s2, 2) * 11;
          m.vel[i * 2] += dx / d * f;
          m.vel[i * 2 + 1] += dy / d * f;
        }
      }
      m.vel[i * 2] = (m.vel[i * 2] - m.off[i * 2] * 0.012) * 0.9;
      m.vel[i * 2 + 1] = (m.vel[i * 2 + 1] - m.off[i * 2 + 1] * 0.012) * 0.9;
      m.off[i * 2] += m.vel[i * 2];
      m.off[i * 2 + 1] += m.vel[i * 2 + 1];
      var px = bx + m.off[i * 2], py = by + m.off[i * 2 + 1];
      if (px.abs() > reach || py.abs() > reach) {
        px = 99999;
        py = 99999;
      }
      final k = fill[s.bucket]++;
      _pts[s.bucket][k * 2] = px;
      _pts[s.bucket][k * 2 + 1] = py;
      if (s.size > 1.8 && halos.length < 40) halos.add(Offset(px, py));
    }
    final sp = Paint()
      ..blendMode = BlendMode.plus
      ..strokeCap = StrokeCap.round;
    for (var b = 0; b < 6; b++) {
      final c = _buckets[b];
      sp
        ..color = Color.fromRGBO(c[0].toInt(), c[1].toInt(), c[2].toInt(), c[3])
        ..strokeWidth = b < 2 ? 3.2 : (b < 4 ? 2.6 : 2.0);
      canvas.drawRawPoints(ui.PointMode.points, _pts[b], sp);
    }
    final halo = Paint()..blendMode = BlendMode.plus;
    for (final o in halos) {
      halo.shader = ui.Gradient.radial(o, 16, const [Color(0xCCFFFAF0), Color(0x0FFFFAF0), Color(0x00FFFAF0)], const [0, 0.5, 1]);
      canvas.drawCircle(o, 16, halo);
    }

    // Our solar system on an arm.
    {
      const r0 = 0.55;
      final (sx, sy, ps) = project(r0, 1.2 + m.time * (0.11 / (0.24 + r0)) * rot, 0);
      final k = ps.clamp(0.8, 1.6) * 1.5;
      final inc = math.max(0.28, sinT.abs());
      canvas.drawCircle(Offset(sx, sy), 30 * k,
          Paint()..shader = ui.Gradient.radial(Offset(sx, sy), 30 * k, const [Color(0x73FFC88C), Color(0x24FFC88C), Color(0x00FFC88C)], const [0, 0.4, 1]));
      final orbitP = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 0.8
        ..color = const Color(0x17FFFFFF);
      for (final pl in m.planets) {
        canvas.drawOval(Rect.fromCenter(center: Offset(sx, sy), width: pl[0] * k * 2, height: pl[0] * k * inc * 2), orbitP);
      }
      void planet(List<double> pl) {
        final ang = pl[6] + m.time * pl[2] * 0.9;
        final x = sx + math.cos(ang) * pl[0] * k, y = sy + math.sin(ang) * pl[0] * k * inc;
        final depth = 0.8 + 0.2 * math.sin(ang);
        canvas.drawCircle(Offset(x, y), pl[1] * k * depth, Paint()..color = Color.fromRGBO(pl[3].toInt(), pl[4].toInt(), pl[5].toInt(), 1));
        if (pl[0] == 20) {
          final ma = m.time * 5.5;
          canvas.drawCircle(Offset(x + math.cos(ma) * 3.4 * k, y + math.sin(ma) * 3.4 * k * inc), 0.55 * k, Paint()..color = const Color(0xFFD2D2CD));
        }
        if (pl[0] == 52) {
          canvas.drawOval(Rect.fromCenter(center: Offset(x, y), width: pl[1] * k * 4, height: pl[1] * k * 1.4),
              Paint()
                ..style = PaintingStyle.stroke
                ..strokeWidth = 0.7
                ..color = const Color(0x99E6D2A0));
        }
      }

      bool behind(List<double> pl) => math.sin(pl[6] + m.time * pl[2] * 0.9) < 0;
      m.planets.where(behind).forEach(planet);
      canvas.drawCircle(Offset(sx, sy), 3.2 * k, Paint()..color = const Color(0xFFFFE8B4));
      m.planets.where((pl) => !behind(pl)).forEach(planet);
    }
    canvas.restore();

    // Shooting stars, comets and tap ripples (screen space).
    final line = Paint()
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    for (final s in m.meteors) {
      s.x += s.vx * dt / w;
      s.y += s.vy * dt / h;
      final a = Offset(s.x * w, s.y * h), b = a - Offset(s.vx * 0.12, s.vy * 0.12);
      line
        ..strokeWidth = 1.2
        ..shader = ui.Gradient.linear(a, b, [Color.fromRGBO(255, 255, 255, (s.life * 0.8).clamp(0, 1)), const Color(0x00FFFFFF)]);
      canvas.drawLine(a, b, line);
    }
    for (final c in m.comets) {
      c.x += c.vx * dt / w;
      c.y += c.vy * dt / h;
      final a = Offset(c.x * w, c.y * h), b = a - Offset(c.vx * 1.1, c.vy * 1.1);
      line
        ..strokeWidth = c.size * 1.6
        ..shader = ui.Gradient.linear(a, b, [Color.fromRGBO(255, 244, 225, (c.life * 0.55).clamp(0, 1)), const Color(0x00FFF4E1)]);
      canvas.drawLine(a, b, line);
      canvas.drawCircle(a, c.size * 4,
          Paint()..shader = ui.Gradient.radial(a, c.size * 4, [Color.fromRGBO(255, 250, 240, c.life.clamp(0, 1)), const Color(0x00FFFAF0)]));
    }
    line.shader = null;
    for (final r in m.ripples) {
      line
        ..strokeWidth = 1
        ..color = Color.fromRGBO(255, 240, 220, math.max(0, 0.35 - r[2] * 0.5));
      canvas.drawCircle(Offset(r[0], r[1]), 10 + r[2] * 120, line);
    }
  }

  @override
  bool shouldRepaint(covariant _GalaxyPainter old) => false;
}
