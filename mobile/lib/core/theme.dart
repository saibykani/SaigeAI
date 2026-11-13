import 'package:material_ui/material_ui.dart';

/// Saige design tokens: deep black, one crimson accent, big radii.
class C {
  static const bg = Color(0xFF000000);
  static const surface = Color(0xFF0D0D0F);
  static const surface2 = Color(0xFF161619);
  static const surface3 = Color(0xFF1F1F24);
  static const line = Color(0xFF26262C);
  static const text = Color(0xFFECEBE7);
  static const muted = Color(0xFF8D8D96);
  static const primary = Color(0xFFE5304A);
  static const primarySoft = Color(0x33E5304A);
  static const good = Color(0xFF3DDC97);
  static const warn = Color(0xFFF5B544);
  static const bad = Color(0xFFFF5A5F);
}

class R {
  static const sm = 14.0;
  static const md = 20.0;
  static const lg = 28.0;
}

ThemeData buildTheme() {
  final base = ThemeData(brightness: Brightness.dark, useMaterial3: true);
  return base.copyWith(
    scaffoldBackgroundColor: C.bg,
    colorScheme: const ColorScheme.dark(primary: C.primary, surface: C.surface, onSurface: C.text, secondary: C.primary),
    splashFactory: NoSplash.splashFactory,
    highlightColor: Colors.transparent,
    textTheme: base.textTheme.apply(bodyColor: C.text, displayColor: C.text, fontFamily: 'Roboto'),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: C.surface2,
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
      hintStyle: const TextStyle(color: C.muted),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(R.md), borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(R.md), borderSide: const BorderSide(color: C.primary, width: 1.4)),
    ),
  );
}

class T {
  static const display = TextStyle(fontSize: 34, fontWeight: FontWeight.w700, letterSpacing: -1.2, height: 1.05, color: C.text);
  static const h1 = TextStyle(fontSize: 26, fontWeight: FontWeight.w700, letterSpacing: -0.8, color: C.text);
  static const h2 = TextStyle(fontSize: 19, fontWeight: FontWeight.w600, letterSpacing: -0.4, color: C.text);
  static const body = TextStyle(fontSize: 15, height: 1.4, color: C.text);
  static const small = TextStyle(fontSize: 13, height: 1.35, color: C.muted);
  static const label = TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, letterSpacing: 1.1, color: C.muted);
}

Color scoreColor(num? s) {
  if (s == null) return C.muted;
  if (s >= 75) return C.good;
  if (s >= 55) return C.warn;
  return C.bad;
}
