import 'package:material_ui/material_ui.dart';

import '../motion.dart';

/// The Saige mark (off-white square, tall ellipse, half-ellipse bowl) drawn in code.
/// [t] 0..1 assembles it; [morph] lets the bowl separate/rotate (pull-to-refresh).
class LogoPainter extends CustomPainter {
  LogoPainter({this.t = 1, this.morph = 0, this.square = true, this.ink = const Color(0xFF000000), this.paper = const Color(0xFFECEBE7)});
  final double t;
  final double morph;
  final bool square;
  final Color ink;
  final Color paper;

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width / 768;
    canvas.save();
    canvas.scale(s);
    final a = t.clamp(0.0, 1.0);
    if (square) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(const Rect.fromLTWH(0, 0, 768, 768), Radius.circular(160 * (1 - a * 0.0))),
        Paint()..color = paper.withValues(alpha: Curves.easeOut.transform(a)),
      );
    }
    final p = Paint()..color = ink;
    // Ellipse springs in from the left.
    final e = softSpring.transform((a * 1.15).clamp(0.0, 1.0));
    canvas.save();
    canvas.translate(262.5, 384);
    canvas.scale(e.clamp(0.0, 1.4), e.clamp(0.0, 1.4));
    canvas.drawOval(Rect.fromCenter(center: Offset.zero, width: 245, height: 488), p);
    canvas.restore();
    // Bowl drops in from above, pivoting around its flat edge while morphing.
    final b = springy.transform(((a - 0.25) / 0.75).clamp(0.0, 1.0));
    canvas.save();
    canvas.translate(506, 383);
    canvas.translate(0, -300 * (1 - b) - morph * 30);
    canvas.rotate(morph * 1.2);
    canvas.translate(-506, -383);
    final bowl = Path()
      ..moveTo(385, 383)
      ..lineTo(627, 383)
      ..arcToPoint(const Offset(385, 383), radius: const Radius.elliptical(121, 245), clockwise: true)
      ..close();
    canvas.drawPath(bowl, p);
    canvas.restore();
    canvas.restore();
  }

  @override
  bool shouldRepaint(LogoPainter o) => o.t != t || o.morph != morph || o.ink != ink || o.paper != paper;
}

class LogoMark extends StatelessWidget {
  const LogoMark({super.key, this.size = 40, this.t = 1, this.morph = 0, this.radius = 0.22});
  final double size;
  final double t;
  final double morph;
  final double radius;
  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: BorderRadius.circular(size * radius),
        child: CustomPaint(size: Size.square(size), painter: LogoPainter(t: t, morph: morph)),
      );
}
