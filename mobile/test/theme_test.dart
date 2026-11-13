import 'package:flutter_test/flutter_test.dart';
import 'package:saige_mobile/core/theme.dart';

void main() {
  test('palettes: unique ids, Light is default, tokens follow the active palette', () {
    expect(palettes.map((p) => p.id).toSet().length, palettes.length);
    expect(palettes.first.id, 'light');
    C.active = paletteById('dark');
    expect(C.dark, isTrue);
    expect(C.bg, palettes[1].bg);
    C.active = paletteById('unknown');
    expect(C.active.id, 'light');
  });
}
