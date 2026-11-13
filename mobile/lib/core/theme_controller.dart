import 'dart:async';
import 'dart:ui' as ui;

import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'theme.dart';

/// Holds the chosen theme, persists it, and switches with a circular reveal from the tap point.
class ThemeController extends ChangeNotifier with WidgetsBindingObserver {
  ThemeController._();
  static final I = ThemeController._();
  static const _key = 'saige-theme';

  /// Wraps the whole app so a snapshot can be taken for the reveal.
  final boundaryKey = GlobalKey();
  final navigatorKey = GlobalKey<NavigatorState>();
  Palette get palette => C.active;

  /// 'system' or a palette id: what the user picked (the active palette may differ when following the system).
  String mode = 'system';

  Palette _resolve(String m) {
    if (m != 'system') return paletteById(m);
    final b = WidgetsBinding.instance.platformDispatcher.platformBrightness;
    return paletteById(b == Brightness.dark ? 'dark' : 'light');
  }

  @override
  void didChangePlatformBrightness() {
    if (mode == 'system') _apply(_resolve('system'));
  }

  Future<void> load() async {
    try {
      final p = await SharedPreferences.getInstance();
      mode = p.getString(_key) ?? 'system';
    } catch (_) {}
    C.active = _resolve(mode);
    WidgetsBinding.instance.addObserver(this);
    _syncChrome();
  }

  void _syncChrome() {
    final p = C.active;
    SystemChrome.setSystemUIOverlayStyle(SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      systemNavigationBarColor: p.bg,
      statusBarIconBrightness: p.dark ? Brightness.light : Brightness.dark,
      systemNavigationBarIconBrightness: p.dark ? Brightness.light : Brightness.dark,
    ));
  }

  Future<void> _save(String id) async {
    try {
      await (await SharedPreferences.getInstance()).setString(_key, id);
    } catch (_) {}
  }

  static void _rebuildAll(Element el) {
    el.markNeedsBuild();
    el.visitChildren(_rebuildAll);
  }

  void _apply(Palette p) {
    C.active = p;
    _syncChrome();
    notifyListeners();
    // Widgets read C.* directly, so force every element to rebuild (state is preserved).
    WidgetsBinding.instance.rootElement?.visitChildren(_rebuildAll);
  }

  /// Switch theme; if [origin] (global position) is given, the new theme grows from it as a circle.
  Future<void> select(String newMode, {Offset? origin}) async {
    final p = _resolve(newMode);
    mode = newMode;
    unawaited(_save(newMode));
    if (p.id == C.active.id) {
      notifyListeners();
      return;
    }
    final overlay = navigatorKey.currentState?.overlay;
    final boundary = boundaryKey.currentContext?.findRenderObject();
    if (overlay == null || boundary is! RenderRepaintBoundary || origin == null) {
      _apply(p);
      return;
    }
    final ui.Image shot;
    try {
      shot = await boundary.toImage(pixelRatio: 1.0);
    } catch (_) {
      _apply(p);
      return;
    }
    final size = boundary.size;
    final ctl = AnimationController(vsync: overlay, duration: const Duration(milliseconds: 750));
    final entry = OverlayEntry(
      builder: (_) => IgnorePointer(
        child: AnimatedBuilder(
          animation: ctl,
          builder: (context, _) => CustomPaint(size: size, painter: _RevealPainter(shot, origin, Curves.easeInOutCubic.transform(ctl.value))),
        ),
      ),
    );
    overlay.insert(entry);
    _apply(p);
    await ctl.forward();
    entry.remove();
    ctl.dispose();
    shot.dispose();
  }
}

/// Paints the old screenshot everywhere except a growing circle, which reveals the new theme beneath.
class _RevealPainter extends CustomPainter {
  _RevealPainter(this.shot, this.origin, this.t);
  final ui.Image shot;
  final Offset origin;
  final double t;

  @override
  void paint(Canvas canvas, Size size) {
    final far = [Offset.zero, Offset(size.width, 0), Offset(0, size.height), Offset(size.width, size.height)].map((c) => (c - origin).distance).reduce((a, b) => a > b ? a : b);
    final path = Path()
      ..fillType = PathFillType.evenOdd
      ..addRect(Offset.zero & size)
      ..addOval(Rect.fromCircle(center: origin, radius: far * t));
    canvas.save();
    canvas.clipPath(path);
    canvas.drawImageRect(shot, Rect.fromLTWH(0, 0, shot.width.toDouble(), shot.height.toDouble()), Offset.zero & size, Paint()..filterQuality = FilterQuality.low);
    canvas.restore();
    canvas.drawCircle(origin, far * t, Paint()..style = PaintingStyle.stroke..strokeWidth = 2..color = C.primary.withValues(alpha: 0.5 * (1 - t)));
  }

  @override
  bool shouldRepaint(_RevealPainter o) => o.t != t;
}
