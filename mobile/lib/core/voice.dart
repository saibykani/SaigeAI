import 'package:flutter_tts/flutter_tts.dart';

/// Picks the most human-sounding voice on the phone for [locale].
/// On Android, Google's speech engine ships "network" (neural, online) voices that sound far more natural than the
/// default offline ones, so prefer: Google engine → network voice for the exact locale → any voice of the locale.
/// Speaking rate/pitch are set to natural conversational values (no sped-up robotic delivery).
Future<void> useHumanVoice(FlutterTts tts, String locale) async {
  try {
    final engines = (await tts.getEngines as List?)?.cast<Object?>() ?? const [];
    if (engines.contains('com.google.android.tts')) await tts.setEngine('com.google.android.tts');
  } catch (_) {/* iOS / no engine list */}
  await tts.setLanguage(locale);
  try {
    final raw = (await tts.getVoices as List?) ?? const [];
    final lang = locale.toLowerCase().replaceAll('_', '-');
    final base = lang.split('-').first;
    final voices = [
      for (final v in raw)
        if (v is Map) {'name': '${v['name'] ?? ''}', 'locale': '${v['locale'] ?? ''}'.toLowerCase().replaceAll('_', '-')},
    ].where((v) => v['locale']!.startsWith(base)).toList();
    int score(Map<String, String> v) {
      final n = v['name']!.toLowerCase();
      var s = 0;
      if (v['locale'] == lang) s += 4;
      if (n.contains('network')) s += 6; // Google neural voices
      if (n.contains('enhanced') || n.contains('premium') || n.contains('neural')) s += 5; // iOS / others
      if (n.contains('local')) s += 1;
      if (n.contains('legacy') || n.contains('compact')) s -= 4;
      return s;
    }

    voices.sort((a, b) => score(b) - score(a));
    if (voices.isNotEmpty) await tts.setVoice({'name': voices.first['name']!, 'locale': voices.first['locale']!});
  } catch (_) {/* fall back to the engine default for the locale */}
  await tts.setSpeechRate(0.5); // Android 0.5 == normal human pace
  await tts.setPitch(1.0);
  await tts.setVolume(1.0);
}
