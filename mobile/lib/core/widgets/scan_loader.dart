import 'package:material_ui/material_ui.dart';

import '../theme.dart';
import 'dot_ring.dart';

/// Resume "laser scan": a paper sheet whose lines light up as a crimson laser sweeps down it.
class ScanLoader extends StatefulWidget {
  const ScanLoader({super.key, this.label = 'Reading your resume', this.sub = 'Only facts from the file are used'});
  final String label;
  final String sub;
  @override
  State<ScanLoader> createState() => _ScanLoaderState();
}

class _ScanLoaderState extends State<ScanLoader> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 2200))..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(mainAxisSize: MainAxisSize.min, children: [
        RepaintBoundary(
          child: SizedBox(
            width: 190,
            height: 250,
            child: CustomPaint(painter: _ScanPainter(_c)),
          ),
        ),
        const SizedBox(height: 22),
        Row(mainAxisSize: MainAxisSize.min, children: [
          const DotRing(size: 26, dots: 12),
          const SizedBox(width: 12),
          Text(widget.label, style: T.h2),
        ]),
        const SizedBox(height: 6),
        Text(widget.sub, style: T.small),
      ]);
}

class _ScanPainter extends CustomPainter {
  _ScanPainter(this.a) : super(repaint: a);
  final Animation<double> a;

  @override
  void paint(Canvas canvas, Size s) {
    final page = RRect.fromRectAndRadius(Offset.zero & s, const Radius.circular(18));
    canvas.drawRRect(page, Paint()..color = C.surface2);
    canvas.drawRRect(page, Paint()..style = PaintingStyle.stroke..strokeWidth = 1..color = C.line);
    final y = Curves.easeInOut.transform(a.value) * (s.height - 20) + 10;
    const rows = 13;
    for (var i = 0; i < rows; i++) {
      final ly = 28.0 + i * (s.height - 56) / (rows - 1);
      final w = (i == 0 ? 0.45 : (i % 4 == 3 ? 0.55 : 0.82)) * (s.width - 44);
      final near = (1 - ((ly - y).abs() / 46)).clamp(0.0, 1.0);
      final scanned = ly < y;
      final col = Color.lerp(scanned ? C.surface3 : C.line, C.primary, near)!;
      canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(22, ly - 3, w * (0.9 + 0.1 * near), 6), const Radius.circular(3)), Paint()..color = col);
    }
    // Laser beam + soft trailing glow (gradient, no blur).
    final glow = Rect.fromLTWH(0, y - 34, s.width, 34);
    canvas.drawRect(
      glow,
      Paint()..shader = LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [C.primary.withValues(alpha: 0), C.primary.withValues(alpha: 0.27)]).createShader(glow),
    );
    canvas.drawRect(Rect.fromLTWH(0, y - 1, s.width, 2), Paint()..color = C.primary);
    canvas.drawCircle(Offset(s.width - 2, y), 4, Paint()..color = C.primary);
    canvas.drawCircle(Offset(2, y), 4, Paint()..color = C.primary);
  }

  @override
  bool shouldRepaint(_ScanPainter o) => false;
}
