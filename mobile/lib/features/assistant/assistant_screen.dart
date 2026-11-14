import 'dart:math' as math;

import 'package:flutter_tts/flutter_tts.dart';
import 'package:material_ui/material_ui.dart';
import 'package:speech_to_text/speech_to_text.dart';

import '../shell/app_drawer.dart';
import '../../core/api.dart';
import '../../core/config.dart';
import '../../core/motion.dart';
import '../../core/resource.dart';
import '../../core/session.dart';
import '../../core/theme.dart';
import '../../core/widgets/dot_ring.dart';
import '../../core/widgets/ui.dart';
import '../interviews/interviews_screen.dart';
import '../shell/shell.dart';

enum OrbState { idle, listening, thinking, speaking }

const _langs = <(String, String, String)>[
  ('en', 'English', 'en-IN'),
  ('hi', 'हिन्दी', 'hi-IN'),
  ('te', 'తెలుగు', 'te-IN'),
  ('ta', 'தமிழ்', 'ta-IN'),
  ('kn', 'ಕನ್ನಡ', 'kn-IN'),
  ('ml', 'മലയാളം', 'ml-IN'),
];

class _Msg {
  _Msg(this.role, this.text, [this.actions = const []]);
  final String role;
  final String text;
  final List<Map<String, dynamic>> actions;
}

class AssistantScreen extends StatefulWidget {
  const AssistantScreen({super.key});
  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends State<AssistantScreen> with SingleTickerProviderStateMixin {
  final _msgs = <_Msg>[];
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _stt = SpeechToText();
  final _tts = FlutterTts();
  late final AnimationController _pulse = AnimationController(vsync: this, duration: const Duration(seconds: 2))..repeat();
  final _level = ValueNotifier<double>(0);
  OrbState _state = OrbState.idle;
  int _lang = _langs.indexWhere((l) => l.$1 == AppConfig.lang).clamp(0, _langs.length - 1);
  bool _sttReady = false;
  bool _speak = true;
  String _partial = '';

  @override
  void initState() {
    super.initState();
    _msgs.add(_Msg('assistant', 'Hi ${Session.I.firstName}. Ask about your matches, applications or interviews. Tap the mic to talk.'));
    _tts.setCompletionHandler(() => _setState(OrbState.idle));
    _tts.setCancelHandler(() => _setState(OrbState.idle));
    _tts.setErrorHandler((_) => _setState(OrbState.idle));
  }

  void _setState(OrbState s) {
    if (mounted) setState(() => _state = s);
  }

  @override
  void dispose() {
    _stt.cancel();
    _tts.stop();
    _pulse.dispose();
    _level.dispose();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _toggleMic() async {
    tap();
    if (_state == OrbState.listening) {
      await _stt.stop();
      return;
    }
    await _tts.stop();
    if (!_sttReady) {
      try {
        _sttReady = await _stt.initialize(onStatus: (s) {
          if ((s == 'done' || s == 'notListening') && _state == OrbState.listening) _setState(OrbState.idle);
        }, onError: (_) => _setState(OrbState.idle));
      } catch (_) {
        _sttReady = false;
      }
      if (!_sttReady) {
        if (mounted) toast(context, 'Speech recognition is not available. Type instead.', error: true);
        return;
      }
    }
    _partial = '';
    _setState(OrbState.listening);
    await _stt.listen(
      onSoundLevelChange: (l) => _level.value = ((l + 2) / 12).clamp(0.0, 1.0),
      listenOptions: SpeechListenOptions(partialResults: true, cancelOnError: true, listenMode: ListenMode.dictation, localeId: _langs[_lang].$3.replaceAll('-', '_'), pauseFor: const Duration(seconds: 3)),
      onResult: (r) {
        _partial = r.recognizedWords;
        if (mounted) setState(() {});
        if (r.finalResult && _partial.trim().isNotEmpty) {
          final t = _partial;
          _partial = '';
          _send(t, voice: true);
        }
      },
    );
  }

  Future<void> _send(String text, {bool voice = false}) async {
    final t = text.trim();
    if (t.isEmpty || _state == OrbState.thinking) return;
    _input.clear();
    setState(() {
      _msgs.add(_Msg('user', t));
      _state = OrbState.thinking;
    });
    _toEnd();
    try {
      final history = _msgs.where((m) => m.text.isNotEmpty).toList();
      final r = asMap(await Session.I.api.post('/assistant/chat', data: {
        'messages': [for (final m in history.skip(math.max(0, history.length - 14))) {'role': m.role, 'content': m.text}],
        'language': _langs[_lang].$1,
        'voice': voice || _speak,
      }));
      final reply = '${r['reply'] ?? ''}';
      setState(() => _msgs.add(_Msg('assistant', reply, asList(r['actions']))));
      _toEnd();
      if ((voice || _speak) && reply.isNotEmpty) {
        _setState(OrbState.speaking);
        await _tts.setLanguage(_langs[_lang].$3);
        await _tts.speak(reply);
      } else {
        _setState(OrbState.idle);
      }
    } on ApiException catch (e) {
      setState(() => _msgs.add(_Msg('assistant', e.offline ? 'I am offline right now. Try again when you are connected.' : e.message)));
      _setState(OrbState.idle);
    }
  }

  void _toEnd() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent + 200, duration: const Duration(milliseconds: 400), curve: Curves.easeOutCubic);
      });

  void _action(Map<String, dynamic> a) {
    final h = '${a['href']}';
    tick();
    if (h.contains('interview')) {
      pushDepth(context, (_) => const InterviewsScreen());
    } else if (h.contains('job')) {
      ShellNav.go(1);
    } else if (h.contains('application')) {
      ShellNav.go(2);
    } else if (h.contains('profile') || h.contains('resume')) {
      openProfile(context);
    }
  }

  @override
  Widget build(BuildContext context) => SafeArea(
        bottom: false,
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 12, 0),
            child: Row(children: [
              const MenuButton(),
              Expanded(child: Text('Saige', style: T.display)),
              IconButton(
                tooltip: 'Speak replies',
                onPressed: () {
                  tick();
                  setState(() => _speak = !_speak);
                  if (!_speak) _tts.stop();
                },
                icon: Icon(_speak ? Icons.volume_up_rounded : Icons.volume_off_rounded, color: _speak ? C.primary : C.muted),
              ),
            ]),
          ),
          SizedBox(
            height: 40,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: _langs.length,
              itemBuilder: (context, i) => Pressable(
                onTap: () => setState(() => _lang = i),
                scale: 0.92,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  margin: const EdgeInsets.only(right: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(color: _lang == i ? C.primarySoft : C.surface2, borderRadius: BorderRadius.circular(99), border: Border.all(color: _lang == i ? C.primary : C.line)),
                  child: Text(_langs[i].$2, style: TextStyle(fontWeight: FontWeight.w600, color: _lang == i ? C.text : C.muted)),
                ),
              ),
            ),
          ),
          SizedBox(
            height: 150,
            child: Center(
              child: Pressable(
                onTap: _toggleMic,
                scale: 0.92,
                haptic: false,
                child: RepaintBoundary(
                  child: SizedBox(
                    width: 150,
                    height: 150,
                    child: CustomPaint(painter: _OrbPainter(_pulse, _level, () => _state)),
                  ),
                ),
              ),
            ),
          ),
          Text(
            switch (_state) { OrbState.listening => _partial.isEmpty ? 'Listening...' : _partial, OrbState.thinking => 'Thinking...', OrbState.speaking => 'Speaking', _ => 'Tap the orb to talk' },
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: T.small,
          ),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.builder(
              controller: _scroll,
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
              itemCount: _msgs.length + (_state == OrbState.thinking ? 1 : 0),
              itemBuilder: (context, i) {
                if (i == _msgs.length) return Align(alignment: Alignment.centerLeft, child: Padding(padding: EdgeInsets.all(8), child: DotRing(size: 30, dots: 12)));
                final m = _msgs[i];
                final me = m.role == 'user';
                return Stagger(
                  index: 0,
                  dx: me ? 30 : -30,
                  child: Align(
                    alignment: me ? Alignment.centerRight : Alignment.centerLeft,
                    child: Container(
                      margin: const EdgeInsets.symmetric(vertical: 5),
                      constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.82),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      decoration: BoxDecoration(color: me ? C.primary : C.surface2, borderRadius: BorderRadius.only(topLeft: const Radius.circular(22), topRight: const Radius.circular(22), bottomLeft: Radius.circular(me ? 22 : 6), bottomRight: Radius.circular(me ? 6 : 22)), border: me ? null : Border.all(color: C.line)),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        SelectableText(m.text, style: T.body.copyWith(color: me ? C.onPrimary : C.text)),
                        if (m.actions.isNotEmpty) ...[const SizedBox(height: 10), Wrap(spacing: 8, children: [for (final a in m.actions) Pressable(onTap: () => _action(a), child: Pill('${a['label']}', color: C.text, filled: true))])],
                      ]),
                    ),
                  ),
                );
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 96),
            child: Row(children: [
              Expanded(child: TextField(controller: _input, textInputAction: TextInputAction.send, onSubmitted: _send, decoration: const InputDecoration(hintText: 'Ask Saige anything'))),
              const SizedBox(width: 10),
              Pressable(onTap: () => _send(_input.text), child: Container(width: 54, height: 54, decoration: BoxDecoration(color: C.primary, shape: BoxShape.circle), child: const Icon(Icons.arrow_upward_rounded))),
            ]),
          ),
        ]),
      );
}

/// Orb: a glowing core with radiating rings. Rings expand faster and wider while listening (driven by mic level),
/// ripple inward while thinking, and breathe while speaking.
class _OrbPainter extends CustomPainter {
  _OrbPainter(this.t, this.level, this.state) : super(repaint: Listenable.merge([t, level]));
  final Animation<double> t;
  final ValueNotifier<double> level;
  final OrbState Function() state;

  @override
  void paint(Canvas canvas, Size s) {
    final c = s.center(Offset.zero);
    final st = state();
    final lv = st == OrbState.listening ? level.value : 0.0;
    final base = s.width * 0.26;
    final speed = switch (st) { OrbState.idle => 1.0, OrbState.listening => 2.0, OrbState.thinking => 3.0, OrbState.speaking => 2.5 };
    for (var i = 0; i < 3; i++) {
      final p = (t.value * speed + i / 3) % 1.0;
      final r = base * (1 + p * (0.9 + lv * 0.8));
      canvas.drawCircle(c, r, Paint()..style = PaintingStyle.stroke..strokeWidth = 2..color = C.primary.withValues(alpha: (1 - p) * (st == OrbState.idle ? 0.25 : 0.55)));
    }
    final breathe = st == OrbState.speaking ? 1 + 0.08 * math.sin(t.value * math.pi * 2 * 6) : 1 + 0.04 * math.sin(t.value * math.pi * 2);
    final r = base * breathe * (1 + lv * 0.35);
    final rect = Rect.fromCircle(center: c, radius: r);
    canvas.drawCircle(c, r * 1.35, Paint()..shader = RadialGradient(colors: [C.primary.withValues(alpha: 0.33), C.primary.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: c, radius: r * 1.35)));
    canvas.drawCircle(c, r, Paint()..shader = RadialGradient(center: Alignment(-0.3, -0.35), colors: [Color.lerp(C.primary, Colors.white, 0.4)!, C.primary, Color.lerp(C.primary, Colors.black, 0.45)!], stops: [0, 0.55, 1]).createShader(rect));
    if (st == OrbState.listening) {
      canvas.drawCircle(c, r * 0.28, Paint()..color = Colors.white.withValues(alpha: 0.85));
    }
  }

  @override
  bool shouldRepaint(_OrbPainter o) => false;
}
