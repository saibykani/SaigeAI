import 'dart:math' as math;

import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

/// Underdamped spring as a Curve (overshoots then settles): used for entrances.
class SpringCurve extends Curve {
  const SpringCurve({this.damping = 7, this.freq = 3.2});
  final double damping;
  final double freq;
  @override
  double transformInternal(double t) => 1 - math.exp(-damping * t) * math.cos(freq * math.pi * t);
}

const springy = SpringCurve();
const softSpring = SpringCurve(damping: 9, freq: 2.2);

void tick() => HapticFeedback.selectionClick();
void tap() => HapticFeedback.lightImpact();
void thump() => HapticFeedback.mediumImpact();
void success() => HapticFeedback.heavyImpact();

/// Page route with depth: the new page rises with a slight 3D tilt while the old one recedes.
class DepthRoute<T> extends PageRouteBuilder<T> {
  DepthRoute({required WidgetBuilder builder})
      : super(
          transitionDuration: const Duration(milliseconds: 480),
          reverseTransitionDuration: const Duration(milliseconds: 320),
          pageBuilder: (c, a, s) => builder(c),
          transitionsBuilder: (c, a, s, child) {
            final t = CurvedAnimation(parent: a, curve: Curves.easeOutCubic, reverseCurve: Curves.easeInCubic);
            final back = CurvedAnimation(parent: s, curve: Curves.easeOut);
            return AnimatedBuilder(
              animation: Listenable.merge([t, back]),
              builder: (c, _) {
                final p = t.value;
                final b = back.value;
                final m = Matrix4.identity()
                  ..setEntry(3, 2, 0.0014)
                  ..translateByDouble(0, (1 - p) * 70, 0, 1)
                  ..rotateX((1 - p) * 0.22)
                  ..scaleByDouble(1 - b * 0.06, 1 - b * 0.06, 1, 1);
                return Opacity(
                  opacity: (p * 1.6).clamp(0.0, 1.0) * (1 - b * 0.4),
                  child: Transform(alignment: Alignment.topCenter, transform: m, child: child),
                );
              },
            );
          },
        );
}

Future<T?> pushDepth<T>(BuildContext c, WidgetBuilder b) => Navigator.of(c).push<T>(DepthRoute<T>(builder: b));

/// Scale + tiny 3D tilt towards the touch point, spring back on release, haptic on tap.
class Pressable extends StatefulWidget {
  const Pressable({super.key, required this.child, this.onTap, this.onLongPress, this.scale = 0.95, this.haptic = true});
  final Widget child;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final double scale;
  final bool haptic;
  @override
  State<Pressable> createState() => _PressableState();
}

class _PressableState extends State<Pressable> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 420), value: 0);
  Offset _tilt = Offset.zero;

  void _down(TapDownDetails d) {
    final s = context.size ?? const Size(1, 1);
    _tilt = Offset((d.localPosition.dx / s.width - 0.5) * 2, (d.localPosition.dy / s.height - 0.5) * 2);
    _c.animateTo(1, duration: const Duration(milliseconds: 90), curve: Curves.easeOut);
  }

  void _up() => _c.animateTo(0, duration: const Duration(milliseconds: 520), curve: const SpringCurve(damping: 6, freq: 2.5));

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onTap != null || widget.onLongPress != null;
    if (!enabled) return widget.child;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: _down,
      onTapCancel: _up,
      onTapUp: (_) => _up(),
      onTap: () {
        if (widget.haptic) tap();
        widget.onTap?.call();
      },
      onLongPress: widget.onLongPress,
      child: AnimatedBuilder(
        animation: _c,
        child: widget.child,
        builder: (context, child) {
          final v = _c.value;
          final s = 1 - (1 - widget.scale) * v;
          final m = Matrix4.identity()
            ..setEntry(3, 2, 0.002)
            ..rotateX(-_tilt.dy * 0.12 * v)
            ..rotateY(_tilt.dx * 0.12 * v)
            ..scaleByDouble(s, s, 1, 1);
          return Transform(alignment: Alignment.center, transform: m, child: child);
        },
      ),
    );
  }
}

/// Fade + rise with spring, delayed by [index] (plays once on first build).
class Stagger extends StatefulWidget {
  const Stagger({super.key, required this.index, required this.child, this.dx = 0});
  final int index;
  final Widget child;
  final double dx;
  @override
  State<Stagger> createState() => _StaggerState();
}

class _StaggerState extends State<Stagger> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 650));
  bool _disposed = false;

  @override
  void initState() {
    super.initState();
    Future.delayed(Duration(milliseconds: math.min(widget.index, 8) * 55), () {
      if (!_disposed) _c.forward();
    });
  }

  @override
  void dispose() {
    _disposed = true;
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        child: widget.child,
        builder: (context, child) {
          final p = softSpring.transform(_c.value);
          return Opacity(
            opacity: Curves.easeOut.transform(_c.value.clamp(0.0, 1.0)),
            child: Transform.translate(offset: Offset(widget.dx * (1 - p), 36 * (1 - p)), child: child),
          );
        },
      );
}

/// Counts up to [value] with an ease-out.
class CountUp extends StatelessWidget {
  const CountUp({super.key, required this.value, this.style, this.suffix = ''});
  final num value;
  final TextStyle? style;
  final String suffix;
  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: value.toDouble()),
        duration: const Duration(milliseconds: 1100),
        curve: Curves.easeOutCubic,
        builder: (_, v, _) => Text('${v.round()}$suffix', style: style),
      );
}
