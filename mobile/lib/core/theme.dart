import 'package:material_ui/material_ui.dart';

import 'motion.dart';

/// One app theme, generated from a seed colour with ColorScheme.fromSeed so every tone is harmonious.
/// Light is the default; Dark and the seed themes (Blue, Green, Purple, Coral, Graphite) sit next to it.
class Palette {
  Palette._({
    required this.id,
    required this.name,
    required this.note,
    required this.seed,
    required this.dark,
    required this.scheme,
    required this.bg,
    required this.surface,
    required this.surface2,
    required this.surface3,
    required this.line,
    required this.text,
    required this.muted,
    required this.blue,
    required this.good,
    required this.warn,
    required this.bad,
    required this.teal,
    required this.violet,
    required this.lime,
  });

  factory Palette.seeded(String id, String name, String note, Color seed, {bool dark = false, Color? bgOverride}) {
    final s = ColorScheme.fromSeed(seedColor: seed, brightness: dark ? Brightness.dark : Brightness.light);
    final w = dark ? const Color(0xFF15161A) : const Color(0xFFFFFFFF);
    final ink = dark ? const Color(0xFFE8EAED) : const Color(0xFF1F2328);
    Color mix(Color a, Color b, double t) => Color.lerp(a, b, t)!;
    final bg = bgOverride ?? (dark ? mix(const Color(0xFF111214), s.primary, 0.05) : mix(const Color(0xFFFFFFFF), s.primary, 0.055));
    return Palette._(
      id: id,
      name: name,
      note: note,
      seed: seed,
      dark: dark,
      scheme: s,
      bg: bg,
      surface: dark ? mix(bg, Colors.white, 0.065) : w,
      surface2: dark ? mix(bg, Colors.white, 0.11) : mix(w, s.primary, 0.075),
      surface3: dark ? mix(bg, Colors.white, 0.18) : mix(w, s.primary, 0.15),
      line: dark ? const Color(0x1FFFFFFF) : mix(w, ink, 0.1),
      text: ink,
      muted: dark ? const Color(0xFFA6ABB3) : const Color(0xFF5F6670),
      blue: dark ? const Color(0xFF8AB4F8) : const Color(0xFF1A73E8),
      good: dark ? const Color(0xFF81C995) : const Color(0xFF1E8E3E),
      warn: dark ? const Color(0xFFFDD663) : const Color(0xFFE37400),
      bad: dark ? const Color(0xFFF28B82) : const Color(0xFFD93025),
      teal: dark ? const Color(0xFF78D9EC) : const Color(0xFF129EAF),
      violet: dark ? const Color(0xFFC58AF9) : const Color(0xFF9334E6),
      lime: dark ? const Color(0xFFC6E26A) : const Color(0xFF689F38),
    );
  }

  final String id, name, note;
  final Color seed;
  final bool dark;
  final ColorScheme scheme;
  final Color bg, surface, surface2, surface3, line, text, muted, blue, good, warn, bad, teal, violet, lime;

  Color get primary => scheme.primary;
  Color get onPrimary => scheme.onPrimary;
  Color get primarySoft => scheme.primary.withValues(alpha: dark ? 0.22 : 0.12);
}

/// The website's Graphite look: pure black, silver primary, one solid Apple-system accent per tone
/// (same values as --tone-* in frontend/app/globals.css). This is the default.
Palette _webGraphite() {
  const primary = Color(0xFFF5F5F7);
  final s = ColorScheme.fromSeed(seedColor: const Color(0xFF8A8F98), brightness: Brightness.dark).copyWith(
    primary: primary,
    onPrimary: Colors.black,
    secondary: const Color(0xFFFF9F0A),
    surface: const Color(0xFF111113),
    onSurface: primary,
  );
  return Palette._(
    id: 'web',
    name: 'Saige',
    note: 'Same as the website',
    seed: const Color(0xFF8A8F98),
    dark: true,
    scheme: s,
    bg: Colors.black,
    surface: const Color(0xFF111113),
    surface2: const Color(0xFF1C1C1E),
    surface3: const Color(0xFF2C2C2E),
    line: const Color(0x1AFFFFFF),
    text: primary,
    muted: const Color(0xFF98989F),
    blue: const Color(0xFF40C8E0),
    good: const Color(0xFF30D158),
    warn: const Color(0xFFFF9F0A),
    bad: const Color(0xFFFF453A),
    teal: const Color(0xFF63E6BE),
    violet: const Color(0xFFBF5AF2),
    lime: const Color(0xFFA3E635),
  );
}

final palettes = <Palette>[
  _webGraphite(),
  Palette.seeded('light', 'Light', 'Clean and bright', const Color(0xFF1A73E8)),
  Palette.seeded('dark', 'Dark', 'Soft charcoal', const Color(0xFF1A73E8), dark: true),
  Palette.seeded('blue', 'Blue', 'Ocean blue', const Color(0xFF0B57D0)),
  Palette.seeded('green', 'Green', 'Fresh green', const Color(0xFF1B8A5A)),
  Palette.seeded('purple', 'Purple', 'Royal purple', const Color(0xFF7C4DFF)),
  Palette.seeded('coral', 'Coral', 'Warm coral', const Color(0xFFE8604C)),
  Palette.seeded('graphite', 'Graphite', 'Quiet dark grey', const Color(0xFF8A8F98), dark: true, bgOverride: const Color(0xFF0E0E10)),
];

Palette paletteById(String? id) => palettes.firstWhere((p) => p.id == id, orElse: () => palettes.first);

/// Saige design tokens. These read the active [Palette], so screens follow the chosen theme.
/// Because they are getters (not constants), widgets using them cannot be `const`.
class C {
  static Palette active = palettes.first;
  static Color get bg => active.bg;
  static Color get surface => active.surface;
  static Color get surface2 => active.surface2;
  static Color get surface3 => active.surface3;
  static Color get line => active.line;
  static Color get text => active.text;
  static Color get muted => active.muted;
  static Color get primary => active.primary;
  static Color get onPrimary => active.onPrimary;
  static Color get primarySoft => active.primarySoft;
  static Color get good => active.good;
  static Color get warn => active.warn;
  static Color get bad => active.bad;
  static Color get blue => active.blue;
  static Color get teal => active.teal;
  static Color get violet => active.violet;
  static Color get lime => active.lime;
  static bool get dark => active.dark;

  /// Soft card shadow: visible on light themes, none on dark (borders do the work there).
  static List<BoxShadow> get shadow => dark ? const [] : [BoxShadow(color: const Color(0xFF1F2A44).withValues(alpha: 0.08), blurRadius: 24, offset: const Offset(0, 8)), BoxShadow(color: const Color(0xFF1F2A44).withValues(alpha: 0.04), blurRadius: 4, offset: const Offset(0, 1))];
}

class R {
  // Bubbly: everything is soft and round. Buttons, chips and fields are full pills.
  static const sm = 22.0;
  static const md = 30.0;
  static const lg = 36.0;
}

ThemeData buildTheme([Palette? p]) {
  p ??= C.active;
  final base = ThemeData(brightness: p.dark ? Brightness.dark : Brightness.light, useMaterial3: true);
  final scheme = p.scheme.copyWith(surface: p.surface, onSurface: p.text);
  return base.copyWith(
    scaffoldBackgroundColor: p.bg,
    colorScheme: scheme,
    splashFactory: NoSplash.splashFactory,
    highlightColor: Colors.transparent,
    textTheme: base.textTheme.apply(bodyColor: p.text, displayColor: p.text, fontFamily: 'Nunito'),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: p.surface2,
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
      hintStyle: TextStyle(color: p.muted),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(R.md), borderSide: BorderSide.none),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(R.md), borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(R.md), borderSide: BorderSide(color: p.primary, width: 2)),
    ),
    filledButtonTheme: const FilledButtonThemeData(style: ButtonStyle(shape: WidgetStatePropertyAll(StadiumBorder()), padding: WidgetStatePropertyAll(EdgeInsets.symmetric(horizontal: 24, vertical: 16)))),
    elevatedButtonTheme: const ElevatedButtonThemeData(style: ButtonStyle(shape: WidgetStatePropertyAll(StadiumBorder()))),
    outlinedButtonTheme: const OutlinedButtonThemeData(style: ButtonStyle(shape: WidgetStatePropertyAll(StadiumBorder()))),
    textButtonTheme: const TextButtonThemeData(style: ButtonStyle(shape: WidgetStatePropertyAll(StadiumBorder()))),
    iconButtonTheme: const IconButtonThemeData(style: ButtonStyle(shape: WidgetStatePropertyAll(CircleBorder()))),
    floatingActionButtonTheme: const FloatingActionButtonThemeData(shape: CircleBorder()),
    pageTransitionsTheme: const PageTransitionsTheme(builders: {TargetPlatform.android: BouncyPageTransitionsBuilder(), TargetPlatform.iOS: BouncyPageTransitionsBuilder()}),
    chipTheme: base.chipTheme.copyWith(shape: const StadiumBorder()),
    cardTheme: CardThemeData(shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(R.lg))),
    dialogTheme: DialogThemeData(shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(R.lg + 4))),
    bottomSheetTheme: const BottomSheetThemeData(shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(R.lg + 8)))),
    popupMenuTheme: PopupMenuThemeData(shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(R.md))),
    snackBarTheme: const SnackBarThemeData(shape: StadiumBorder()),
    listTileTheme: ListTileThemeData(shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(R.md))),
  );
}

class T {
  static TextStyle get display => TextStyle(fontSize: 36, fontWeight: FontWeight.w900, letterSpacing: -0.8, height: 1.05, color: C.text);
  static TextStyle get h1 => TextStyle(fontSize: 29, fontWeight: FontWeight.w800, letterSpacing: -0.6, color: C.text);
  static TextStyle get h2 => TextStyle(fontSize: 19.5, fontWeight: FontWeight.w800, letterSpacing: -0.2, color: C.text);
  static TextStyle get body => TextStyle(fontSize: 15, height: 1.4, color: C.text);
  static TextStyle get small => TextStyle(fontSize: 13, height: 1.35, color: C.muted);
  static TextStyle get label => TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, letterSpacing: 1.1, color: C.muted);
}

Color scoreColor(num? s) {
  if (s == null) return C.muted;
  if (s >= 75) return C.good;
  if (s >= 55) return C.warn;
  return C.bad;
}
